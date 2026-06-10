"""
Unit tests for FluxaraSolver.
"""

from __future__ import annotations

import pandas as pd
import pytest
from fluxara_core.solver import FluxaraSolver, FluxaraSolverConfig


def test_solver_config_defaults() -> None:
    cfg = FluxaraSolverConfig()
    assert cfg.horizon_windows == 12
    assert cfg.min_power_frac == 0.55
    assert cfg.site_mw == 10.0


def test_solver_execution_scipy() -> None:
    # Explicitly test SciPy fallback solver path
    solver = FluxaraSolver()
    state = {
        "power_frac": 1.0,
        "interruptible_frac": 0.10,
    }
    forecast_df = pd.DataFrame(
        {
            "lmp_usd_per_mwh": [40.0] * 12,
            "carbon_kg_per_mwh": [200.0] * 12,
        }
    )

    action = solver._solve_scipy(state, forecast_df)
    assert "power_frac" in action
    assert "checkpoint_effort" in action
    assert "objective_usd" in action
    assert action["backend"] == "scipy-LBFGSB"

    assert solver.cfg.min_power_frac <= action["power_frac"] <= 1.0
    assert 0.0 <= action["checkpoint_effort"] <= 1.0


def test_solver_solve_wrapper() -> None:
    # Resolves using CVXPY + OSQP or SciPy fallback automatically.
    solver = FluxaraSolver()
    state = {
        "power_frac": 0.8,
        "interruptible_frac": 0.20,
    }
    forecast_df = pd.DataFrame(
        {
            "lmp_usd_per_mwh": [30.0] * 12,
            "carbon_kg_per_mwh": [100.0] * 12,
        }
    )

    action = solver.solve(state, forecast_df)
    assert "power_frac" in action
    assert "checkpoint_effort" in action
    assert "backend" in action
    assert action["power_frac"] >= solver.cfg.min_power_frac
    assert action["power_frac"] <= 1.0
    assert action["checkpoint_effort"] >= 0.0
    assert action["checkpoint_effort"] <= 1.0
