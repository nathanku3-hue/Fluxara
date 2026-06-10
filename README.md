# Fluxara: Grid-Interactive AI Control Plane

> **Tagline:** *Turning AI data centers into controllable cyber-physical power plants.*

Fluxara is an advanced cyber-physical control plane designed to transform energy-intensive AI data centers into flexible, contractable grid assets. By co-optimizing power system signals, liquid cooling telemetry, silicon fatigue limitations, and distributed machine learning workloads in real time, Fluxara maximizes net risk-adjusted profit for hyper-scale infrastructure.

---

## 🚀 Key Features

- **Hierarchical Model Predictive Control (MPC):** Optimizes electricity costs, carbon, and hardware degradation over a sliding lookahead horizon.
- **Convex Physics Surrogate Solver:** Utilizes continuous relaxations to solve box-constrained Quadratic Programs (QP) in sub-milliseconds via `OSQP`.
- **Multi-Rate Plant Simulation:** Decouples 1-second physical/thermal updates from 5-minute grid bidding intervals.
- **Silicon Fatigue ledger:** Tracks transient HBM junction temperatures and cycles, penalizing rapid setpoint changes using a Coffin-Manson empirical damage proxy.
- **Workflow Visibility Integration:** Native support for the `meta-harness` markdown-first tracking ledger.

---

## 📁 Repository Structure

```
Fluxara/
├── fluxara_core/          # Core control system package
│   ├── bidding/           # v0.2 Stochastic bidding & market security
│   ├── hardware/          # v0.3 Aging-aware compiler placement
│   ├── research/          # v0.R Thermodynamic computing & Landauer arbitrage
│   ├── env.py             # Multi-rate physical/market environment
│   ├── solver.py          # Continuous convex MPC optimizer
│   └── demo.py            # Local closed-loop simulation script
├── docs/                  # Technical and product documentation
│   ├── ARCHITECTURE.md    # Control theory and clock resolution spec
│   ├── ROADMAP_R8.md      # Round 8 roadmap and release planning
│   ├── WHITEPAPER.md      # Co-optimization thesis and journal bibliography
│   └── product/
│       ├── prd.md         # Product Requirement Document
│       ├── product-spec.md# API signatures, data schemas, and specifications
│       └── decision-log.md# Architectural decision record log
├── pyproject.toml         # PEP 517 build configuration
└── README.md              # Project landing page
```

---

## 🛠️ Quickstart

### 1. Install Dependencies
Ensure you have Python 3.8+ and `npm` installed, then set up the python packages:

```bash
pip install numpy pandas scipy cvxpy osqp clarabel
```

*(Note: `cvxpy` is recommended for the convex optimizer. If it is not installed, the solver will automatically fall back to `SciPy L-BFGS-B` to keep the simulation runnable.)*

### 2. Run the Closed-Loop Demo
Install the package in editable mode:
```bash
pip install -e .
```

Then run the console script:
```bash
fluxara-demo
```

Alternatively, you can run the demo directly as a module:
```bash
python -m fluxara_core.demo
```

The script runs the MPC loop and outputs a step-by-step telemetry status:
```text
k=001 LMP=$  35.24/MWh u=1.000 ckpt=0.000 Tj=65.00C D=0.000e+00 backend=scipy-LBFGSB
k=002 LMP=$  32.88/MWh u=1.000 ckpt=0.000 Tj=70.45C D=0.000e+00 backend=scipy-LBFGSB
...
wrote fluxara_history.csv
```

---

## 📊 Workflow Visibility (`meta-harness`)

Fluxara incorporates the `meta-harness` workflow tool to maintain audit logs of all development phases.

### Initialize visibility
To inspect or log developmental events:
```bash
meta-harness init "Initialize Fluxara Control Plane" --owner "antigravity"
```

### Log a research event
```bash
meta-harness event --stream research --phase work --action "drafted whitepaper and prd specifications" --result "aligned brand identity and control boundaries"
```

### Check status
```bash
meta-harness status
```

---

## 📚 References & Scientific Anchors

Fluxara's core models are built upon research published in leading scientific journals:
- **Workload Flexibility:** *Nature Energy* (2025) field demonstration on a 256-GPU cluster showing 25% peak power demand reduction.
- **Carbon Intelligence:** *IEEE Transactions on Power Systems* Google Carbon-Intelligent Compute management.
- **Liquid Cooling:** ASME *Journal of Electronic Packaging* detailing $20^\circ\text{C}$ reductions in GPU junction temperature under ML workloads.
- **Silicon Fatigue:** *Journal of Semiconductor Technology and Science* (2026) characterization of CTE mismatch and warpage in 3D HBM stacks.
