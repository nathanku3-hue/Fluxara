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
    seed: int = 42


class BidPolicy:
    """Stochastic bidding policy wrapper."""

    def __init__(self, config: BidPolicyConfig | None = None) -> None:
        self.cfg = config or BidPolicyConfig()
        self.rng = np.random.default_rng(self.cfg.seed)

    def generate_bid(self, solver_action: dict[str, float], state: dict[str, any]) -> dict[str, float]:
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

        return {
            "power_frac": u_rand,
            "checkpoint_effort": c_rand,
            "power_frac_deterministic": u_det,
            "checkpoint_effort_deterministic": c_det,
            "backend": solver_action.get("backend", "unknown"),
        }
