"""
bid_policy.py

Stochastic bidding policy for Fluxara R8-1.
Wraps deterministic solver actions with private randomized noise to prevent strategic
adversary price-probing while maintaining physical safety bounds.
"""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass
class BidPolicyConfig:
    power_noise_std: float = 0.03
    checkpoint_noise_std: float = 0.05
    price_noise_std: float = 5.0
    seed: int = 42


class BidPolicy:
    """Stochastic bidding policy wrapper."""

    def __init__(self, config: BidPolicyConfig | None = None) -> None:
        self.cfg = config or BidPolicyConfig()
        self.rng = np.random.default_rng(self.cfg.seed)

    def generate_bid(self, solver_action: dict[str, float], state: dict[str, any]) -> dict[str, any]:
        """Apply noise to deterministic solver actions and enforce physical boundaries."""
        u_det = solver_action["power_frac"]
        c_det = solver_action["checkpoint_effort"]

        # Sample private randomized noise
        u_noise = self.rng.normal(0, self.cfg.power_noise_std)
        c_noise = self.rng.normal(0, self.cfg.checkpoint_noise_std)

        u_rand = u_det + u_noise
        c_rand = c_det + c_noise

        # Enforce safety constraints
        min_p = state.get("min_power_frac", 0.55)
        u_rand = float(np.clip(u_rand, min_p, 1.0))
        c_rand = float(np.clip(c_rand, 0.0, 1.0))

        site_mw = state.get("site_mw", 10.0)
        bid_mw = (1.0 - u_rand) * site_mw

        # Generate stochastic bidding price (base threshold 50.0 + noise)
        base_threshold = 50.0
        price_noise = self.rng.normal(0, self.cfg.price_noise_std) if self.cfg.price_noise_std > 0 else 0.0
        bid_price = base_threshold + price_noise

        return {
            "power_frac": u_rand,
            "checkpoint_effort": c_rand,
            "bid_mw": float(bid_mw),
            "bid_price_usd_per_mwh": float(bid_price),
            "response_duration_s": 300,
            "confidence_level": 0.999,
            "rebound_limit_mw": 1.5,
            "private_entropy_id": f"entropy-{self.rng.integers(1000, 9999)}",
            "deterministic_power_frac": float(u_det),
            "power_frac_deterministic": float(u_det),
            "checkpoint_effort_deterministic": float(c_det),
            "randomized_power_frac": float(u_rand),
            "backend": solver_action.get("backend", "unknown"),
        }
