"""
Unit tests for stochastic bidding policy, threshold adversary, and exploitability evaluator.
"""

from __future__ import annotations

from fluxara_core.bidding.adversary import AdversaryAgent
from fluxara_core.bidding.bid_policy import BidPolicy, BidPolicyConfig
from fluxara_core.bidding.exploitability import ExploitabilityEvaluator


def test_bid_policy_generation_and_safety_bounds() -> None:
    # Set high std dev to ensure values would exceed bounds without clipping
    cfg = BidPolicyConfig(power_noise_std=0.5, checkpoint_noise_std=0.5, seed=1)
    policy = BidPolicy(cfg)

    solver_action = {"power_frac": 1.0, "checkpoint_effort": 0.0, "backend": "test"}
    state = {"min_power_frac": 0.55}

    # Generate many bids and check safety limits
    for _ in range(50):
        bid = policy.generate_bid(solver_action, state)
        assert 0.55 <= bid["power_frac"] <= 1.0
        assert 0.0 <= bid["checkpoint_effort"] <= 1.0
        assert bid["power_frac_deterministic"] == 1.0
        assert bid["checkpoint_effort_deterministic"] == 0.0
        assert bid["backend"] == "test"


def test_adversary_agent_threshold_estimation() -> None:
    adversary = AdversaryAgent()

    # Simulate price-response observations where the true threshold is 50.0
    # If price >= 50.0, power is shed to 0.55. Otherwise, power is 1.0.
    for price in range(10, 100, 5):
        power_frac = 0.55 if price >= 50.0 else 1.0
        adversary.observe(float(price), power_frac)

    estimated = adversary.estimate_threshold()
    # Throttled prices: [50, 55, 60, ...] (min is 50)
    # Unthrottled prices: [10, 15, ..., 45] (max is 45)
    # Midpoint should be (45 + 50) / 2.0 = 47.5
    assert estimated == 47.5


def test_exploitability_evaluator() -> None:
    # 1. Deterministic case (100% predictable)
    history = [
        (10.0, 1.0),
        (20.0, 1.0),
        (30.0, 1.0),
        (60.0, 0.55),
        (70.0, 0.55),
        (80.0, 0.55),
    ]
    # Perfect estimated threshold
    estimated = 45.0
    score = ExploitabilityEvaluator.calculate_score(history, estimated)
    # All points classified correctly -> accuracy = 1.0 -> score = (1.0 - 0.5)/0.5 = 1.0
    assert score == 1.0

    # 2. Stochastic case (blurry threshold)
    # At price 40, some are throttled, some are not
    history_stoch = [
        (10.0, 1.0),
        (20.0, 1.0),
        (40.0, 1.0),
        (40.0, 0.55),  # overlapping
        (60.0, 0.55),
        (70.0, 0.55),
    ]
    estimated_stoch = 30.0
    score_stoch = ExploitabilityEvaluator.calculate_score(history_stoch, estimated_stoch)
    # With threshold = 30, prediction for 40 is throttled.
    # The actual observation (40.0, 1.0) is classified incorrectly (False).
    # Accuracy is 5/6 = 0.833. Score is (0.833 - 0.5) / 0.5 = 0.667
    assert score_stoch < 1.0
    assert score_stoch > 0.0
