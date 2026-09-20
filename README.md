# invoice-economy-copper

### Can commodity data tell a tonne moving toward consumption from a tonne generating transactions?

When several datasets claim to measure the same economic phenomenon and disagree, the reflex is to treat the gap as error and clean it. This project asks whether the disagreement is itself information about market structure.

Chinese copper data bundles four different things into one word, "demand":

1. **End-use consumption** — copper physically transformed into wire, cable, grid, appliances
2. **Input-form demand** — whether that consumption is met by refined cathode or by scrap
3. **Commercial circulation** — repeated ownership and invoice turnover of the same physical tonne
4. **Financing activity** — metal and paperwork held to obtain credit rather than to be used

Most analysis collapses all four into a single signal.

## The instrument

The **Physical Consistency Score** asks whether claimed activity leaves matching footprints across independent datasets:

```
PCS_t = mean_z(physical block) − mean_z(commercial block)
```

| Regime | Reading |
|---|---|
| PCS ≫ 0 | Commercial activity is well supported by independent physical evidence |
| PCS ≈ 0 | Commercial and physical signals broadly agree |
| PCS ≪ 0 | Commercial activity is running ahead of its physical corroboration |

A negative score does **not** mean fraud, fake demand, or financing. It means the commercial signal cannot currently be reconciled with independent physical evidence. The research layer asks why; the indicator does not assert a cause.

**Market pricing series are deliberately excluded from the score.** Yangshan premium, Shanghai spot premium, and the SHFE–LME arbitrage state sit in a separate confirmation block and are tested as a *consequence* of PCS, never as an input. A physical premium can itself reflect genuine scarcity, so using premiums to build the predictor and then explaining premiums with it would be circular.

## Proposed validation setting

China's State Taxation Administration released the *Positive and Negative List for Taxpayer Compliance Invoicing* on **April 24, 2026** — 44 provisions organised around four-flow consistency, explicitly targeting circular invoicing, mutual invoicing, and artificially added transaction layers. Traders hit invoice quota limits, firms not engaged in physical trade largely suspended activity, and the Yangshan premium reached a record $119/t by July.

That episode motivates a proposed test environment, not established ground truth for this indicator. The event narrative and its source evidence require separate review before any empirical claim; this repository has not validated the score against the episode.

## Status

**Ongoing, unvalidated research.** Partial real-source ingestion and offline research infrastructure are implemented. A provisional monthly snapshot diagnostic is available; it is not a historically point-in-time backtest or a causal result. `FINDINGS.md` does not exist. Missing evidence is **inconclusive**, not a statistically established null effect.

| Component | State |
|---|---|
| Vintage store with as-of resolution | implemented, tested; unknown Comtrade release times use conservative retrieval bounds, not reconstructed historical vintages |
| Local warehouse SQL audit toolkit | implemented: inventory, shared as-of query, revision windows and duplicate-key checks; no cloud warehouse deployment |
| Evidence security checks | read-only audit, optional raw-byte hash verification, narrow Git-index secret/file checks; not a security certification |
| PCS construction and coverage metadata | implemented, tested |
| PCS sensitivity diagnostics | equal, inverse-variance and leave-one-out implemented; residual **disabled/not specified** because the previous formula duplicated the baseline |
| Exposure-intensity estimator, monotonicity, bootstrap, permutation, pre-trends | implemented, tested |
| Placebo dates, negative-control metals, confounder ladder | implemented, tested against synthetic data (`research/placebos.py`, `research/confounders.py`) — see "Open research gap" below for why real data can't drive them yet |
| Pre-registration lock mechanism | implemented, tested |
| Four-flow ontology | implemented |
| Live source ingestion | **partial and real** — SHFE and UN Comtrade are live; NBS, SHIBOR verified blocked from this build; LME in documented licensed fallback (see "Live ingestion status") |
| Original mixed-frequency PCS (`make realtime`, `make pcs`) | **blocked** until a reviewed frequency/alignment policy exists; no implicit 252-month normalization |
| Monthly snapshot diagnostic (`make monthly`) | **provisional**: explicit monthly features, 36-month rolling window, 24 prior valid months; not preregistered and not empirically validated |
| Findings | not started — by design, after the pipeline, and blocked on real per-channel data (see below) |

**A null result is a publishable outcome of this repository.** `PREREGISTRATION.md` names eight conditions under which the hypothesis is rejected, each mapped to the module that tests it. If any triggers, that is what gets written up.

## Live ingestion status

Status recorded during the September 19 build, not a claim that access conditions cannot change:

| Source | Status | Evidence |
|---|---|---|
| [SHFE](https://www.shfe.com.cn/eng/reports/) daily trading (`kx{date}.dat`) | **Live.** Real daily volume/open-interest/settlement data for copper, no auth needed | `ingest/shfe.py`; feeds `volume_oi_churn` (commercial block) |
| SHFE warehouse stocks (`dailystock`/`weeklystock`) | Not resolved | Every date/product-id pattern tried against the documented endpoint returned the site's HTML 404, not the JSON contract; `warrant_churn` and `deliveries_vs_warrant_change` remain unfilled |
| [UN Comtrade](https://comtrade.un.org) (trade proxy) | Historical HS-7403 import/export snapshots, including unwrought refined copper **and alloys** | Archive and default request range end at **2024-12**; this does not establish a universal free-tier ceiling or that paying would resolve it |
| [NBS](https://data.stats.gov.cn/english/) | **Verified blocked.** HTTP 403 (WAF) on every request, including a full browser session | `ingest/nbs.py`; removes `cable_wire_output`, `semis_production`, `refined_production` — half the physical block |
| [SHIBOR](https://www.shibor.org) | **Verified unreachable.** 403 / connection timeout, including a full browser session | `ingest/shibor.py`; does not feed core PCS, only the future confounder ladder |
| [LME](https://www.lme.com) | **Licensed, not held.** By design — see `PREREGISTRATION.md` §9 | `ingest/lme.py`; pipeline runs in documented SHFE-only fallback mode |

Run `make ingest`, then `make monthly` for the explicitly exploratory path. Default ingestion requests 36 months of trade history; a prior build archived additional older data, so a fresh database need not have the same history length. Only one declared physical input and one commercial input have data adapters producing observations in this build. Missing series stay in the coverage denominator. Fetching more years does not repair missing series or missing event-window data.

## Methodology corrections and provisional monthly clock

The September 20 correction replaces assumptions that passed tests but were not economically defensible. These corrections do not establish that the indicator works.

| Issue | Implemented correction | Remaining limit |
|---|---|---|
| 252 observations applied indiscriminately | Original mixed-frequency config fails closed; alternative `config/pcs_monthly_exploratory.yaml` aggregates raw inputs monthly **before** transforms and standardization | Alternative specification is exploratory, not a modification of the original lock |
| Assumed Comtrade release lag | No fixed 23-day date; snapshots become available no earlier than retrieval, with explicit unknown-publication flags | Actual release dates and historical vintages are still missing; retrieval is not a measured publication date |
| Missing trade leg treated as zero | Net imports require both legs in the same month; a genuinely reported zero remains valid | Missing leg produces a missing input and lowers PCS coverage |
| Redundant residual sensitivity | `(P-F)-(C-F)` check removed; residual status is `not_specified`, with no score | A distinct factor model and estimation window would need to be specified before reinstatement |

The monthly alternative uses **36 calendar months with at least 24 valid prior transformed values**, shifted by one month. The same clock applies to both blocks. This is an explicit provisional choice, not a parameter selected for a favorable result:

- Daily volume/OI churn: mean of observed daily ratios, requiring at least 15 observations per month. This is not monthly volume divided by month-end OI.
- Weekly turnover ratios/proxies: mean of observed weekly values, requiring at least 3 observations.
- Weekly inventory withdrawals: sum, requiring at least 3 observations. The source adapter and non-overlapping flow definition remain unresolved.
- Monthly quantities: the single monthly observation; duplicate observations in a month are rejected. Annual/cumulative NBS releases and January/February combined releases need source-specific handling before ingestion.
- Current partial calendar months are excluded. Empty months and insufficient-count months remain missing; reported zero flows remain zero. Minimum-count rules are quality screens, **not exchange-calendar completeness guarantees**.
- Missing calendar months remain gaps in transforms and rolling moments. Log differences of nonpositive net flows remain unavailable rather than being forced into a logarithm.

The CLI computes **snapshot history at one as-of date**. Even though normalization uses prior months, this is not a sequence of historically available trading signals. Comtrade snapshots downloaded after the event cannot become event-window information merely because their economic reference months are earlier. Legacy rows with the old assumed lag are also retrieval-gated, without rewriting the archived provenance. Intraday availability is not modeled.

The monthly clock cannot distinguish April 13 from April 24 within April. It does not inherit the original daily event-study estimand, event-window controls, or preregistration claim. Inverse-variance sensitivity uses the supplied sample and is descriptive, not a historical real-time weighting scheme. Sign agreement requires all declared variants and common valid periods; unavailable residual results cannot produce a robustness pass.

## Open research gap

The exposure/monotonicity analysis needs outcomes disaggregated by invoice-exposure channel, as declared in `config/exposure.yaml`. **This build has not identified or ingested a usable channel-level panel.** That is not proof that none exists anywhere. Aggregate exchange and trade data do not by themselves identify intermediary exposure. A suitable licensed dataset or a separately specified proxy design would need validation before estimation. Synthetic tests exercise the estimators; they do not establish identification, rule out confounding, or prove readiness for a real causal study.

## What is unusual here

**Pre-registration is a build dependency, not a promise.** `make estimate` refuses to run unless `pcs.lock` matches the commit that introduced `PREREGISTRATION.md`. If the instrument definition changed after pre-registration, the build fails and names the drift. Verify it yourself:

```bash
git log --diff-filter=A --format='%ad %h %s' -- PREREGISTRATION.md   # must be first
git log --diff-filter=A --format='%ad %h %s' -- research/            # must be later
cat pcs.lock
```

**As-of dates are explicit.** `as_of(series_id, asof)` selects eligible vintages using publication dates when verified, and conservative retrieval bounds for Comtrade or unknown-publication snapshots. Tests cover both verified revision history and the exclusion of later-downloaded Comtrade values from an earlier as-of date. A store can enforce metadata; it cannot manufacture missing historical vintages.

**The null case is tested.** `test_null_case_does_not_manufacture_significance` generates data with zero planted effect and asserts the pipeline declines to find one. Most projects test that a method detects an effect; testing that it refuses to invent one is what stops a pipeline from producing a result regardless of the data.

**Cross-source disagreement is flagged, never auto-corrected.** Conventional data-engineering instinct is wrong here: a pipeline that quietly reconciles sources to agree would erase the thing being measured.

## Database model and evidence protection

The [warehouse model and SQL guide](docs/DATA_MODEL.md) documents the actual
single-table SQLite schema, an ER diagram with external file/config relationships,
and executable SQL reports. The [security scope](SECURITY.md) describes read-only
audits, parameter binding, raw-payload integrity checks and Git-index hygiene.
These features protect and inspect evidence; they do not solve missing input
coverage, authenticate historical vintages or validate the research hypothesis.

```bash
make security
make audit ARGS="--db warehouse/data/pit_store.db --asof 2026-09-20 --series volume_oi_churn --series refined_copper_trade_m --series refined_copper_trade_x --series cable_wire_output --archive ingest/archive"
```

The audit requires an existing database. Explicitly list expected raw series so
absent inputs stay visible; the report does not infer PCS coverage. Review audit
outputs before sharing because revision history can contain licensed values.

## Reproduction

```bash
git clone https://github.com/fatehaszaman/invoice-economy-copper
cd invoice-economy-copper
make install
make test          # offline regression suite
make lint          # lint and type checks; failures return nonzero
make ingest        # fetch real SHFE + UN Comtrade data into the PIT store
make monthly       # EXPLORATORY monthly snapshot, not a historical backtest
make realtime      # intentionally refuses the unresolved original mixed-frequency config
# make all runs offline synthetic stages, NOT a completed empirical pipeline
```

Do not regenerate `pcs.lock` as a routine run step. Original config and lock are preserved; lock tests operate on temporary files. `make robustness` and `make report` intentionally fail because empirical validation and findings are unavailable. `make monthly` neither obtains a channel-level panel nor resolves licensed-data gaps.

## Reviewer guide

Read the status and methodology corrections above before interpreting any
output. Two technical documents describe the implementation without claiming
the missing empirical work is complete:

- [Development lifecycle and release criteria](docs/SDLC.md): change process,
  verification commands, test-to-requirement map, CI boundaries, and outstanding
  research and operational risks.
- [Algorithms and data contracts](docs/ALGORITHMS.md): pipeline boundaries,
  as-of selection, missing-leg handling, monthly construction, normalization,
  coverage, and sensitivity pseudocode.

In particular, source-failure reporting and the confounder/placebo diagnostics
need further hardening. The current test suite is evidence about specific
behaviors, not a certification of the full research design.

## Layout

```
config/          declared choices: series, exposure, PCS blocks, event dates
ingest/          fetcher contract with immutable content-addressed raw archival
ontology/        Prolog — four flow types, stock states, transition validity
warehouse/       point-in-time store (sqlite reference impl)
pcs/             the instrument: transform, standardise, blocks, coverage, score, lock
research/        exposure design, monotonicity, bootstrap, permutation, pre-trends
tests/           invariants, including the three that matter most

planned, not yet present — listed so the gap is visible rather than implied:
canonical/       units, calendars, identifier resolution
compute/         Java — curves, VAT-adjusted wedge, turnover proxies
simulate/        real-time observability and measurement uncertainty — NOT the causal test
monitor/         freshness, coverage, revisions, schema drift
```

## Method, in one paragraph

Treatment is **pre-existing invoice exposure intensity** per channel, not material type. A scrap-versus-cathode design was considered and rejected before estimation, because invoice friction pushes buyers *from* scrap *toward* cathode — making cathode an outcome of the treatment rather than a control. See `MISTAKES.md`. Because enforcement was national, no channel is untreated, so this is a dose-response design and the primary reported evidence is **monotonicity of effect across exposure intensity** rather than the magnitude of any single coefficient. The event is a window with two reference points: observable enforcement onset around April 13 and formal guidance on April 24. Inference uses block bootstrap and permutation of exposure labels; cluster-robust errors are reported as secondary, since few clusters make those asymptotics unreliable. Monte Carlo is used only to propagate measurement uncertainty through constructed physical quantities, never for inference on the causal coefficient.

## Data

Publicly accessible or individually licensed source data. No employer or confidential data of any kind.

| Source | Content | Live status |
|---|---|---|
| [SHFE](https://www.shfe.com.cn/eng/reports/) | Daily settlement, volume, open interest, weekly warehouse stocks | Daily settlement/volume/OI **live**; warehouse stocks not resolved (see above) |
| [LME](https://www.lme.com) | Reference prices, official stocks — [historical data is licensed](https://www.lme.com/Market-data/Accessing-market-data/Historical-data) | Licensed fallback, by design |
| [UN Comtrade](https://comtrade.un.org) (trade proxy) | HS-7403 imports/exports only; not scrap, semis or cathode-only data | Archived through 2024-12; exact historical vintages unverified |
| [NBS](https://data.stats.gov.cn/english/) | Refined production, cable and wire output, grid investment | Verified blocked (HTTP 403 WAF) |
| [SHIBOR](https://www.shibor.org) | Onshore rates, CNH forwards, USD funding | Verified unreachable |

Turnover is **proxied** from public measures. No circulation multiplier or empirical exposure-ordered effect is currently reported.

## Background reading on the event

- [STA release via People's Daily](https://finance.people.com.cn)
- [Four-flow consistency framework analysis](https://cwhkcpa.com/understanding-chinas-new-invoice-compliance-framework-positive-lists-negative-lists-and-four-flow-consistency/)
- [Shanghai Tax Bureau Q&A on compliant invoicing](https://shanghai.chinatax.gov.cn/xwdt/ztzl/zhl/yhysgj/nbzy/jsbwl/202608/t481253.html)
- [S&P Global: invoice quotas slow copper cargo flow](https://www.spglobal.com/energy/en/news-research/latest-news/metals/043026-china-tax-compliance-push-tightens-invoice-quotas-slows-copper-cargo-flow)
- [Mysteel: copper availability disrupted by tighter invoice management](https://www.mysteel.net/analysis/5127212-chinas-copper-availability-disrupted-by-tighter-invoice-management-)
- [Wood Mackenzie: China's invoice economy and implications for copper](https://www.woodmac.com/reports/metals-lme-asia-2026-chinas-invoice-economy-and-implications-for-copper-150469032)
- [Chinese commodity financing deals](https://macrosynergy.com/research/chinas-commodity-financing-deals/)

## Author

Fateha Zaman. Built from the physical consumption side: I started in quantitative development at MRS Industries, working within an existing engineering team, and became the first technical hire at BRB Cable Industries, building its technical infrastructure from zero close to the copper and aluminium and cable-manufacturing side of the business. The cathode-versus-scrap input decision in this analysis is something I have watched get made, not something I inferred from a paper.

No employer data, prices, volumes, counterparties, or internal figures appear anywhere in this repository. Mechanism knowledge is stated as industry practice.
