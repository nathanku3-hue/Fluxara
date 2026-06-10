"""
env.py

MVP environment for Fluxara: a multi-rate AI data-center flexibility simulator.

Design choices for v0.1:
- 1-second plant clock for thermal and checkpoint-age state.
- 5-minute market/control clock for LMP-based bidding and power-cap decisions.
- First-order RC surrogate for representative GPU/HBM junction temperature.
- Coffin-Manson-style fractional damage proxy on power-cap thermal cycles.
- Continuous checkpoint effort in [0, 1] rather than discrete checkpoint jobs.

This is intentionally a surrogate, not a package-reliability model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import math
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class FluxaraEnvConfig:
    # Simulation clocks
    dt_s: int = 1
    market_interval_s: int = 300
    n_market_steps: int = 288  # one day at 5-minute resolution

    # Site / representative GPU scaling
    site_mw: float = 10.0
    min_power_frac: float = 0.55
    initial_power_frac: float = 1.0
    representative_gpu_tdp_w: float = 700.0

    # First-order RC junction-temperature surrogate
    ambient_c: float = 25.0
    thermal_r_c_per_w: float = 0.075
    thermal_tau_s: float = 45.0
    initial_tj_c: float = 65.0

    # Coffin-Manson-style damage proxy
    # N_f = fatigue_C * (DeltaT)^(-fatigue_exp)
    # damage per equivalent cycle = 1 / N_f = DeltaT^fatigue_exp / fatigue_C
    fatigue_C: float = 1.0e12
    fatigue_exp: float = 5.0
    damage_cost_per_fraction: float = 3.0e8  # $ if damage ledger reaches 1.0
    min_counted_delta_t_c: float = 0.5

    # Simple dwell/creep multiplier, deliberately conservative but optional.
    dwell_enabled: bool = True
    dwell_threshold_c: float = 75.0
    dwell_coeff_per_s: float = 2.0e-12

    # Checkpoint liquidity surrogate
    checkpoint_age_s0: float = 1800.0
    checkpoint_refresh_rate_per_s: float = 1.0 / 300.0
    base_interruptible_frac: float = 0.10
    checkpoint_interruptible_gain: float = 0.75

    # Synthetic data generation
    seed: int = 7


class FluxaraEnv:
    """Multi-rate Fluxara plant/market environment.

    Parameters
    ----------
    lmp_df:
        Optional DataFrame with at least column ``lmp_usd_per_mwh`` and optionally
        ``carbon_kg_per_mwh``. One row per market interval.
    gpu_trace_df:
        Optional DataFrame for future use. v0.1 accepts it but does not require it.
    config:
        Environment configuration.
    """

    def __init__(
        self,
        lmp_df: Optional[pd.DataFrame] = None,
        gpu_trace_df: Optional[pd.DataFrame] = None,
        config: Optional[FluxaraEnvConfig] = None,
    ) -> None:
        self.cfg = config or FluxaraEnvConfig()
        self.rng = np.random.default_rng(self.cfg.seed)

        if self.cfg.market_interval_s % self.cfg.dt_s != 0:
            raise ValueError("market_interval_s must be an integer multiple of dt_s")

        self.ticks_per_market = self.cfg.market_interval_s // self.cfg.dt_s
        self.lmp_df = self._prepare_lmp(lmp_df)
        self.gpu_trace_df = gpu_trace_df
        self.reset()

    def reset(self) -> Dict[str, Any]:
        self.t_s = 0
        self.market_idx = 0
        self.power_frac = self.cfg.initial_power_frac
        self.prev_power_frac = self.cfg.initial_power_frac
        self.tj_c = self.cfg.initial_tj_c
        self.damage_fraction = 0.0
        self.checkpoint_age_s = self.cfg.checkpoint_age_s0
        self.last_action: Dict[str, float] = {
            "power_frac": self.power_frac,
            "checkpoint_effort": 0.0,
        }
        self.history = []
        return self.observe()

    def observe(self) -> Dict[str, Any]:
        row = self.lmp_df.iloc[min(self.market_idx, len(self.lmp_df) - 1)]
        interruptible = self._interruptible_frac()
        return {
            "t_s": self.t_s,
            "market_idx": self.market_idx,
            "power_frac": self.power_frac,
            "prev_power_frac": self.prev_power_frac,
            "site_mw": self.cfg.site_mw,
            "min_power_frac": self.cfg.min_power_frac,
            "tj_c": self.tj_c,
            "damage_fraction": self.damage_fraction,
            "checkpoint_age_s": self.checkpoint_age_s,
            "interruptible_frac": interruptible,
            "interruptible_mw": self.cfg.site_mw * interruptible,
            "lmp_usd_per_mwh": float(row["lmp_usd_per_mwh"]),
            "carbon_kg_per_mwh": float(row.get("carbon_kg_per_mwh", 0.0)),
        }

    def forecast(self, horizon: int) -> pd.DataFrame:
        start = self.market_idx
        stop = min(start + horizon, len(self.lmp_df))
        out = self.lmp_df.iloc[start:stop].copy()
        if len(out) < horizon:
            pad = pd.concat([out.iloc[[-1]].copy()] * (horizon - len(out)), ignore_index=True)
            out = pd.concat([out, pad], ignore_index=True)
        return out.reset_index(drop=True)

    def step_market(self, action: Dict[str, float]) -> Dict[str, Any]:
        """Apply one market-window action and simulate second-level plant state."""
        if self.market_idx >= self.cfg.n_market_steps:
            raise RuntimeError("Simulation already finished")

        power_frac = float(np.clip(action.get("power_frac", self.power_frac), self.cfg.min_power_frac, 1.0))
        checkpoint_effort = float(np.clip(action.get("checkpoint_effort", 0.0), 0.0, 1.0))

        self._apply_power_cap_cycle_damage(power_frac)
        self.prev_power_frac = self.power_frac
        self.power_frac = power_frac
        self.last_action = {"power_frac": power_frac, "checkpoint_effort": checkpoint_effort}

        for _ in range(self.ticks_per_market):
            self._step_plant_one_tick(checkpoint_effort)

        self.market_idx += 1
        return self.observe()

    def done(self) -> bool:
        return self.market_idx >= self.cfg.n_market_steps

    def _step_plant_one_tick(self, checkpoint_effort: float) -> None:
        dt = self.cfg.dt_s
        prev_tj = self.tj_c
        gpu_power_w = self.power_frac * self.cfg.representative_gpu_tdp_w
        t_inf = self.cfg.ambient_c + self.cfg.thermal_r_c_per_w * gpu_power_w
        alpha = 1.0 - math.exp(-dt / self.cfg.thermal_tau_s)
        self.tj_c = prev_tj + alpha * (t_inf - prev_tj)

        # Optional creep-like dwell damage proxy at elevated temperature.
        if self.cfg.dwell_enabled and self.tj_c > self.cfg.dwell_threshold_c:
            excess = self.tj_c - self.cfg.dwell_threshold_c
            self.damage_fraction += self.cfg.dwell_coeff_per_s * excess * dt

        # Continuous checkpoint refresh model.
        self.checkpoint_age_s += dt
        refresh = checkpoint_effort * self.cfg.checkpoint_refresh_rate_per_s * dt
        if refresh > 0:
            self.checkpoint_age_s *= math.exp(-refresh)

        self.t_s += dt

        self.history.append(
            {
                "t_s": self.t_s,
                "market_idx": self.market_idx,
                "power_frac": self.power_frac,
                "tj_c": self.tj_c,
                "damage_fraction": self.damage_fraction,
                "checkpoint_age_s": self.checkpoint_age_s,
                "lmp_usd_per_mwh": self.lmp_df.iloc[self.market_idx]["lmp_usd_per_mwh"],
            }
        )

    def _apply_power_cap_cycle_damage(self, new_power_frac: float) -> None:
        """Damage proxy from changing the power cap setpoint.

        We approximate the thermal-cycle amplitude by the change in steady-state
        junction temperature implied by the old and new power caps.
        """
        old_t_inf = self.cfg.ambient_c + self.cfg.thermal_r_c_per_w * (
            self.power_frac * self.cfg.representative_gpu_tdp_w
        )
        new_t_inf = self.cfg.ambient_c + self.cfg.thermal_r_c_per_w * (
            new_power_frac * self.cfg.representative_gpu_tdp_w
        )
        delta_t = abs(new_t_inf - old_t_inf)
        if delta_t < self.cfg.min_counted_delta_t_c:
            return
        nf = self.cfg.fatigue_C * (delta_t ** (-self.cfg.fatigue_exp))
        self.damage_fraction += 1.0 / max(nf, 1.0)

    def _interruptible_frac(self) -> float:
        # Fresher checkpoints mean more of the load is safely interruptible.
        freshness = math.exp(-self.checkpoint_age_s / 1800.0)
        return float(
            np.clip(
                self.cfg.base_interruptible_frac + self.cfg.checkpoint_interruptible_gain * freshness,
                0.0,
                1.0,
            )
        )

    def _prepare_lmp(self, lmp_df: Optional[pd.DataFrame]) -> pd.DataFrame:
        if lmp_df is not None:
            df = lmp_df.copy()
            if "lmp_usd_per_mwh" not in df.columns:
                raise ValueError("lmp_df must contain 'lmp_usd_per_mwh'")
            if "carbon_kg_per_mwh" not in df.columns:
                df["carbon_kg_per_mwh"] = 0.0
            if len(df) < self.cfg.n_market_steps:
                raise ValueError("lmp_df has fewer rows than n_market_steps")
            return df.iloc[: self.cfg.n_market_steps].reset_index(drop=True)

        # Synthetic CAISO-like daily price with evening peak, occasional scarcity spike,
        # and a midday solar dip. This is only a fixture for unit tests.
        n = self.cfg.n_market_steps
        t = np.arange(n) / n
        base = 45 + 20 * np.sin(2 * np.pi * (t - 0.65))
        solar_dip = -35 * np.exp(-((t - 0.52) ** 2) / (2 * 0.06**2))
        evening_peak = 70 * np.exp(-((t - 0.78) ** 2) / (2 * 0.04**2))
        noise = self.rng.normal(0, 5, size=n)
        lmp = np.clip(base + solar_dip + evening_peak + noise, -40, 300)
        # One volatility spike.
        spike_idx = int(0.80 * n)
        lmp[spike_idx : spike_idx + 3] += np.array([160, 220, 120])[: max(0, min(3, n - spike_idx))]

        carbon = 260 + 90 * np.sin(2 * np.pi * (t - 0.70)) - 100 * np.exp(-((t - 0.52) ** 2) / (2 * 0.07**2))
        carbon = np.clip(carbon, 80, 600)
        return pd.DataFrame({"lmp_usd_per_mwh": lmp, "carbon_kg_per_mwh": carbon})

    def history_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.history)
