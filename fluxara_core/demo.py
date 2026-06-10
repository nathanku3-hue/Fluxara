"""Minimal Fluxara v0.1 demo."""

from fluxara_core.env import FluxaraEnv, FluxaraEnvConfig
from fluxara_core.solver import FluxaraSolver, FluxaraSolverConfig


def main() -> None:
    env = FluxaraEnv(config=FluxaraEnvConfig(n_market_steps=48))  # 4 hours
    solver = FluxaraSolver(FluxaraSolverConfig(horizon_windows=12))

    obs = env.observe()
    while not env.done():
        forecast = env.forecast(solver.cfg.horizon_windows)
        action = solver.solve(obs, forecast)
        obs = env.step_market(action)
        print(
            f"k={obs['market_idx']:03d} "
            f"LMP=${obs['lmp_usd_per_mwh']:7.2f}/MWh "
            f"u={obs['power_frac']:.3f} "
            f"ckpt={action['checkpoint_effort']:.3f} "
            f"Tj={obs['tj_c']:.2f}C "
            f"D={obs['damage_fraction']:.3e} "
            f"backend={action['backend']}"
        )

    env.history_frame().to_csv("fluxara_history.csv", index=False)
    print("wrote fluxara_history.csv")


if __name__ == "__main__":
    main()
