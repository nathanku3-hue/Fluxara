# Product Requirement Document (PRD) - Fluxara Core

## 1. Document Overview

This document defines the product requirements for **Fluxara Core**, a Grid-Interactive AI Control Plane. Fluxara enables operators of large-scale AI compute clusters to dynamically schedule workloads, cap power usage, and dispatch hardware assets to maximize cost arbitrage and carbon savings without compromising silicon health or violating user SLAs.

---

## 2. Product Goals & Target Audience

### A. High-Level Goals
- **Monetize Demand Flexibility:** Convert rigid megawatt-scale AI training clusters into contractable, demand-responsive grid assets.
- **Minimize Total Cost of Ownership (TCO):** Co-optimize energy costs, carbon taxes, hardware degradation, and SLA penalties.
- **Ensure Safety and Reliability:** Implement strict physics-informed guardrails (thermal and electrical limits) that cannot be breached by the optimization layer.

### B. Target Audience
- **Cloud Infrastructure Engineers:** Responsible for scheduling AI jobs (e.g., via Slurm or Kubernetes) and maintaining cluster reliability.
- **Data Center Energy Managers:** Tasked with minimizing energy opex, avoiding demand charges, and fulfilling carbon neutrality targets.
- **Utility and Microgrid Operators:** Interested in bidding the data center's flexibility into demand-response or frequency-regulation programs.

---

## 3. Product Scope & Roadmap Releases

Fluxara will be developed in iterative releases:

### A. Release v0.1: Core Co-Optimization Engine (Current Baseline)
- **Multi-Rate Simulation Plant:** 1-second resolution for temperature and checkpoint state; 5-minute resolution for market and bidding.
- **Convex Model Predictive Controller (MPC):** Fast, convex optimization solver using continuous relaxations of checkpoint efforts and job-pausing states to ensure sub-second solve latency.
- **Environmental Physics Ledger:** High-fidelity tracking of junction temperature ($T_j$), Coffin-Manson microbump fatigue damage, and high-temperature dwell creep.
- **Synthetic Data Fixtures:** CAISO-like LMP and carbon intensity data generators for local workstation development.

### B. Release v0.2: Market Security & Stochastic Bidding
- **Stochastic Bidding Layer:** Introduce randomized bidding surfaces using private entropy to prevent strategic price-maker exploitation.
- **Adversary Probing Simulation:** Replay and benchmark the system against an external agent attempting to infer Fluxara's pricing thresholds.
- **Delivery Quantile Constraints:** Hard constraint models to guarantee that committed physical delivery is satisfied with $\ge 99.9\%$ probability.

### C. Release v0.3: Hardware-Aware Compiler Placement
- **Silent Data Corruption (SDC) Model:** GPU-level risk estimation mapping cumulative fatigue damage and ECC error logs to SDC probability.
- **Operator Sensitivity Classification:** Interface that groups ML operations (e.g., softmax, dense GEMM) based on their mathematical error tolerance.
- **Aging-Aware Placer:** Compiler scheduling module to route highly sensitive math to healthy GPUs and error-tolerant math to degraded GPUs.

---

## 4. Technical Requirements

### A. Input Telemetry Interface
Fluxara must ingest synchronized telemetry from the facility and compute cluster:
- **GPU Metrics:** Power draw (W), junction temperature (°C), utilization (%), memory bandwidth.
- **Facility Metrics:** Ambient temperature, coolant flow rate, return temperature, power feeder capacity (MW).
- **IT Metrics:** Current checkpoint age (s), fraction of jobs that are checkpointable/interruptible.
- **Market Metrics:** Locational Marginal Price ($/MWh), carbon intensity (kg/MWh).

### B. Solver Constraints and Guardrails
The solver must satisfy the following constraints at all times:
1. **Power Feeder Capacity:** Total allocated power must not exceed site feeder limits.
2. **Thermal Safety Thresholds:** Junction temperatures must not exceed manufacturer limits ($105^\circ\text{C}$).
3. **SLA Execution Bounds:** Deferred jobs must not violate user-defined deadlines.
4. **Checkpoint Liquidity:** Shedding rate is bounded by the current interruptible capacity, which is dynamically refreshed by checkpoint effort.

### C. Execution Latency
- The optimization step in the control loop must resolve in **under 100 milliseconds** using CVXPY + OSQP on a standard workstation to support real-time grid actuation.
