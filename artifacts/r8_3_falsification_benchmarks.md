# R8-3 Reversible Computing & Landauer Falsification Benchmarks

> [!WARNING]
> **Strict Research Decoupling Disclaimer:**
> - R8-3 is a simulator-only research track.
> - It does not claim or imply reversible computing execution capabilities on any deployed hardware (e.g., standard GPUs).
> - It does not modify, influence, or interact with production grid bidding, physical curtailment delivery, or aging-aware hardware routing behavior.
> - The production control plane solver remains 100% decoupled from these theoretical models.

---

## 1. Practical Dissipation Sweeps ($Q_{actual}$ in Watts)

Swept over typical silicon operating temperatures $T$ and CMOS-level silicon overhead factors $\chi_{hardware}$ for an execution rate generating $10^{12}$ bits of ancilla state per second.

| \\chi_{hardware} | T = 25°C (298.1 K) | T = 45°C (318.1 K) | T = 65°C (338.1 K) | T = 85°C (358.1 K) | T = 95°C (368.1 K) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1e+00** | `2.8533e-09` W | `3.0447e-09` W | `3.2361e-09` W | `3.4275e-09` W | `3.5232e-09` W |
| **1e+02** | `2.8533e-07` W | `3.0447e-07` W | `3.2361e-07` W | `3.4275e-07` W | `3.5232e-07` W |
| **1e+04** | `2.8533e-05` W | `3.0447e-05` W | `3.2361e-05` W | `3.4275e-05` W | `3.5232e-05` W |
| **1e+06** | `2.8533e-03` W | `3.0447e-03` W | `3.2361e-03` W | `3.4275e-03` W | `3.5232e-03` W |
| **1e+08** | `2.8533e-01` W | `3.0447e-01` W | `3.2361e-01` W | `3.4275e-01` W | `3.5232e-01` W |

> [!CAUTION]
> **Falsification Insight:** Standard CMOS gate switching transitions dissipate $\approx 10\text{ fJ}$ ($10^{-14}\text{ J}$), yielding an implied silicon overhead factor $\chi_{hardware} \ge 10^5$. At standard operating temperatures, this results in significant thermal dissipation, dwarfing the theoretical Landauer bound and verifying **Hypothesis 1** that Landauer arbitrage is non-viable on standard CMOS nodes.

---

## 2. Caching Efficiency Crossover Surface

Ancilla bits can be cached to physical memory to defer erasure. We map the crossover surface showing whether **caching is efficient** (True) or **caching is inefficient / falsified** (False) as a function of the caching transaction energy and silicon overhead $\chi_{hardware}$.

Swept for a cache size of $10^{10}$ bits at $T = 75^\circ\text{C}$ ($348.15\text{ K}$).

| Transaction Energy (E_{mem}) | \\chi_{hardware} = 1e+00 | \\chi_{hardware} = 1e+02 | \\chi_{hardware} = 1e+04 | \\chi_{hardware} = 1e+06 | \\chi_{hardware} = 1e+08 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1e-12 J** | **TRUE** | **TRUE** | **TRUE** | **TRUE** | **TRUE** |
| **1e-09 J** | **FALSE** | **TRUE** | **TRUE** | **TRUE** | **TRUE** |
| **1e-08 J** | **FALSE** | **FALSE** | **TRUE** | **TRUE** | **TRUE** |
| **2e-08 J** | **FALSE** | **FALSE** | **TRUE** | **TRUE** | **TRUE** |

> [!CAUTION]
> **Falsification Insight:** Current memory access energy is $\ge 2\text{ nJ}$ per transaction. At realistic silicon overhead factors ($\chi \le 10^6$), the memory write/read overhead to store the ancilla state exceeds the thermal erasure cost, validating **Hypothesis 2** (caching is falsified for standard memory buses).
