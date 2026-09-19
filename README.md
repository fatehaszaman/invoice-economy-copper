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

## The validation

China's State Taxation Administration released the *Positive and Negative List for Taxpayer Compliance Invoicing* on **April 24, 2026** — 44 provisions organised around four-flow consistency, explicitly targeting circular invoicing, mutual invoicing, and artificially added transaction layers. Traders hit invoice quota limits, firms not engaged in physical trade largely suspended activity, and the Yangshan premium reached a record $119/t by July.

That episode is not the contribution. It is the test environment: a case where the ground truth was independently reported, against which a general indicator can be checked.

## Status

**Early build.** The infrastructure below is implemented and tested. Data ingestion against live sources, and therefore the empirical result, is not yet complete. `FINDINGS.md` does not exist yet and will not be written before the analysis runs.

| Component | State |
|---|---|
| Point-in-time store with as-of resolution | implemented, tested |
| Snowflake DDL for the vintage tables | not yet written |
| PCS construction and coverage metadata | implemented, tested |
| PCS sensitivity band across weighting and coverage-floor grids | not yet written |
| Exposure-intensity estimator, monotonicity, bootstrap, permutation, pre-trends | implemented, tested |
| Pre-registration lock mechanism | implemented, tested |
| Four-flow ontology | implemented |
| Live source ingestion | in progress |
| Findings | not started — by design, after the pipeline |

**A null result is a publishable outcome of this repository.** `PREREGISTRATION.md` names eight conditions under which the hypothesis is rejected, each mapped to the module that tests it. If any triggers, that is what gets written up.

## What is unusual here

**Pre-registration is a build dependency, not a promise.** `make estimate` refuses to run unless `pcs.lock` matches the commit that introduced `PREREGISTRATION.md`. If the instrument definition changed after pre-registration, the build fails and names the drift. Verify it yourself:

```bash
git log --diff-filter=A --format='%ad %h %s' -- PREREGISTRATION.md   # must be first
git log --diff-filter=A --format='%ad %h %s' -- research/            # must be later
cat pcs.lock
```

**There is no function that returns "the current value."** All research reads go through `as_of(series_id, asof)`, which selects the greatest publication timestamp at or before the as-of date. The latest vintage is reachable only by passing today's date explicitly, which makes the choice visible in code review. `tests/unit/test_pit.py` includes an adversarial case that a naive latest-value implementation passes everything else and fails only there.

**The null case is tested.** `test_null_case_does_not_manufacture_significance` generates data with zero planted effect and asserts the pipeline declines to find one. Most projects test that a method detects an effect; testing that it refuses to invent one is what stops a pipeline from producing a result regardless of the data.

**Cross-source disagreement is flagged, never auto-corrected.** Conventional data-engineering instinct is wrong here: a pipeline that quietly reconciles sources to agree would erase the thing being measured.

## Reproduction

```bash
git clone https://github.com/fatehaszaman/invoice-economy-copper
cd invoice-economy-copper
make install
make test          # 38 tests
make lock          # freeze the instrument
make all           # full pipeline
```

Where licensed LME history is unavailable, `make all` runs in documented SHFE-only fallback mode and labels affected results rather than crashing or silently substituting.

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

| Source | Content |
|---|---|
| [SHFE](https://www.shfe.com.cn/eng/reports/) | Daily settlement, volume, open interest, weekly warehouse stocks |
| [LME](https://www.lme.com) | Reference prices, official stocks — [historical data is licensed](https://www.lme.com/Market-data/Accessing-market-data/Historical-data) |
| [China Customs](http://english.customs.gov.cn) | Cathode, scrap, semis trade |
| [NBS](https://data.stats.gov.cn/english/) | Refined production, cable and wire output, grid investment |
| [SHIBOR](https://www.shibor.org) | Onshore rates, CNH forwards, USD funding |

Turnover is **proxied** from public measures and said to be proxied. No circulation multiplier is reported as a number; the reported result is a differential ordered by exposure intensity.

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
