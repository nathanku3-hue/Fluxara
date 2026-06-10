"""
test_landauer_toy.py

Unit tests for R8-3 thermodynamic debt tracking, Landauer calculators, and research falsification gates.
"""

from __future__ import annotations

import math
from fluxara_core.research import ThermodynamicDebt, LandauerCalculator


def test_thermodynamic_debt_caching_dynamics() -> None:
    # 1. Initialize tracker: 0 initial bits, 1M bits per op, 0.1% leakage per second
    tracker = ThermodynamicDebt(
        initial_ancilla_bits=0.0,
        ancilla_bits_per_op=1.0e6,
        leakage_erasure_rate=0.001,
        bits_per_mb=8.0e6,
    )
    
    # 2. Run one step: 5 operations, 0 active erasure, dt = 100 seconds
    # generated = 5 * 1e6 = 5,000,000 bits.
    # old_bits = 0, passive_erased = 0, active_erased = 0.
    # final_bits should be 5,000,000.
    erased = tracker.step(num_ops=5.0, active_erasure_rate_per_s=0.0, dt_s=100.0)
    assert tracker.ancilla_bits == 5.0e6
    assert tracker.memory_mb == 5.0e6 / 8.0e6  # 0.625 MB
    assert erased == 0.0

    # 3. Run second step: 0 operations, 10,000 bits/sec active erasure, dt = 100 seconds
    # generated = 0.
    # old_bits = 5,000,000.
    # passive_erased = 5,000,000 * 0.001 * 100 = 500,000 bits.
    # active_erased = 10,000 * 100 = 1,000,000 bits.
    # new_bits = 5,000,000 - 500,000 - 1,000,000 = 3,500,000.
    erased2 = tracker.step(num_ops=0.0, active_erasure_rate_per_s=10000.0, dt_s=100.0)
    assert tracker.ancilla_bits == 3.5e6
    assert erased2 == 1.5e6  # 1.5M bits erased total


def test_landauer_calculator_physical_limits() -> None:
    # 1. Compute theoretical limit at room temperature (25C -> 298.15K)
    # k_B = 1.380649e-23
    # ln(2) = 0.69314718
    # q_min_per_bit = 1.380649e-23 * 298.15 * ln(2) approx 2.8545e-21 Joules
    q_theory = LandauerCalculator.compute_theoretical_erasure_heat(1e12, temp_c=25.0)
    expected_q_per_bit = 1.380649e-23 * 298.15 * math.log(2.0)
    assert math.isclose(q_theory, expected_q_per_bit * 1e12, rel_tol=1e-5)

    # 2. Compute practical erasure heat incorporating high silicon overhead (chi = 1e5)
    # Q_actual = 1e5 * Q_theory + 0
    q_practical = LandauerCalculator.compute_practical_erasure_heat(1e12, temp_c=25.0, chi_hardware=1.0e5)
    assert math.isclose(q_practical, 1.0e5 * q_theory, rel_tol=1e-5)


def test_research_falsification_criteria() -> None:
    # Falsification Gate 1: Caching is inefficient if the memory access overhead
    # exceeds the thermodynamic cooling savings.
    # Case A: High memory energy (e.g. 50 nJ total) vs tiny theoretical cooling savings (e.g. 1e10 bits at room temp)
    # q_min_per_bit approx 2.85e-21 J. For 1e10 bits, Q_theory approx 2.85e-11 J.
    # Even with chi = 100, erasure dissipation = 2.85e-9 J = 2.85 nJ.
    # Memory access energy = 2 * 25 nJ = 50 nJ.
    # Caching energy (50 nJ) > erasure dissipation (2.85 nJ) -> Caching is inefficient!
    is_efficient_a = LandauerCalculator.is_caching_efficient(
        bits_to_cache=1.0e10,
        temp_c=25.0,
        chi_hardware=100.0,
        memory_accesses=2.0,
        energy_per_access_j=25.0e-9,  # high memory access cost
    )
    assert is_efficient_a is False

    # Case B: Caching is efficient if erasure dissipation is high (large chi and bit count)
    # and memory access energy is extremely low (e.g., 1 pJ)
    is_efficient_b = LandauerCalculator.is_caching_efficient(
        bits_to_cache=1.0e12,
        temp_c=25.0,
        chi_hardware=1.0e6,  # huge silicon overhead makes erasure very expensive
        memory_accesses=2.0,
        energy_per_access_j=1.0e-12,  # extremely efficient near-compute memory
    )
    assert is_efficient_b is True

    # Falsification Gate 2: Silicon overhead (chi) must be large on standard CMOS logic.
    # Asserts that standard CMOS gate switching energy (typically ~10 fJ = 1e-14 J)
    # is at least 1,000 times larger than the single-bit Landauer limit (~3e-21 J).
    single_bit_landauer = LandauerCalculator.compute_theoretical_erasure_heat(1.0, temp_c=75.0)
    cmos_switching_energy = 1.0e-14  # 10 fJ
    implied_chi = cmos_switching_energy / single_bit_landauer
    assert implied_chi >= 1.0e5
