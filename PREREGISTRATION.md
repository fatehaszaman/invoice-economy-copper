# Pre-registration

**This document is committed before any estimation code exists in this repository.**

Verify that claim yourself:

```bash
git log --diff-filter=A --format='%ad  %s' -- PREREGISTRATION.md
git log --diff-filter=A --format='%ad  %s' -- research/
```

The first must strictly precede the second. `make estimate` will not run unless `pcs.lock` matches the commit that introduced this file — see `pcs/lock.py`.

Nothing below was written with knowledge of any estimation output, because no estimation code existed when it was written.

---

## 1. Research question

When multiple commodity datasets claim to measure "demand," can disagreement between them reveal market structure rather than merely bad data?

Concretely: can public commodity data distinguish a tonne of copper moving toward consumption from a tonne generating transactions because of financial, administrative, or ownership plumbing?

## 2. The instrument — Physical Consistency Score

\[
\mathrm{PCS}_t = \bar{z}^{\text{physical}}_t - \bar{z}^{\text{commercial}}_t
\]

**Sign convention, fixed here:** negative PCS means commercial activity is running ahead of its physical corroboration. Positive means physical evidence exceeds commercial activity.

**Interpretation, constrained here:** a negative score means *the commercial signal cannot be reconciled with independent physical evidence.* It does not mean fraud, fake demand, or financing. Any such attribution belongs to the research layer and must be argued separately.

### 2.1 Block membership

Frozen in `config/pcs.yaml`. Reproduced here for the record.

**Physical block** (PCS input)
- cable and wire output
- semis production
- refined copper production
- net refined imports
- inventory withdrawals
- scrap utilisation

**Commercial block** (PCS input)
- SHFE volume-to-open-interest churn
- warrant churn
- deliveries relative to warrant change
- ownership-transfer proxy
- trader-activity proxy

**Market confirmation block** — **explicitly held out of PCS**
- Yangshan premium
- Shanghai #1 refined spot premium
- SHFE–LME arbitrage state
- nearby spread
- curve structure

**Why held out.** A physical premium can itself reflect genuine physical scarcity. Including premiums in the predictor and then using the predictor to explain premium behaviour would be circular. The confirmation block is instead tested as a *consequence* of PCS:

\[
M_{t+h} = \alpha + \beta_1 \text{HeadlineDemand}_t + \beta_2 \mathrm{PCS}_t + \varepsilon_t
\]

The pre-registered prediction is \(\beta_2 \neq 0\) with the sign implied by §3.

### 2.2 Construction rules, all fixed in advance

| Rule | Value |
|---|---|
| Stationary transform | Per series in `config/pcs.yaml`; log-difference default |
| Standardisation | Rolling z-score, prior-vintage data only, window 252 observations |
| Normalisation window | Must not overlap the event window; enforced in code |
| Baseline weights | Equal within each block. No optimisation. |
| Missing data | Dropped from that period's block mean. **Never imputed.** |
| Coverage floor | 0.60 per block. Scores below are labelled low-confidence and excluded from primary estimation. |
| Sensitivity variants | equal, inverse-variance, leave-one-series-out, residual construction |

If the conclusion depends on which weighting variant is used, that dependence is the reported finding.

## 3. Hypothesis

> Commercial and transaction activity in high invoice-exposure channels contracted materially more than in low-exposure channels across the enforcement window, with the magnitude ordered by exposure intensity, while downstream physical output (cable, wire, semis) did not fall commensurately. Therefore a portion of pre-shock "demand" activity was commercial circulation and input-form substitution rather than end use.

**Predicted direction:** PCS becomes more negative in the pre-event period in high-exposure channels, and the enforcement episode compresses commercial activity toward physical corroboration — PCS moves toward zero or positive after `t_A`.

## 4. Identification

**Treatment is pre-existing invoice exposure, not material type.**

A scrap-versus-cathode design was considered and **rejected before estimation**: the proposed mechanism is that invoice friction pushes buyers *from* scrap *toward* cathode, so cathode is an outcome of the treatment rather than a control. See `MISTAKES.md`.

**Specification.** Static:

\[
Y_{i,t} = \alpha_i + \gamma_t + \beta\,(\text{Post}_t \times \text{Exposure}_i) + \varepsilon_{i,t}
\]

Event-dynamic, which is the reported form:

\[
Y_{i,t} = \alpha_i + \gamma_t + \sum_k \beta_k\,\mathbb{1}[t - t_0 = k]\cdot\text{Exposure}_i + \varepsilon_{i,t}
\]

**This is dose-response, not treated-versus-control.** Enforcement was national. No copper channel is untreated; "low exposure" means less treated. The primary reported evidence is therefore **monotonicity of effect across exposure intensity**, not the magnitude of a single coefficient.

**Event window — two reference points.** `t_A` = 2026-04-13, onset of observable enforcement inspections. `t_B` = 2026-04-24, formal national guidance. Fixed in `config/events.yaml`. Effects beginning before `t_B` are a finding about policy transmission, not a broken model.

## 5. Exposure classification

Frozen in `config/exposure.yaml`, committed with this document. Continuous `exposure ∈ [0,1]` is primary; tiers are a coarsened robustness check.

| Channel | Exposure | Tier | Documented basis | Confidence |
|---|---|---|---|---|
| `scrap_domestic / multi_intermediary` | 0.95 | high | Reverse invoicing dependence; CNY 5m individual seller cap; scrap invoice cost ~7%→10% H1 2026 | high |
| `scrap_domestic / single_intermediary` | 0.75 | high | Same instruments, shorter chain | moderate |
| `cathode / multi_intermediary` | 0.55 | moderate | Invoice quota limits reported binding on traders | moderate |
| `scrap_imported / single_intermediary` | 0.45 | moderate | Customs documentation substitutes for some domestic invoicing | low |
| `cathode / single_intermediary` | 0.35 | moderate | Quota constraints reported but less binding | moderate |
| `cathode / direct_smelter` | 0.10 | low | Buyers observably shifted toward direct smelter procurement | high |
| `rod / direct_smelter` | 0.10 | low | Minimal intermediation | moderate |

Where the basis is trade commentary rather than a published figure, confidence is marked `low` or `moderate` accordingly. **Any later change to this table must be recorded in `DECISIONS.md` with the old value, new value, reason, date, and whether the result changed.**

## 6. Falsification conditions

The hypothesis is rejected if **any** of the following holds. Each is tested by a named module.

| Condition | Module |
|---|---|
| Downstream physical output fell in line with transaction activity | `research/exposure.py` |
| Effects do not order monotonically by exposure intensity | `research/monotonicity.py` |
| High- and low-exposure channels were already diverging before `t_A` | `research/pretrends.py` |
| Placebo dates produce comparable effects | `research/placebos.py` |
| Low-exposure metals produce comparable effects | `research/placebos.py` |
| The permutation distribution puts the actual labelling inside its bulk | `research/permutation.py` |
| The result holds only under one PCS weighting variant | `pcs/sensitivity.py` |
| The exposure ordering does not survive the confounder ladder | `research/confounders.py` |

**If any condition triggers, `FINDINGS.md` reports the hypothesis as rejected.** A null result is a publishable outcome of this repository, and the README says so on the first screen.

## 7. Confounders acknowledged in advance

Record copper prices during 2026, US Section 232 tariff uncertainty, mine-side concentrate tightness, a shifting SHFE–LME import arbitrage window, and general macro risk appetite. These are entered as a ladder in `research/confounders.py` rather than controlled away silently; the estimate is reported at each rung.

The policy change is described as **plausibly external** to short-run physical copper supply and end-use demand — it is a tax-compliance campaign, not a market event. It is not described as exogenous, because the above coincided with it.

## 8. Inference, fixed in advance

| Purpose | Method |
|---|---|
| Uncertainty on the exposure coefficient | Block bootstrap over time blocks |
| Cross-sectional significance | Permutation of exposure labels across channels |
| Within-channel correlation | Cluster-robust SEs by channel — **secondary**, reported but not relied on given few clusters |
| Measurement error in constructed physical quantities | Monte Carlo propagation |

Monte Carlo is **not** used for inference on the causal coefficient.

## 9. Data

Publicly accessible or individually licensed source data only. No employer or confidential data of any kind. Where licensed LME history is unavailable, the pipeline runs in documented SHFE-only fallback mode and labels affected results.

---

*Committed before estimation. Amendments, if any, appear in `DECISIONS.md` with dates — never by editing this file silently.*
