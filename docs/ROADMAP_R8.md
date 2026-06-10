# Fluxara Round 8 Roadmap: Day-2 Existential Threats

This roadmap is designed for the first post-MVP release after the baseline `env.py` / `solver.py` loop is running.

## Executive decision

Round 8 should be split into three tracks:

1. **R8-1 Adversarial LMP Exploitation** — immediate v0.2 security/economics track.
2. **R8-2 Aging-Aware Sub-graph Routing** — v0.3 hardware-health / compiler-scheduling track.
3. **R8-3 Landauer Arbitrage** — long-horizon research track, not a production v0.2 dependency.

The production thesis is:

> Fluxara should not merely optimize against prices. It must make its bid surface non-exploitable, route sensitive math away from degraded hardware, and avoid promising thermodynamic primitives that do not exist on deployed GPUs.

---

## R8-1: Adversarial LMP Exploitation

### Threat model

The deterministic MVP has a threshold-like behavior:

```text
accept bid if grid_revenue > risk_cost
```

If the threshold can be inferred, a strategic counterparty can attempt induced load shedding or market games around Fluxara’s predictable response. The exact mechanism will differ by market design, but the system-level weakness is real: a deterministic, large, price-responsive load becomes a predictable market object.

### Design goal

Introduce a **stochastic bidding policy** while keeping physical delivery auditable.

Important distinction:

```text
Randomize the bid surface.
Do not randomize contractual physical delivery after a bid clears.
```

### Mathematical boundary

Let the controller sample a bid action:

```text
a_t ~ pi_theta(a | s_t)
```

where `a_t` may include:

```text
bid_mw
bid_price
response_duration
confidence_level
rebound_limit
```

But once a market award is accepted, physical delivery must satisfy:

```text
P(delivered_MW >= committed_MW | s_t) >= 0.999
```

A usable v0.2 objective:

```text
maximize  E[market_profit]
        - lambda_1 * CVaR_99(delivery_shortfall)
        - lambda_2 * exploitability_score(pi_theta)
        - lambda_3 * information_leakage(pi_theta)
```

### MVP implementation boundary

Do not implement a full Markov Perfect Equilibrium solver in v0.2. Instead, implement:

1. A randomized bid policy with private entropy.
2. A simple adversary agent that estimates Fluxara thresholds.
3. An exploitability benchmark.
4. A delivery quantile constraint.

Suggested modules:

```text
fluxara_core/bidding/bid_policy.py
fluxara_core/bidding/adversary.py
fluxara_core/bidding/exploitability.py
```

### Initial tests

```text
T1: deterministic threshold policy vs adversarial price probing
T2: randomized policy vs adversarial price probing
T3: delivery confidence maintained under randomized bids
T4: profit vs exploitability frontier
```

---

## R8-2: Aging-Aware Sub-graph Routing

### Threat model

Damage is not binary. Before a GPU dies, its probability of silent data corruption may drift upward. Fluxara therefore needs a path from:

```text
Damage Index + telemetry -> SDC risk -> op placement penalty
```

### Design goal

Route numerically sensitive operations to healthier devices, and route error-tolerant operations to older or riskier devices.

### Mathematical boundary

For GPU `i` and operation `o`:

```text
risk_cost(i, o) = eta(o) * P_SDC(i)
```

Placement objective:

```text
minimize  sum_i sum_o x[i,o] * eta(o) * P_SDC(i)
        + lambda_latency * latency_cost
        + lambda_comm * communication_cost
        + lambda_balance * residual_life_imbalance
```

subject to:

```text
capacity constraints
memory constraints
communication constraints
operator dependency constraints
```

### Health model v0.3

Use a conservative GPU-level SDC model first:

```text
P_SDC(i) = sigmoid(
    beta_0
  + beta_D * damage_index_i
  + beta_E * ECC_slope_i
  + beta_L * leakage_drift_i
  + beta_T * thermal_cycle_count_i
  + beta_X * XID_error_rate_i
)
```

Do not claim per-ALU or per-Tensor-Core micro-maps without vendor support. Start with:

```text
GPU-level placement -> MIG / device-slice placement -> kernel-class placement -> future SM-level placement
```

### Operator sensitivity table v0.3

Initial manually assigned sensitivity classes:

```text
Very high: softmax, normalization, optimizer state update, reduction for loss/grad norm
High: attention score matmul, logits projection, all-reduce gradients
Medium: dense GEMM in FFN, embedding lookup
Low: dropout mask generation, ReLU/GELU approximate regions, redundant eval jobs
```

These are placeholders. Replace with fault-injection-derived `eta(o)` values once `op_sensitivity.py` exists.

Suggested modules:

```text
fluxara_core/hardware/health_map.py
fluxara_core/hardware/op_sensitivity.py
fluxara_core/hardware/aging_aware_placer.py
```

### Initial tests

```text
T1: degraded GPU receives fewer high-eta ops
T2: placement improves expected SDC-weighted risk vs cost-only placement
T3: sensitivity table can be replaced by empirical fault-injection scores
T4: latency overhead remains bounded
```

---

## R8-3: Landauer Arbitrage / Reversible Computing

### Status

This is a long-term research direction, not a v0.2 engineering dependency.

Reason: current deployed GPUs do not expose a reversible-computing execution mode. The Landauer limit is a fundamental lower bound on bit erasure, but practical erasure and finite-time computation dissipate far above that limit.

### Research abstraction

If Fluxara later models reversible or partially reversible compute, use a thermodynamic debt state:

```text
A_t = ancilla_bits_accumulated
M_t = memory_used_by_ancilla
Q_debt_t = erasure_heat_debt
```

Debt dynamics:

```text
A_{t+1} = A_t + reversible_mode_ancilla_rate - erasure_rate
```

Lower-bound heat debt:

```text
Q_min = k_B * T * ln(2) * erased_bits
```

Practical heat debt:

```text
Q_actual = chi_hardware * Q_min + memory_traffic_energy + control_overhead
```

where `chi_hardware >> 1` for any realistic nonideal implementation.

### Roadmap boundary

Do not implement reversible compute in `solver.py`. Instead, reserve an optional research interface:

```text
fluxara_core/research/thermodynamic_debt.py
```

Initial use: toy simulations only.

---

## Release plan

### v0.2: Market Security Layer

Add stochastic bidding and adversarial tests.

Deliverables:

```text
BidPolicy interface
AdversaryAgent interface
Exploitability benchmark
Delivery quantile constraint
```

### v0.3: Hardware Health / Compiler Layer

Add aging-aware placement at GPU granularity.

Deliverables:

```text
HealthMap
SDC risk model
Operator sensitivity table
Aging-aware placement solver
```

### v0.R: Thermodynamic Research Layer

Keep as a whitepaper / toy-model track.

Deliverables:

```text
ThermodynamicDebt toy model
Landauer erasure-cost calculator
Memory-debt scheduling experiment
```

---

## Immediate code TODOs

1. Add `risk_surface_noise` and `rng_seed` to solver config.
2. Add a `BidPolicy` abstraction that wraps deterministic solver outputs.
3. Add adversary replay tests that infer bid thresholds.
4. Add `damage_index` -> `P_SDC` placeholder mapping.
5. Add an operator sensitivity dictionary for future compiler placement.
6. Keep Landauer arbitrage out of the production solver until hardware assumptions become real.
