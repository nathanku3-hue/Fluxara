"""
Adversarial benchmark testing for R8-1.
Compares a deterministic policy against a randomized policy, verifying that
stochastic bidding reduces exploitability by at least 25% while maintaining
at least 95% of expected profit, and keeping delivery success rate >= 99.9%.
"""

from __future__ import annotations

import pandas as pd
from fluxara_core.bidding import AdversaryAgent, BidPolicy, BidPolicyConfig, ExploitabilityEvaluator
from fluxara_core.env import FluxaraEnv, FluxaraEnvConfig
from fluxara_core.solver import FluxaraSolver, FluxaraSolverConfig


def run_market_loop(use_stochastic: bool) -> tuple[float, float, float]:
    env_cfg = FluxaraEnvConfig(n_market_steps=48, seed=42)
    # Using chance constraint in solver
    solver_cfg = FluxaraSolverConfig(horizon_windows=12, rng_seed=42, risk_surface_noise=0.03)

    env = FluxaraEnv(config=env_cfg)
    solver = FluxaraSolver(config=solver_cfg)
    
    # Configure noise std: 0.0 if deterministic, 0.05 if stochastic
    noise_std = 0.05 if use_stochastic else 0.0
    price_std = 8.0 if use_stochastic else 0.0
    bid_policy = BidPolicy(BidPolicyConfig(
        power_noise_std=noise_std,
        checkpoint_noise_std=noise_std,
        price_noise_std=price_std,
        seed=42
    ))
    adversary = AdversaryAgent()

    obs = env.reset()
    dt_h = env_cfg.market_interval_s / 3600.0

    total_profit = 0.0
    trials = 0
    successes = 0

    while not env.done():
        forecast = env.forecast(solver.cfg.horizon_windows)
        det_action = solver.solve(obs, forecast)

        # Generate bid action (deterministic or stochastically randomized)
        bid = bid_policy.generate_bid(det_action, obs)

        # Clear bid
        current_lmp = obs["lmp_usd_per_mwh"]
        cleared = current_lmp >= bid["bid_price_usd_per_mwh"]
        award_mw = bid["bid_mw"] if cleared else 0.0

        # Physical delivery commitment
        site_mw = obs["site_mw"]
        max_deliverable_mw = obs["interruptible_frac"] * site_mw
        delivered_mw = min(award_mw, max_deliverable_mw)
        delivery_shortfall_mw = max(0.0, award_mw - delivered_mw)

        physical_power_frac = 1.0 - (delivered_mw / site_mw)
        physical_power_frac = max(env_cfg.min_power_frac, min(1.0, physical_power_frac))

        # Check delivery success
        trials += 1
        if delivery_shortfall_mw < 1e-7:
            successes += 1

        # Profit calculation
        energy_revenue = current_lmp * delivered_mw * dt_h
        sla_penalty = solver_cfg.sla_penalty_usd * (delivery_shortfall_mw / site_mw) ** 2
        market_profit_usd = energy_revenue - sla_penalty
        total_profit += market_profit_usd

        # Adversary observations
        adversary.observe(current_lmp, physical_power_frac)

        # Execute env step
        action_dict = {
            "power_frac": physical_power_frac,
            "checkpoint_effort": bid["checkpoint_effort"],
        }
        obs = env.step_market(action_dict)

    # Estimate exploitability
    est_thresh = adversary.estimate_threshold()
    exploitability = ExploitabilityEvaluator.calculate_score(adversary.history, est_thresh)
    delivery_success_rate = successes / trials

    return exploitability, total_profit, delivery_success_rate


def test_adversarial_bidding_benchmark() -> None:
    # 1. Evaluate deterministic baseline
    exp_det, profit_det, success_det = run_market_loop(use_stochastic=False)
    
    # 2. Evaluate stochastic bidding policy
    exp_rand, profit_rand, success_rand = run_market_loop(use_stochastic=True)

    print(f"Deterministic Policy: Exploitability={exp_det:.3f}, Profit=${profit_det:.2f}, Success={success_det:.3f}")
    print(f"Randomized Policy:    Exploitability={exp_rand:.3f}, Profit=${profit_rand:.2f}, Success={success_rand:.3f}")

    # Exploitability reduction gate: exploitability(randomized) <= 0.75 * exploitability(deterministic)
    # Since deterministic is highly predictable (1.0), randomized should be <= 0.75
    assert exp_rand <= 0.75 * exp_det, (
        f"Stochastic policy exploitability {exp_rand:.3f} is not 25% lower than deterministic {exp_det:.3f}"
    )

    # Expected profit gate: profit(randomized) >= 0.95 * profit(deterministic)
    # The randomized policy must not excessively sacrifice profit (should retain >= 95% of det baseline)
    assert profit_rand >= 0.95 * profit_det, (
        f"Stochastic policy profit ${profit_rand:.2f} is below 95% of deterministic profit ${profit_det:.2f}"
    )

    # Delivery success rate gate: success_rate >= 0.999 (should be 100% since solver handles chance constraints)
    assert success_rand >= 0.999, (
        f"Stochastic policy delivery success rate {success_rand:.3f} is below 99.9% requirement"
    )
