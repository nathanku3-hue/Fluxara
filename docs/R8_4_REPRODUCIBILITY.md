# Fluxara R8-4 Reproducibility Contract

This document outlines the reproducibility contracts, testing procedures, and environmental controls for Fluxara to ensure that all simulation, optimization, and research outputs can be audited and verified externally.

---

## 1. Pinned Environment Controls

To eliminate variances in core libraries (especially solvers like OSQP/Clarabel and float parsing engines), the environment is pinned in the repository root:
- **`requirements.lock.txt`**: Pinned list of exact package versions used to run tests and benchmarks.
- **`constraints.txt`**: Constraints enforced during installation.

### Installation
To install the verified reproducible environment:
```bash
pip install -r requirements.lock.txt -c constraints.txt
```

---

## 2. Replay and Validation Checks

Deterministic acceptance and schema validations are performed using the following script:
```bash
# Verify release schemas and run replay with seed 1337
python scripts/replay_acceptance.py --seed 1337

# Verify with baseline seed 42 (asserts exact match with report)
python scripts/replay_acceptance.py --seed 42
```

### Script Actions
1. **Schema Validation**: Validates `r8_acceptance_report.json`, `release_manifest_v0.4_research_alpha.json`, and `release_manifest_v0.4.1_repro_alpha.json` against their official schemas in `schemas/`.
2. **CSV Dataset Validation**: Parses `r8_3_crossover_surface.csv` row-by-row and verifies schema alignment.
3. **Acceptance Replay**: Reruns the Market bidding loop, Monte Carlo safety trials, and hardware Router Placer benchmark under the parameterized seed.

---

## 3. Tolerated Numeric Drift

For any non-baseline seeds (e.g. `--seed 1337`), stochastic market trajectories will naturally drift from the baseline report:
- **Deterministic Metrics**: (Deterministic exploitability, deterministic profit, and Placer routing risk) remain exact.
- **Stochastic Metrics**:
  - Exploitability ratio: Allowed to drift up to $\le 0.90$ (due to randomized bidding variance).
  - Profit ratio: Allowed to drift down to $\ge 0.95$.
  - Monte Carlo safety success rate: Must remain $\ge 0.999$.
  - SDC risk reduction: Must remain $\ge 30.0\%$.

---

## 4. Simulator-vs-Telemetry Boundary

Fluxara maintains a strict boundary between simulator models and actual physical/hardware telemetry:
- **Simulator (Production Alpha)**: Uses model-based approximations for LMP grid bids, CPU/GPU temperature cycles, and Coffin-Manson empirical damage factors.
- **Research Abstractions (Research Alpha)**: Evaluates ideal theoretical Landauer limits and caching thermodynamics. It is physically isolated and does not claim physical reversible computing on actual hardware.
- **Hardware Telemetry**: Future iterations (e.g. real-world deployments) must ingest real-time hardware telemetry streams (e.g. NVML, IPMI) to validate simulator predictions. Actual controller decisions remain strictly decoupled from the thermodynamic computing model.

---

## 5. External Validation Path

External auditors can run the verification checks on standard hardware:
1. Clone the repository at tag `v0.4.1-repro-alpha`.
2. Install pinned dependencies.
3. Run the replay script to verify schema compliance and mathematical convergence:
   ```bash
   python scripts/replay_acceptance.py --seed 1337
   ```
