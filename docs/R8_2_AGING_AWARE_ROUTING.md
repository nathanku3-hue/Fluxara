# R8-2: Aging-Aware Sub-graph Routing

## 1. Overview and Threat Model

Silicon degradation is not a binary failure state. Before a GPU completely fails (e.g., stops responding on the PCIe bus), physical wear-out mechanisms such as electromigration, hot-carrier injection, and thermal cycling degrade the gate oxide layers. This wear-out manifests as transient hardware faults, leading to an increased rate of **Silent Data Corruption (SDC)**.

In deep learning training and inference pipelines:
- An SDC in a **numerically sensitive** operator (e.g., `softmax` or `normalization`) can result in catastrophic gradient explosions or NaN values, corrupting the entire training run.
- An SDC in an **error-tolerant** operator (e.g., `dropout` or `gelu` approximations) has negligible impact on model convergence or downstream task performance.

Fluxara R8-2 introduces **Aging-Aware Sub-graph Routing**. By tracking device-level telemetry and estimated cumulative wear-out, Fluxara maps computation sub-graphs dynamically, routing highly sensitive operations to healthy GPUs and placing error-tolerant workloads on degraded GPUs, maximizing the useful lifetime of hardware fleets without compromising model accuracy.

---

## 2. Mathematical Formulations

### A. Silent Data Corruption (SDC) Risk Model
For each GPU $i$, the probability of SDC is modeled using a multivariate sigmoid function over active telemetry signals:

$$P_{SDC}(i) = \frac{1}{1 + e^{-z_i}}$$

where the linear log-odds predictor $z_i$ is computed from physical parameters:

$$z_i = \beta_0 + \beta_D D_i + \beta_E E_i + \beta_L L_i + \beta_T T_i + \beta_X X_i$$

- $D_i$: Cumulative physical damage index.
- $E_i$: Corrected ECC error rate slope.
- $L_i$: Static leakage current drift.
- $T_i$: Thermal cycle count.
- $X_i$: Driver-level XID error rate.
- $\beta$: Coefficents mapping telemetry to SDC probability (default: $\beta_0 = -6.0, \beta_D = 2.0, \beta_E = 1.5, \beta_L = 1.0, \beta_T = 0.5, \beta_X = 2.0$).

The physical device health score is defined as:

$$\text{HealthScore}(i) = 1.0 - P_{SDC}(i)$$

### B. Placement Optimization Problem
Given a set of operations $\mathcal{O}$ and a pool of GPUs $\mathcal{G}$, we define the binary placement decision variable:

$$X_{i,o} = \begin{cases} 1 & \text{if operation } o \text{ is assigned to GPU } i \\ 0 & \text{otherwise} \end{cases}$$

The objective is formulated as a Mixed-Integer Linear Program (MILP):

$$\min_{X, d} \sum_{i \in \mathcal{G}} \sum_{o \in \mathcal{O}} X_{i,o} \cdot \eta(o) \cdot P_{SDC}(i) + \lambda_{latency} \cdot \text{Cost}_{lat} + \lambda_{comm} \cdot \text{Cost}_{comm} + \lambda_{balance} \cdot \text{Cost}_{bal}$$

where:
- $\eta(o)$ is the operator sensitivity coefficient.
- $\text{Cost}_{lat} = \sum_{o \in \mathcal{O}} \sum_{i \in \mathcal{G}} X_{i,o} \cdot \text{base\_latency}_i$ (execution latency cost).
- $\text{Cost}_{comm} = \sum_{o \in \mathcal{O}} \sum_{i \in \mathcal{G}} X_{i,o} \cdot \text{comm\_delay}_i$ (inter-device communication penalty).
- $\text{Cost}_{bal} = \sum_{i \in \mathcal{G}} d_i$ (load imbalance surrogate), bounded by:
  $$d_i \ge \sum_{o \in \mathcal{O}} X_{i,o} \cdot \text{compute}_o - \text{TargetLoad}, \quad \forall i \in \mathcal{G}$$
  $$d_i \ge \text{TargetLoad} - \sum_{o \in \mathcal{O}} X_{i,o} \cdot \text{compute}_o, \quad \forall i \in \mathcal{G}$$
  where $\text{TargetLoad} = \frac{1}{|\mathcal{G}|} \sum_{o \in \mathcal{O}} \text{compute}_o$.

### C. Constraints
1. **Assignment Constraint**: Every operator must be placed on exactly one GPU:
   $$\sum_{i \in \mathcal{G}} X_{i,o} = 1, \quad \forall o \in \mathcal{O}$$

2. **Memory Capacity**: Total memory allocation must not exceed physical GPU capacity:
   $$\sum_{o \in \mathcal{O}} X_{i,o} \cdot \text{memory}_o \le \text{MemoryCapacity}_i, \quad \forall i \in \mathcal{G}$$

3. **Compute Capacity**: Total computational load must not exceed GPU throughput capacity:
   $$\sum_{o \in \mathcal{O}} X_{i,o} \cdot \text{compute}_o \le \text{ComputeCapacity}_i, \quad \forall i \in \mathcal{G}$$

4. **Colocation Constraints**: Certain operators must be colocated on the same physical device:
   $$X_{i, o_a} = X_{i, o_b}, \quad \forall i \in \mathcal{G}, \ \forall (o_a, o_b) \in \mathcal{C}$$

---

## 3. Operator Sensitivity Classification

Operator sensitivity coefficients $\eta(o)$ map mathematical structures to their vulnerability to silent data corruption:

| Severity | Sensitivity ($\eta$) | Operator Types | Failure Modes & Impacts |
| :--- | :--- | :--- | :--- |
| **Very High** | `10.0` | `softmax`, `normalization`, `optimizer_state_update`, `loss_reduction`, `grad_norm_reduction` | Div-by-zero, exponent overflow, weight/state corruption, model training failure. |
| **High** | `5.0` | `attention_score_matmul`, `logits_projection`, `all_reduce_gradients` | Erroneous attention distribution, gradient aggregation corruption. |
| **Medium** | `2.0` | `ffn_gemm`, `embedding_lookup` | Moderate noise injection into representation spaces, bounded validation loss degradation. |
| **Low** | `0.5` | `dropout_mask_generation`, `relu`, `gelu_approx`, `redundant_eval` | Minor changes to sparse activation patterns, negligible effect on downstream accuracy. |

---

## 4. Placement Engine Architecture

The placement engine utilizes a two-tier execution plan:
1. **Primary MILP Solver**: Solves the CVXPY MILP formulation to optimality.
2. **Greedy Heuristic Fallback**: Runs in $\mathcal{O}(|\mathcal{O}| \log |\mathcal{O}| + |\mathcal{O}| \cdot |\mathcal{G}|)$ if the mathematical solver fails or experiences timeout. It sorts operations by sensitivity descending, and greedily maps each to the device that minimizes the local incremental cost contribution while satisfying hard capacity limits.

---

## 5. Known Limitations
1. **Static Sensitivities**: While sensitivities are customizable via JSON load files, the placement engine currently treats operator sensitivities as static variables. Runtime dynamic precision or dynamic scale scaling could adjust sensitivity levels on the fly.
2. **Network Topology Simplicity**: The inter-device communication cost is modeled as device-level communication delay coefficients rather than a full non-uniform memory access (NUMA) / NVLink network topology matrix.
3. **Simulator-Level Health Modeling**: The physical telemetry model, damage indices, and SDC probabilities are strictly **simulator-level surrogates**. They are meant for control-loop validation and compiler scheduling evaluations. They should not be interpreted as absolute physical predictions unless calibrated telemetry and empirical SDC profiles from specific GPU hardware models become available.
