"""
adversary.py

Threshold adversary agent for Fluxara R8-1.
Attempts to estimate or infer the data center's price-response threshold by
observing historical Locational Marginal Price (LMP) and power fraction setpoints.
"""

from __future__ import annotations


class AdversaryAgent:
    """Adversary probing agent trying to infer the response threshold of the system."""

    def __init__(self) -> None:
        self.history: list[tuple[float, float]] = []

    def observe(self, lmp: float, power_frac: float) -> None:
        """Record a single market price and power cap fraction observation."""
        self.history.append((lmp, power_frac))

    def estimate_threshold(self) -> float | None:
        """Estimate the price threshold above which the system sheds load.

        Uses the midpoint between the maximum unthrottled price and the minimum
        throttled price in historical observations.
        """
        if not self.history:
            return None

        # u < 0.99 is considered throttled load shedding
        throttled_prices = [p for p, u in self.history if u < 0.99]
        unthrottled_prices = [p for p, u in self.history if u >= 0.99]

        if not throttled_prices:
            return None

        if not unthrottled_prices:
            return min(throttled_prices)

        max_unthrottled = max(unthrottled_prices)
        min_throttled = min(throttled_prices)

        # In a deterministic policy, the threshold lies between these two
        return (max_unthrottled + min_throttled) / 2.0
