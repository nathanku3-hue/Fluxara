"""
solver.py

Continuous MPC solver for Fluxara v0.1.

Primary intended backend: CVXPY + OSQP for a convex QP.
Fallback: scipy.optimize.minimize if CVXPY is not installed.

The v0.1 solver relaxes checkpoint and pausing decisions into continuous fractions.
Discrete job-level checkpointing / pausing should be layered on later as a rounding
or dispatch stage after the fast convex controller has produced setpoints.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class FluxaraSolverConfig:
    horizon_windows: int = 12               # 1 hour at 5-min resolution
    market_interval_s: int = 300
    min_power_frac: float = 0.55
    site_mw: float = 10.0

    # Economic objective weights
    carbon_price_usd_per_kg: float = 0.0
    sla_penalty_usd: float = 1200.0
    ramp_penalty_usd: float = 250.0
    fatigue_proxy_penalty_usd: float = 600.0
    checkpoint_linear_usd: float = 30.0
    checkpoint_quadratic_usd: float = 800.0

    # Continuous checkpoint-liquidity relaxation
    base_interruptible_frac: float = 0.10
    checkpoint_interruptible_gain: float = 0.75

    # CVXPY settings
    solver: str = "OSQP"
    verbose: bool = False


class FluxaraSolver:
    def __init__(self, config: Optional[FluxaraSolverConfig] = None) -> None:
        self.cfg = config or FluxaraSolverConfig()

    def solve(self, state: Dict[str, Any], forecast_df: pd.DataFrame) -> Dict[str, float]:
        """Return first-window action: power_frac and checkpoint_effort."""
        forecast = forecast_df.iloc[: self.cfg.horizon_windows].reset_index(drop=True)
        if len(forecast) < self.cfg.horizon_windows:
            raise ValueError("forecast_df shorter than horizon_windows")

        try:
            return self._solve_cvxpy(state, forecast)
        except Exception:
            # Keep the MVP runnable on machines without cvxpy/OSQP installed.
            return self._solve_scipy(state, forecast)

    def _problem_arrays(self, state: Dict[str, Any], forecast: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        price = forecast["lmp_usd_per_mwh"].to_numpy(dtype=float)
        carbon = forecast.get("carbon_kg_per_mwh", pd.Series(np.zeros(len(forecast)))).to_numpy(dtype=float)
        return price, carbon

    def _solve_cvxpy(self, state: Dict[str, Any], forecast: pd.DataFrame) -> Dict[str, float]:
        import cvxpy as cp  # type: ignore

        H = self.cfg.horizon_windows
        price, carbon = self._problem_arrays(state, forecast)
        dt_h = self.cfg.market_interval_s / 3600.0
        prev_u = float(state.get("power_frac", 1.0))
        interruptible_now = float(state.get("interruptible_frac", self.cfg.base_interruptible_frac))

        u = cp.Variable(H)  # power fraction
        c = cp.Variable(H)  # continuous checkpoint effort

        energy_cost = cp.sum(cp.multiply(price, self.cfg.site_mw * dt_h * u))
        carbon_cost = self.cfg.carbon_price_usd_per_kg * cp.sum(
            cp.multiply(carbon, self.cfg.site_mw * dt_h * u)
        )
        shed_frac = 1 - u
        sla_cost = self.cfg.sla_penalty_usd * cp.sum_squares(shed_frac)

        du0 = u[0] - prev_u
        du = cp.hstack([du0, u[1:] - u[:-1]])
        ramp_cost = self.cfg.ramp_penalty_usd * cp.sum_squares(du)
        fatigue_proxy = self.cfg.fatigue_proxy_penalty_usd * cp.sum_squares(du)
        checkpoint_cost = self.cfg.checkpoint_linear_usd * cp.sum(c) + self.cfg.checkpoint_quadratic_usd * cp.sum_squares(c)

        constraints = [
            u >= self.cfg.min_power_frac,
            u <= 1.0,
            c >= 0.0,
            c <= 1.0,
            shed_frac <= interruptible_now + self.cfg.checkpoint_interruptible_gain * c,
        ]

        objective = cp.Minimize(energy_cost + carbon_cost + sla_cost + ramp_cost + fatigue_proxy + checkpoint_cost)
        problem = cp.Problem(objective, constraints)
        problem.solve(solver=getattr(cp, self.cfg.solver), warm_start=True, verbose=self.cfg.verbose)

        if u.value is None or c.value is None:
            raise RuntimeError("CVXPY solver returned no solution")
        return {
            "power_frac": float(np.clip(u.value[0], self.cfg.min_power_frac, 1.0)),
            "checkpoint_effort": float(np.clip(c.value[0], 0.0, 1.0)),
            "objective_usd": float(problem.value),
            "backend": "cvxpy-" + self.cfg.solver,
        }

    def _solve_scipy(self, state: Dict[str, Any], forecast: pd.DataFrame) -> Dict[str, float]:
        from scipy.optimize import minimize

        H = self.cfg.horizon_windows
        price, carbon = self._problem_arrays(state, forecast)
        dt_h = self.cfg.market_interval_s / 3600.0
        prev_u = float(state.get("power_frac", 1.0))
        interruptible_now = float(state.get("interruptible_frac", self.cfg.base_interruptible_frac))

        def unpack(z: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
            return z[:H], z[H:]

        def obj(z: np.ndarray) -> float:
            u, c = unpack(z)
            energy = np.sum(price * self.cfg.site_mw * dt_h * u)
            carbon_cost = self.cfg.carbon_price_usd_per_kg * np.sum(carbon * self.cfg.site_mw * dt_h * u)
            shed = 1 - u
            sla = self.cfg.sla_penalty_usd * np.sum(shed**2)
            du = np.r_[u[0] - prev_u, np.diff(u)]
            ramp = self.cfg.ramp_penalty_usd * np.sum(du**2)
            fatigue = self.cfg.fatigue_proxy_penalty_usd * np.sum(du**2)
            ckpt = self.cfg.checkpoint_linear_usd * np.sum(c) + self.cfg.checkpoint_quadratic_usd * np.sum(c**2)
            # Soft penalty for violating checkpoint-liquidity relaxation.
            violation = np.maximum(0.0, shed - (interruptible_now + self.cfg.checkpoint_interruptible_gain * c))
            liquidity_penalty = 1.0e5 * np.sum(violation**2)
            return float(energy + carbon_cost + sla + ramp + fatigue + ckpt + liquidity_penalty)

        x0 = np.r_[np.full(H, prev_u), np.zeros(H)]
        bounds = [(self.cfg.min_power_frac, 1.0)] * H + [(0.0, 1.0)] * H
        res = minimize(obj, x0, bounds=bounds, method="L-BFGS-B", options={"maxiter": 500})
        u, c = unpack(res.x)
        return {
            "power_frac": float(np.clip(u[0], self.cfg.min_power_frac, 1.0)),
            "checkpoint_effort": float(np.clip(c[0], 0.0, 1.0)),
            "objective_usd": float(res.fun),
            "backend": "scipy-LBFGSB",
        }
