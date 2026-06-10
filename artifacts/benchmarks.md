# Fluxara R8 Performance & Safety Benchmarks

This artifact documents the verified performance and safety benchmarks for **R8-1 (Stochastic Bidding)** and **R8-2 (Aging-Aware Routing)**. 

---

## 1. R8-1: Profit vs. Exploitability

Strategic adversaries attempt to probe and estimate the data center's price-response threshold. We evaluate the effectiveness of the **Stochastic Bidding** policy in obscuring the bid surface compared to the **Deterministic Baseline** over a 48-interval CAISO market simulation.

| Metric | Deterministic Baseline | Stochastic Bidding | Comparison Ratio / Delta | Gate Threshold | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Adversary Exploitability** | `0.583` | `0.417` | **-28.6%** (Ratio: `0.714`) | $\le$ 25% Reduction (Ratio $\le$ 0.75) | **PASSED** |
| **Expected Profit** | `$38.30` | `$48.53` | **+26.7%** (Ratio: `1.267`) | $\ge$ 95% Retained (Ratio $\ge$ 0.95) | **PASSED** |

> [!NOTE]
> Under this specific price trajectory, the stochastic policy actually achieves *higher* expected profit than the deterministic policy due to opportunistic clearing from randomized price offsets.

---

## 2. R8-1: Delivery Confidence & Tail Risk

To guarantee that randomized bidding does not violate physical demand-response capacity commitments, we run a **10,000-trial Monte Carlo simulation** under the chance-constrained MPC solver setpoints ($z_{\eta} = 3.09$ safety buffer for $99.9\%$ delivery confidence).

| Parameter / Metric | Measured Value | Target Gate | Status |
| :--- | :--- | :--- | :--- |
| **Monte Carlo Trials** | `10,000` | $\ge 10,000$ | **PASSED** |
| **Delivery Success Rate** | `1.00000` (100.0%) | $\ge 99.9\%$ (`0.9990`) | **PASSED** |
| **CVaR_99 (Tail Shortfall)** | `0.0000` MW | $\le 0.05$ MW | **PASSED** |

---

## 3. R8-2: SDC-Weighted Risk vs. Latency

Aging-aware sub-graph routing maps computation tasks to GPUs based on device health. We compare the **Aging-Aware MILP Placer** against the **Cost-Only Placer** under active degradation settings:
- `gpu_0` (Healthy): $P_{SDC} \approx 0.002$
- `gpu_1` (Medium wear): $P_{SDC} \approx 0.119$
- `gpu_2` (Degraded): $P_{SDC} \approx 0.880$

| Placement Metric | Cost-Only Baseline | Aging-Aware MILP | Improvement Delta | Gate Threshold | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **SDC-Weighted Risk** | `15.988` | `1.866` | **-88.3%** | $\ge 30\%$ Reduction | **PASSED** |
| **Latency Overhead** | `0.00%` | `0.00%` | **+0.00%** | $\le 5.0\%$ Overhead | **PASSED** |

---

## 4. Cost-Only vs. Aging-Aware Placement Mapping

Detailed breakdown of operator placements across devices:

### Cost-Only Placement (Baseline)
- **High/Very High Sensitivity Operators on Degraded GPU (`gpu_2`):** `2` (`op_0` softmax, `op_1` normalization)
- **Low/Medium Sensitivity Operators on Degraded GPU (`gpu_2`):** `0`
- **Resulting Risk Exposure:** Severe. Highly sensitive math runs on hardware with high probability of Silent Data Corruption.

### Aging-Aware Placement (Ours)
- **High/Very High Sensitivity Operators on Degraded GPU (`gpu_2`):** `0` (Reduction: **100.0%**, Gate: $\ge 50\%$) — **PASSED**
- **Placements on Healthy GPU (`gpu_0`):** `op_0` (softmax, Very High), `op_1` (normalization, Very High), `op_2` (attention matmul, High)
- **Placements on Degraded GPU (`gpu_2`):** `op_4` (relu, Low), `op_5` (redundant_eval, Low)
- **Resulting Risk Exposure:** Minimized. Degraded hardware is only loaded with error-tolerant operations.
