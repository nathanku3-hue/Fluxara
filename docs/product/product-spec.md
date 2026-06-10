# Technical Product Specification - Fluxara Core

This document outlines the detailed API interfaces, configuration parameters, and data schemas for Fluxara Core.

---

## 1. Configurations

### A. FluxaraEnvConfig (`fluxara_core.env`)
Defines the physical simulation parameters.

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `dt_s` | `int` | `1` | Physical simulation clock tick in seconds. |
| `market_interval_s` | `int` | `300` | Grid market bidding window in seconds (5 minutes). |
| `n_market_steps` | `int` | `288` | Number of market intervals in a run (288 = 24 hours). |
| `site_mw` | `float` | `10.0` | Total peak grid interconnection capacity of the site in MW. |
| `min_power_frac` | `float` | `0.55` | Minimum allowable GPU power cap fraction (safety boundary). |
| `initial_power_frac` | `float` | `1.0` | Initial power fraction setpoint. |
| `representative_gpu_tdp_w` | `float` | `700.0` | Thermal Design Power of the representative accelerator (e.g. H100). |
| `ambient_c` | `float` | `25.0` | Data center ambient temperature in °C. |
| `thermal_r_c_per_w` | `float` | `0.075` | Equivalent thermal resistance of junction-to-ambient in °C/W. |
| `thermal_tau_s` | `float` | `45.0` | Thermal time constant of the chip package in seconds. |
| `initial_tj_c` | `float` | `65.0` | Initial junction temperature in °C. |
| `fatigue_C` | `float` | `1.0e12` | Coffin-Manson empirical fatigue constant. |
| `fatigue_exp` | `float` | `5.0` | Coffin-Manson fatigue exponent (nonlinear fatigue slope). |
| `damage_cost_per_fraction` | `float` | `3.0e8` | Virtual economic penalty if chip damage reaches 1.0 (fails). |
| `min_counted_delta_t_c` | `float` | `0.5` | Minimum thermal shift to count as a thermal fatigue cycle in °C. |
| `dwell_enabled` | `bool` | `True` | Toggle for elevated-temperature thermal creep/dwell logging. |
| `dwell_threshold_c` | `float` | `75.0` | Temperature threshold above which creep damage begins to accumulate. |
| `dwell_coeff_per_s` | `float` | `2.0e-12` | Creep damage coefficient. |
| `checkpoint_age_s0` | `float` | `1800.0` | Initial age of checkpoint data in seconds. |
| `checkpoint_refresh_rate_per_s`| `float` | `1.0 / 300.0` | Maximum possible checkpoint creation rate. |
| `base_interruptible_frac` | `float` | `0.10` | Minimum fraction of compute load that is interruptible by default. |
| `checkpoint_interruptible_gain`| `float` | `0.75` | Scaling factor linking checkpoint freshness to interruptibility. |
| `seed` | `int` | `7` | Random seed for synthetic LMP and carbon signal generation. |

### B. FluxaraSolverConfig (`fluxara_core.solver`)
Defines the convex MPC optimizer objectives and constraints.

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `horizon_windows` | `int` | `12` | MPC lookahead horizon (12 steps of 5 min = 1 hour). |
| `market_interval_s` | `int` | `300` | Market step interval in seconds. |
| `min_power_frac` | `float` | `0.55` | Minimum power fraction constraint. |
| `site_mw` | `float` | `10.0` | Total peak site capacity in MW. |
| `carbon_price_usd_per_kg` | `float` | `0.0` | Virtual carbon tax weight in $/kg. |
| `sla_penalty_usd` | `float` | `1200.0` | Quadratic penalty weight for SLA delay/load shedding. |
| `ramp_penalty_usd` | `float` | `250.0` | Penalty weight for scheduling abrupt power swings. |
| `fatigue_proxy_penalty_usd` | `float` | `600.0` | Convex quadratic proxy for microbump fatigue damage. |
| `checkpoint_linear_usd` | `float` | `30.0` | Linear cost weight for trigger checkpoint efforts. |
| `checkpoint_quadratic_usd` | `float` | `800.0` | Quadratic penalty weight representing network checkpoint storm congestion. |
| `base_interruptible_frac` | `float` | `0.10` | Base interruptible fraction. |
| `checkpoint_interruptible_gain`| `float` | `0.75` | Checkpoint freshness gain. |
| `solver` | `str` | `"OSQP"` | Underlying CVXPY solver backend (`OSQP`, `CLARABEL`, etc.). |
| `verbose` | `bool` | `False` | Toggle solver log verbosity. |

---

## 2. API Specifications

### A. class `FluxaraEnv`
The simulation environment model.

- **`__init__(self, lmp_df=None, gpu_trace_df=None, config=None)`**
  Initializes the simulation environment. Ingests CAISO prices and GPU trace data frames.
- **`reset(self) -> Dict[str, Any]`**
  Resets the physical state (temperatures, damage index, clocks) and returns the initial telemetry observation.
- **`observe(self) -> Dict[str, Any]`**
  Returns a dictionary of current environment telemetry states.
- **`forecast(self, horizon: int) -> pd.DataFrame`**
  Returns a DataFrame containing grid LMP and carbon forecasts for the lookahead horizon.
- **`step_market(self, action: Dict[str, float]) -> Dict[str, Any]`**
  Executes one market step (5 minutes), running 300 physical 1-second ticks under the specified action caps.
- **`done(self) -> bool`**
  Returns `True` if the simulation run has completed.
- **`history_frame(self) -> pd.DataFrame`**
  Exports the full physical history log of the simulation.

### B. class `FluxaraSolver`
The convex MPC controller.

- **`__init__(self, config=None)`**
  Initializes the solver config.
- **`solve(self, state: Dict[str, Any], forecast_df: pd.DataFrame) -> Dict[str, float]`**
  Resolves the optimization problem using CVXPY + OSQP (or falls back to SciPy L-BFGS-B if CVXPY is not installed). Returns the action dictionary:
  ```python
  {
      "power_frac": float,          # Optimal power cap fraction for the next step [min_power_frac, 1.0]
      "checkpoint_effort": float,   # Optimal checkpoint effort [0.0, 1.0]
      "objective_usd": float,       # Evaluated objective cost
      "backend": str                # Execution solver backend used
  }
  ```

---

## 3. Data Schemas

### A. Grid Data Frame (`lmp_df`)
Contains grid market prices.

| Column | Type | Description |
| :--- | :--- | :--- |
| `lmp_usd_per_mwh` | `float` | Locational Marginal Price of energy ($/MWh). |
| `carbon_kg_per_mwh` | `float` | Grid carbon intensity (kg CO2e/MWh). |

### B. History Frame (`history_frame()`)
Exported DataFrame logging 1-second physical updates.

| Column | Type | Description |
| :--- | :--- | :--- |
| `t_s` | `int` | Elapsed physical seconds. |
| `market_idx` | `int` | Grid market step index. |
| `power_frac` | `float` | Current power cap setpoint. |
| `tj_c` | `float` | Chip junction temperature in °C. |
| `damage_fraction` | `float` | Cumulative lifetime damage fraction. |
| `checkpoint_age_s` | `float` | Checkpoint age in seconds. |
| `lmp_usd_per_mwh` | `float` | Current grid LMP. |
