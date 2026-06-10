# R8-3: Reversible Computing & Landauer Arbitrage Research Plan

> [!WARNING]
> **Research-Only Track Disclaimer:**
> This plan defines a purely theoretical and simulation-only track. Deployed hardware architectures (e.g., standard GPUs) do not support physically reversible execution. This model must remain decoupled from the active production solver and plant control loops until reversible hardware is deployed and calibrated telemetry becomes available.

---

## 1. Research Context & Problem Statement

Landauer's Principle states that the erasure of one bit of information always dissipates a minimum amount of heat:

$$Q_{min} = k_B \cdot T \cdot \ln(2)$$

where $k_B$ is the Boltzmann constant and $T$ is the absolute junction temperature of the silicon. 

Modern high-performance computing devices dissipate energy orders of magnitude above this thermodynamic limit due to resistive losses, leakage, and non-reversible logic gates (which erase bits continuously). If a computing node could execute operations reversibly, it could theoretically defer or avoid this erasure heat dissipation, transferring the "debt" into stored ancilla bits.

This research plan defines a framework to simulate and analyze the trade-offs of storing ancilla bits to defer thermal dissipation under memory and power constraints.

---

## 2. Research Hypotheses

### Hypothesis 1: Silicon Overhead Falsification
While reversible operations theoretically avoid immediate thermal erasure dissipation, any implementation on standard silicon architectures introduces a physical overhead factor $\chi_{hardware} \gg 1$. 

We hypothesize that for all standard GPU silicon operating temperatures ($30^\circ\text{C}$ to $95^\circ\text{C}$), the practical erasure cost:

$$Q_{actual} = \chi_{hardware} \cdot Q_{min} + E_{mem\_traffic} + E_{control}$$

will exceed standard non-reversible gate switching energy by a factor of at least $10^4$, making Landauer arbitrage economically non-viable on current standard semiconductor nodes.

### Hypothesis 2: Memory-Debt Scheduling Boundary
Deffering bit erasure requires accumulating ancilla bits in physical memory ($A_t$). We hypothesize that there exists a critical memory capacity pressure $M_{limit}$ above which the energy overhead of swapping ancilla bits to storage/memory ($E_{mem\_traffic}$) exceeds the thermodynamic cooling power savings of deferred erasure.

---

## 3. Measurable Simulator Experiments

We define three toy-model simulator experiments to test these hypotheses under `fluxara_core/research/`:

### Experiment 1: Erasure-Cost Sensitivity Sweep
- **Objective:** Map $Q_{actual}$ as a function of temperature $T$, hardware overhead $\chi_{hardware}$, and bit erasure rates.
- **Parameters:**
  - $T \in [300K, 370K]$ (approx. $27^\circ\text{C}$ to $97^\circ\text{C}$)
  - $\chi_{hardware} \in [1.0, 10^6]$
- **Measurement:** Thermal debt generation rate (Watts).

### Experiment 2: Ancilla Caching vs. Memory Traffic Energy
- **Objective:** Simulate a sliding lookahead window where the scheduler can choose to write ancilla bits to memory (deferring erasure) or erase them immediately (generating heat).
- **Measurement:** Total system energy cost (caching energy + erasure heat).
- **Target Outcome:** Find the crossover point where caching becomes less efficient than immediate erasure.

---

## 4. Falsification Criteria

This research track's thermodynamic scheduling viability is **falsified** if:
1. The additional energy required to access and write ancilla bits to high-bandwidth memory (HBM) ($E_{mem\_traffic}$) is greater than the cooling power savings achieved by deferring the equivalent thermal dissipation at all temperatures $T \le 100^\circ\text{C}$.
2. The silicon overhead $\chi_{hardware}$ required to implement reversible gates on standard CMOS logic exceeds $10^2$.

---

## 5. Implementation Roadmap (Future Research Track)

Once approved, the implementation of this research track will be limited to:
1. `fluxara_core/research/thermodynamic_debt.py`: Toy simulation class tracking ancilla bits and heat debt.
2. `fluxara_core/research/landauer_calc.py`: Utility to compute theoretical vs. actual erasure heat.
3. `tests/test_landauer_toy.py`: Verification script validating the toy dynamics and falsification gates.

Under no circumstances will these classes be imported into `fluxara_core/solver.py` or used for actual grid bidding clears.
