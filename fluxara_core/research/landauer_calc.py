"""
landauer_calc.py

Landauer erasure cost calculator for Fluxara R8-3.
Computes theoretical lower bounds and practical silicon-overhead dissipation levels.
"""

from __future__ import annotations

import math


class LandauerCalculator:
    """Calculates theoretical and practical thermodynamic costs of bit erasures."""

    BOLTZMANN_CONSTANT = 1.380649e-23  # J/K

    @classmethod
    def compute_theoretical_erasure_heat(cls, erased_bits: float, temp_c: float) -> float:
        """Calculate the theoretical minimum energy dissipation (Joules) for bit erasures.

        Q_min = k_B * T * ln(2) * erased_bits
        """
        temp_k = temp_c + 273.15
        q_min_per_bit = cls.BOLTZMANN_CONSTANT * temp_k * math.log(2.0)
        return float(q_min_per_bit * erased_bits)

    @classmethod
    def compute_practical_erasure_heat(
        self,
        erased_bits: float,
        temp_c: float,
        chi_hardware: float = 1.0e5,
        memory_accesses: float = 0.0,
        energy_per_access_j: float = 1.0e-9,
    ) -> float:
        """Calculate the practical energy dissipation (Joules) incorporating silicon overhead.

        Q_actual = chi_hardware * Q_min + memory_accesses * energy_per_access_j
        """
        q_min = self.compute_theoretical_erasure_heat(erased_bits, temp_c)
        mem_energy = memory_accesses * energy_per_access_j
        return float(chi_hardware * q_min + mem_energy)

    @classmethod
    def is_caching_efficient(
        self,
        bits_to_cache: float,
        temp_c: float,
        chi_hardware: float = 1.0e5,
        memory_accesses: float = 2.0,  # 1 write + 1 read
        energy_per_access_j: float = 2.0e-9,  # e.g., 2 nJ per memory transaction
    ) -> bool:
        """Determine if caching ancilla bits is energy-efficient compared to immediate erasure.

        Efficient if: Caching Energy < Erasure Dissipation
        where Caching Energy = memory_accesses * energy_per_access_j
        and Erasure Dissipation = chi_hardware * Q_min
        """
        q_min = self.compute_theoretical_erasure_heat(bits_to_cache, temp_c)
        erasure_dissipation = chi_hardware * q_min
        caching_energy = memory_accesses * energy_per_access_j
        return caching_energy < erasure_dissipation
