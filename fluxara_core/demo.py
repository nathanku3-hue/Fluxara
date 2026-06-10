"""
demo.py

Integrated Fluxara simulation demo showing R8-1 stochastic bidding,
adversary price-response learning, and safety-constrained delivery.
"""

from __future__ import annotations

import os
from fluxara_core.env import FluxaraEnv, FluxaraEnvConfig
from fluxara_core.solver import FluxaraSolver, FluxaraSolverConfig
from fluxara_core.bidding import BidPolicy, AdversaryAgent, ExploitabilityEvaluator


def main() -> None:
    # Setup configs
    env_cfg = FluxaraEnvConfig(n_market_steps=48, seed=42)
    solver_cfg = FluxaraSolverConfig(horizon_windows=12, rng_seed=42)

    env = FluxaraEnv(config=env_cfg)
    solver = FluxaraSolver(config=solver_cfg)
    bid_policy = BidPolicy()
    adversary = AdversaryAgent()

    obs = env.reset()
    dt_h = env_cfg.market_interval_s / 3600.0

    print("Starting integrated Fluxara simulation...")
    while not env.done():
        forecast = env.forecast(solver.cfg.horizon_windows)
        
        # 1. Deterministic solver recommendation
        det_action = solver.solve(obs, forecast)

        # 2. Stochastic bidding policy wraps deterministic setpoint
        bid = bid_policy.generate_bid(det_action, obs)

        # 3. Clear bid against simulated grid market LMP
        current_lmp = obs["lmp_usd_per_mwh"]
        cleared = current_lmp >= bid["bid_price_usd_per_mwh"]
        award_mw = bid["bid_mw"] if cleared else 0.0

        # 4. Commit physical delivery action, checking physical capacity bounds
        site_mw = obs["site_mw"]
        max_deliverable_mw = obs["interruptible_frac"] * site_mw
        delivered_mw = min(award_mw, max_deliverable_mw)
        delivery_shortfall_mw = max(0.0, award_mw - delivered_mw)

        # Apply physical cap based on actual capacity limit to ensure safety
        physical_power_frac = 1.0 - (delivered_mw / site_mw)
        physical_power_frac = max(env_cfg.min_power_frac, min(1.0, physical_power_frac))

        # Calculate economic profit/loss including SLA penalty for shortfall
        energy_revenue = current_lmp * delivered_mw * dt_h
        sla_penalty = solver_cfg.sla_penalty_usd * (delivery_shortfall_mw / site_mw) ** 2
        market_profit_usd = energy_revenue - sla_penalty

        # 5. Probing adversary observes price-response and tries to learn
        adversary.observe(current_lmp, physical_power_frac)
        estimated_threshold = adversary.estimate_threshold()

        # Calculate exploitability score
        exploitability_score = ExploitabilityEvaluator.calculate_score(
            adversary.history, estimated_threshold
        )
        
        if estimated_threshold is not None:
            adversary_prediction_error = abs(estimated_threshold - 50.0)
        else:
            adversary_prediction_error = 0.0

        # 6. Execute step in the physical environment
        physical_action = {
            "power_frac": physical_power_frac,
            "checkpoint_effort": bid["checkpoint_effort"],
            # Logging fields
            "deterministic_power_frac": bid["deterministic_power_frac"],
            "randomized_power_frac": bid["randomized_power_frac"],
            "bid_mw": bid["bid_mw"],
            "bid_price_usd_per_mwh": bid["bid_price_usd_per_mwh"],
            "award_mw": award_mw,
            "delivered_mw": delivered_mw,
            "delivery_shortfall_mw": delivery_shortfall_mw,
            "market_profit_usd": market_profit_usd,
            "exploitability_score": exploitability_score,
            "adversary_prediction_error": adversary_prediction_error,
            "backend": det_action["backend"],
            "rng_seed": solver_cfg.rng_seed,
            "timestamp": obs["t_s"],
        }

        obs = env.step_market(physical_action)

        print(
            f"k={obs['market_idx']:03d} "
            f"LMP=${current_lmp:7.2f}/MWh "
            f"u_det={bid['deterministic_power_frac']:.3f} "
            f"u_rand={bid['randomized_power_frac']:.3f} "
            f"bid_mw={bid['bid_mw']:.2f} "
            f"award_mw={award_mw:4.2f} "
            f"shortfall_mw={delivery_shortfall_mw:4.2f} "
            f"profit=${market_profit_usd:7.2f} "
            f"exploitability={exploitability_score:.3f}"
        )

    env.history_frame().to_csv("fluxara_history.csv", index=False)
    print("wrote fluxara_history.csv")


if __name__ == "__main__":
    main()
