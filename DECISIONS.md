# Decisions

Every parameter that could have gone another way, with the reason it went this
way, and what would change it. Recorded before estimation.

Any change to a locked value after pre-registration requires a new row here
with old value, new value, reason, date, and whether the result changed — and
a deliberate re-lock. `make estimate` fails until that happens.

| # | Decision | Value | Reason | What would change it |
|---|---|---|---|---|
| 1 | PCS sign | physical − commercial | Negative reads as "commercial ahead of physical", the direction of interest | Nothing; locked pre-registration |
| 2 | Block weights | equal within block | No basis for differential weights before seeing data; unequal weights invite tuning | A documented external basis, recorded here first |
| 3 | Premiums in PCS | excluded, separate block `M_t` | Circularity: premiums are the outcome being explained | Nothing |
| 4 | Standardisation | rolling z, 252d, shifted by 1 | Prevents an observation standardising itself; window must not overlap the event | — |
| 5 | Coverage floor | 0.60 per block | Below this, a block mean rests on too few series to mean much | Sensitivity grid reports 0.50 and 0.70 |
| 6 | Missing data | drop, never impute | Imputation biases toward the null being tested | Nothing |
| 7 | Treatment | invoice exposure intensity, continuous [0,1] | Material type is contaminated by substitution (`MISTAKES.md` §1) | — |
| 8 | Tiers | secondary, robustness only | Continuous avoids arbitrary cutpoints; tiers aid monotonicity readability | — |
| 9 | Primary result | monotonicity across exposure | National enforcement means no untreated group; ordering is harder to confound than a magnitude | — |
| 10 | Event dates | t_A 2026-04-13, t_B 2026-04-24 | Observable enforcement preceded formal guidance; a single date would misdate the response | Documented evidence of a different onset |
| 11 | Inference | block bootstrap + permutation | Serial dependence and few clusters | — |
| 12 | Cluster-robust SE | reported, secondary | Unreliable asymptotics with few clusters; suppressing it entirely would be worse | More channels |
| 13 | Monte Carlo | measurement error only | Cannot establish causal magnitude from observational data | Nothing |
| 14 | Pre-trend alpha | 0.10 | Lenient by design: a false alarm is cheaper than a missed pre-trend | — |
| 15 | Placebo dates | 2025-04-24, 2025-10-24, 2024-04-24, 2026-01-24 | Tests seasonality and calendar artefacts | — |
| 16 | Negative controls | aluminium, lead | Industrial metals without the same invoice mechanism | — |
| 17 | Bootstrap block | 20 business days | ~1 month; sensitivity at 10 and 40 | — |
| 18 | Seed | 20260424 | The event date; arbitrary but fixed and declared | Nothing |
| 19 | Turnover | proxied, never a multiplier | Circulation multiplier is not identified from public data | — |
| 20 | Prolog for ontology | constraint logic | Flow-type validity is a rule system; expressing it as rules is honest about what it is | — |
| 21 | Java for numerics | deterministic compute | Bit-reproducible curve and wedge construction | — |
| 22 | SQL for vintages | bi-temporal joins | As-of resolution is a set operation | — |
| 23 | Scala | NOT used | I do not write Scala. A repository claiming otherwise would fail its first code review | Learning it, then saying so |
| 24 | Findings before pipeline | forbidden | `FINDINGS.md` cannot exist before the analysis runs | — |
