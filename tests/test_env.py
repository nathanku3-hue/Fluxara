"""
Unit tests for FluxaraEnv.
"""

from __future__ import annotations

import pandas as pd
import pytest
from fluxara_core.env import FluxaraEnv, FluxaraEnvConfig


def test_env_config_defaults() -> None:
    cfg = FluxaraEnvConfig()
    assert cfg.dt_s == 1
    assert cfg.market_interval_s == 300
    assert cfg.min_power_frac == 0.55
    assert cfg.representative_gpu_tdp_w == 700.0


def test_env_initialization_and_reset() -> None:
    env = FluxaraEnv()
    obs = env.reset()

    assert obs["t_s"] == 0
    assert obs["market_idx"] == 0
    assert obs["power_frac"] == 1.0
    assert obs["tj_c"] == 65.0
    assert obs["damage_fraction"] == 0.0
    assert "lmp_usd_per_mwh" in obs
    assert "carbon_kg_per_mwh" in obs


def test_env_observation_schema() -> None:
    env = FluxaraEnv()
    obs = env.observe()

    required_keys = {
        "t_s",
        "market_idx",
        "power_frac",
        "prev_power_frac",
        "site_mw",
        "min_power_frac",
        "tj_c",
        "damage_fraction",
        "checkpoint_age_s",
        "interruptible_frac",
        "interruptible_mw",
        "lmp_usd_per_mwh",
        "carbon_kg_per_mwh",
    }
    assert required_keys.issubset(obs.keys())


def test_env_forecast() -> None:
    env = FluxaraEnv()
    forecast = env.forecast(12)
    assert len(forecast) == 12
    assert "lmp_usd_per_mwh" in forecast.columns
    assert "carbon_kg_per_mwh" in forecast.columns


def test_env_step_market() -> None:
    env = FluxaraEnv(config=FluxaraEnvConfig(n_market_steps=10))
    env.reset()

    # Step with full power
    action = {"power_frac": 1.0, "checkpoint_effort": 0.0}
    obs = env.step_market(action)

    assert obs["market_idx"] == 1
    assert obs["t_s"] == 300
    # Tj should converge towards steady-state (25 + 0.075 * 700 * 1.0 = 77.5C)
    assert obs["tj_c"] > 65.0
    assert obs["tj_c"] < 77.5


def test_env_done() -> None:
    env = FluxaraEnv(config=FluxaraEnvConfig(n_market_steps=2))
    env.reset()
    assert not env.done()

    env.step_market({"power_frac": 1.0, "checkpoint_effort": 0.0})
    assert not env.done()

    env.step_market({"power_frac": 1.0, "checkpoint_effort": 0.0})
    assert env.done()

    with pytest.raises(RuntimeError):
        env.step_market({"power_frac": 1.0, "checkpoint_effort": 0.0})


def test_custom_lmp_df() -> None:
    lmp_data = pd.DataFrame(
        {
            "lmp_usd_per_mwh": [10.0, 20.0, 30.0],
            "carbon_kg_per_mwh": [100.0, 150.0, 200.0],
        }
    )
    env = FluxaraEnv(lmp_df=lmp_data, config=FluxaraEnvConfig(n_market_steps=3))
    obs = env.observe()
    assert obs["lmp_usd_per_mwh"] == 10.0
    assert obs["carbon_kg_per_mwh"] == 100.0

    obs = env.step_market({"power_frac": 1.0, "checkpoint_effort": 0.0})
    assert obs["lmp_usd_per_mwh"] == 20.0
