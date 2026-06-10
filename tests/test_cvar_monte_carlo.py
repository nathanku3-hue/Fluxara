"""
Monte Carlo validation of delivery safety and CVaR tail risk.
Verifies that the chance-constrained solver guarantees P(delivered >= committed) >= 0.999
and bounds the worst-case tail shortfall (CVaR_99).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from fluxara_core.bidding import BidPolicy, BidPolicyConfig
from fluxara_core.env import FluxaraEnv, FluxaraEnvConfig
from fluxara_core.solver import FluxaraSolver, FluxaraSolverConfig


def test_monte_carlo_delivery_safety_and_cvar() -> None:
    # 1. Setup config and state
    env_cfg = FluxaraEnvConfig(n_market_steps=12, seed=42)
    # Expose z-score delivery confidence of 0.999, noise of 0.03
    solver_cfg = FluxaraSolverConfig(
        horizon_windows=12,
        risk_surface_noise=0.03,
        delivery_confidence=0.999,
        shortfall_cvar_alpha=0.99,
        rng_seed=42,
    )

    env = FluxaraEnv(config=env_cfg)
    solver = FluxaraSolver(config=solver_cfg)

    obs = env.reset()
    # Lock the interruptible capacity fraction at 0.40
    # and site capacity at 10.0 MW
    obs["interruptible_frac"] = 0.40
    obs["site_mw"] = 10.0

    forecast = env.forecast(solver_cfg.horizon_windows)

    # 2. Get deterministic solver setpoints
    det_action = solver.solve(obs, forecast)
    u_det = det_action["power_frac"]

    # 3. Run 10,000 Monte Carlo trials
    N_trials = 10000
    shortfalls = []
    successes = 0

    # We use a single BidPolicy but update its seed or let it roll naturally
    bid_policy = BidPolicy(BidPolicyConfig(power_noise_std=0.03, seed=123))

    for _ in range(N_trials):
        bid = bid_policy.generate_bid(det_action, obs)
        u_rand = bid["randomized_power_frac"]

        # Bid capacity in MW
        bid_mw = (1.0 - u_rand) * obs["site_mw"]

        # The grid clears the bid in full
        award_mw = bid_mw

        # Actual physical delivered capacity limit
        max_deliverable_mw = obs["interruptible_frac"] * obs["site_mw"]
        delivered_mw = min(award_mw, max_deliverable_mw)

        shortfall = max(0.0, award_mw - delivered_mw)
        shortfalls.append(shortfall)

        if shortfall < 1e-7:
            successes += 1

    # 4. Evaluate acceptance metrics
    delivery_success_rate = successes / N_trials
    
    # Calculate CVaR_99: expected value of the worst 1% of shortfalls
    sorted_shortfalls = sorted(shortfalls)
    tail_index = int(N_trials * 0.99)
    tail_shortfalls = sorted_shortfalls[tail_index:]
    cvar_99 = np.mean(tail_shortfalls)

    print(f"Monte Carlo Success Rate: {delivery_success_rate:.5f}")
    print(f"CVaR 99% Tail Shortfall: {cvar_99:.5f} MW")

    # Assert delivery success rate >= 99.9%
    assert delivery_success_rate >= 0.999, (
        f"Delivery success rate {delivery_success_rate:.5f} is below 99.9% requirement"
    )

    # Assert CVaR_99 is bounded (tolerance is 0.05 MW)
    assert cvar_99 <= 0.05, f"CVaR_99 shortfall {cvar_99:.5f} MW exceeds tolerance"
