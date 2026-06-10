# R8-1: Market Security & Stochastic Bidding

## 1. Overview and Threat Model

A deterministic demand-response policy operates with static price thresholds:

$$\text{curtail load if } \text{LMP}_t \ge \text{Threshold}$$

When a data center operates at a gigawatt scale, it becomes a "price-maker". If its price-response threshold is static, strategic market counterparties (e.g., generator-marketers or arbitrageurs) can easily probe and infer this threshold by observing price-response historical pairs. Once inferred, the adversary can manipulate local prices (e.g., bidding prices right around the threshold) to trigger artificial load-shedding or exploit the data center's rebound cycles.

Fluxara R8-1 introduces a **stochastic bidding policy** that injects private randomized noise into the bidding surface to obscure response boundaries, preventing threshold inference while strictly maintaining physical delivery safety.

---

## 2. Mathematical Formulations

### A. Stochastic Bid Generation
The `BidPolicy` wraps deterministic MPC solver outputs ($u_{det}, c_{det}$) with private Gaussian noise:

$$u_{rand} = u_{det} + \epsilon_u, \quad \epsilon_u \sim \mathcal{N}(0, \sigma_u^2)$$

$$c_{rand} = c_{det} + \epsilon_c, \quad \epsilon_c \sim \mathcal{N}(0, \sigma_c^2)$$

Where $\sigma_u$ represents `risk_surface_noise`. The randomized setpoints are clipped to physical limits:

$$u_{rand} \in [\text{min\_power\_frac}, 1.0], \quad c_{rand} \in [0.0, 1.0]$$

The resulting bid parameters sent to the grid are:
- `bid_mw` $= (1.0 - u_{rand}) \times \text{site\_mw}$
- `bid_price_usd_per_mwh` $= \text{Threshold} + \epsilon_{price}$

### B. Solver Chance Constraints
To guarantee that physical delivery meets commitments even with randomized noise additions, we convert the checkpoint-liquidity safety constraint in the solver into a convex **chance constraint**:

$$P(1.0 - u_{rand} \le \text{interruptible\_frac}) \ge \eta$$

Since $u_{rand} = u_{det} + \epsilon_u$, the constraint is formulated as:

$$1.0 - u_{det} + z_{\eta} \sigma_u \le \text{interruptible\_now} + G_{ckpt} \cdot c_{det}$$

where $z_{\eta}$ is the inverse CDF value (z-score) corresponding to the delivery confidence $\eta$ (e.g., $z = 3.09$ for $\eta = 0.999$, computed via `scipy.stats.norm.ppf`).

### C. Exploitability and Prediction Error
The adversary's prediction accuracy is evaluated by a classification model attempting to classify whether the data center is throttled ($u < 0.99$) or unthrottled ($u \ge 0.99$) based on its estimated threshold:

$$\text{Exploitability} = \max\left(0, \frac{\text{Accuracy} - 0.5}{0.5}\right)$$

An exploitability score of $1.0$ indicates perfect adversary prediction (deterministic baseline), while $0.0$ indicates random guessing.

---

## 3. Configuration Table

| Configuration Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `rng_seed` | `int` | `42` | Seed to control stochastic bid generation and ensure reproducibility. |
| `risk_surface_noise` | `float` | `0.03` | Standard deviation ($\sigma_u$) of the Gaussian noise applied to the power fraction. |
| `delivery_confidence` | `float` | `0.999` | Required probability threshold ($\eta$) for satisfying physical delivery commitments. |
| `shortfall_cvar_alpha` | `float` | `0.99` | Quantile level ($\alpha$) for tail-risk Conditional Value at Risk ($CVaR$) calculations. |
| `exploitability_weight` | `float` | `100.0` | Objective weight of the exploitability cost term. |

---

## 4. Benchmark Replays (Example Report)

Comparative evaluation results over a 48-step market day:

| Policy | Exploitability | Expected Profit | Delivery Success Rate |
| :--- | :--- | :--- | :--- |
| **Deterministic Baseline** | `1.000` | `$1,250.00` | `1.000` |
| **Stochastic Bidding** | `0.667` | `$1,225.00` | `1.000` |
| **Improvement Delta** | **-33.3%** (Gate: $\le -25\%$) | **98.0% Retained** (Gate: $\ge 95\%$) | **Passed** ($\ge 99.9\%$) |

---

## 5. Known Limitations
1. **Gaussian Assumption:** Bidding noise is currently modeled using a standard Gaussian distribution. Extreme grid volatility could warrant heavy-tailed distributions.
2. **Static Threshold Assumption:** The threshold estimation model assumes the baseline price-response threshold remains constant over the observation window.
