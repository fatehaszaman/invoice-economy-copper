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
| 25 | GACC substitute | UN Comtrade `public/v1/preview`, HS 7403 | GACC publishes no free machine-readable feed; Comtrade republishes the same declarations. Free tier verified capped at 2024-12 for China/HS7403 (`ingest/getDA` check, 2026-09-19) — does not cover the April 2026 event window | A licensed Comtrade key, or a GACC bulletin parser |
| 26 | NBS / SHIBOR live access | verified blocked, not attempted-and-abandoned | `data.stats.gov.cn` returns HTTP 403 (WAF) and `shibor.org` times out / 403s, from this build environment, via both `curl` and a full CDP browser session, checked 2026-09-19 | Running ingestion from a different network, or a licensed reseller (CEIC, Wind, Mysteel) |
| 27 | `pcs/sensitivity.py` "residual" construction | cross-sectional demeaning vs. the pooled physical+commercial mean per period | The config names the variant but does not specify its formula; this is a documented interpretation, not a recovered specification | Author confirms or replaces the formula before this variant is used in a reported result |

## Corrections recorded 2026-09-20

These entries supersede earlier implementation assumptions. The original
`config/pcs.yaml`, `config/events.yaml`, `config/exposure.yaml`,
`PREREGISTRATION.md`, and `pcs.lock` are unchanged. No empirical result has
been established or rescued by these changes.

| Decision | Old behavior | Corrected behavior | Reason / impact |
|---|---|---|---|
| Frequency | 252 native observations for daily and monthly inputs, then daily reindexing | Original mixed-frequency calculation refuses to run. Separate `pcs_monthly_exploratory.yaml` aggregates first, then uses a 36-calendar-month window with 24 prior valid transformed months | Comparable clock; explicit provisional alternative, not the preregistered daily event study |
| Monthly features | Unspecified | Daily ratio means (15 observations minimum), weekly ratio means or withdrawal sums (3 minimum), one observation for monthly series; omit partial current month | Transparent thresholds, not calibrated to output. Exchange completeness, cumulative NBS data and weekly flow overlap still require review |
| Comtrade availability | Month end plus 23 days | Unknown publication is flagged and bounded by retrieval; legacy snapshots are also retrieval-gated | Prevents later-downloaded values from masquerading as known historical vintages |
| Comtrade scope/access, superseding #25 | Claimed universal 2024-12 free-tier cap and pure refined-copper proxy | 2024-12 is the archived/default-request endpoint, not proof of a plan restriction. HS 7403 includes alloys | No claim that payment solves access; no cathode-only interpretation |
| Missing legs | Missing import or export treated as zero | Both legs must be observed in the same month; otherwise net observation missing | Coverage reflects missingness; true reported zeros remain usable |
| Residual, superseding #27 | Same common factor subtracted from both block means | Disabled as `not_specified`; no score or robustness pass | Algebraically cancels: `(P-F)-(C-F) = P-C`. Reinstatement requires a separate factor/loading/window specification |
| Sensitivity reporting | Missing variants could be skipped; leave-one-out paths bypassed floor | Explicit unavailable statuses, coverage-masked paths, common-period sign checks including each dropout | Inconclusive is not agreement, and diagnostic sign checks are not causal falsification verdicts |
| Lock handling | Tests and some routine make targets rewrote the lock | Tests use temporary files; routine scoring verifies rather than regenerates | Preserve provenance; code corrections do not establish that the exploratory policy was preregistered |

The earlier assertion that no public channel-level panel exists anywhere is
withdrawn. The supportable statement is that this build has not identified
or ingested a suitable panel. Lack of coverage is inconclusive, not a null
effect. The earlier daily-grid coverage counts are not validation evidence
for the corrected monthly method.
