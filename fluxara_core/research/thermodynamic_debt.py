"""
thermodynamic_debt.py

Thermodynamic debt state tracker for Fluxara R8-3.
Tracks ancilla bits accumulated, memory utilization, and active bit erasures.
"""

from __future__ import annotations


class ThermodynamicDebt:
    """Tracks the thermodynamic debt (ancilla bits) and memory overhead of reversible computing."""

    def __init__(
        self,
        initial_ancilla_bits: float = 0.0,
        ancilla_bits_per_op: float = 1.0e6,  # 1 million bits per typical model operation
        leakage_erasure_rate: float = 0.001,  # 0.1% passive decay/erasure per second
        bits_per_mb: float = 8.0e6,           # 8 million bits in 1 MB
    ) -> None:
        self.ancilla_bits = float(initial_ancilla_bits)
        self.ancilla_bits_per_op = float(ancilla_bits_per_op)
        self.leakage_erasure_rate = float(leakage_erasure_rate)
        self.bits_per_mb = float(bits_per_mb)
        self.memory_mb = self.ancilla_bits / self.bits_per_mb

    def step(self, num_ops: float, active_erasure_rate_per_s: float, dt_s: float = 300.0) -> float:
        """Advance the simulation window by dt_s seconds.

        Returns the total number of bits erased (active + passive leakage) during this step.
        """
        old_bits = self.ancilla_bits
        
        # Bits generated
        generated_bits = num_ops * self.ancilla_bits_per_op
        
        # Passive leakage erasure
        passive_erased = old_bits * self.leakage_erasure_rate * dt_s
        
        # Active erasure
        active_erased = active_erasure_rate_per_s * dt_s
        
        # New state before clipping
        new_bits = old_bits + generated_bits - active_erased - passive_erased
        
        # Clip state to non-negative
        self.ancilla_bits = max(0.0, new_bits)
        
        # Total bits erased in conservation
        total_erased = old_bits + generated_bits - self.ancilla_bits
        
        # Update memory footprint
        self.memory_mb = self.ancilla_bits / self.bits_per_mb
        
        return float(total_erased)
