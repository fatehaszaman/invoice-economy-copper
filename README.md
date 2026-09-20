# China copper-market research pipeline

Can commodity data distinguish physical consumption from repeated commercial
transactions? This project investigates that question through a Python/SQL
pipeline for source ingestion, vintage-aware storage, data-quality audits and
exploratory comparisons of physical and commercial activity.

**Status: ongoing, unvalidated research.** The working deliverable is research
infrastructure with partial real-source data and a separate synthetic estimator
demonstration. It is not a validated trading signal, a causal finding or a
production system.

For a concrete example, read the [offline evidence walkthrough](docs/DEMO.md)
or run `make demo` after installation. It exercises revision timing, missing
trade legs, read-only SQL access and detection of a changed raw file using
synthetic fixtures and the actual project functions.

## What is implemented

| Component | Evidence | Boundary |
|---|---|---|
| Source ingestion | SHFE daily and UN Comtrade monthly adapters; raw payload hashes and acquisition metadata | Partial coverage; skipped requests need better failure reporting |
| Vintage-aware SQLite store | Explicit as-of reads, retained revisions and adversarial look-ahead tests | Enforces supplied metadata; does not authenticate historical release dates |
| SQL audits and data model | Inventory, revision windows, duplicate-key checks, read-only CLI and ER diagram | Local analytical store, not a deployed cloud warehouse |
| Monthly exploratory score | Aggregate before transforming; prior-month normalization; explicit missingness and coverage | Provisional specification, not the original preregistered daily study |
| Research estimators | Synthetic exposure-intensity, monotonicity, pre-trend, bootstrap and permutation tests | No usable real channel-level outcome panel has been ingested |
| Evidence protection | Optional raw-file hash checks, parameterized queries and Git-index hygiene | Bounded controls, not a security certification |

The design keeps economic reference dates separate from the dates information
becomes available. Missing observations stay missing, and later-retrieved trade
snapshots cannot become earlier historical information by changing their labels.

```text
SHFE / Comtrade
  -> raw payloads + acquisition metadata
  -> canonical observations + retained vintages
  -> explicit as-of read
  -> monthly features + coverage
  -> exploratory diagnostic

Separate: synthetic channel panel -> estimator and inference demonstration
Missing:  validated real channel panel -> empirical causal analysis
```

## Run the offline demonstration

Use Python 3.11 or later, Git and Make. Dependency installation requires network
access; the checks and synthetic demonstration below do not fetch market data or
require provider credentials.

```bash
git clone https://github.com/fatehaszaman/invoice-economy-copper.git
cd invoice-economy-copper
python3 -m venv .venv
source .venv/bin/activate
make install
make demo
make demo-check
make test
make lint
make estimate
make determinism
make security
```

`make estimate` verifies the original specification lock, then prints a planted
effect example and a zero-effect example, both explicitly labeled synthetic.
It is a demonstration, not the test-suite pass/fail gate: `make test` supplies
regression assertions. `make determinism` compares two fixed-seed synthetic runs.
Do not regenerate `pcs.lock` as an installation or routine execution step.

The [CI workflow](.github/workflows/ci.yml) runs tests, lint/type checks, lock
verification, the demo-output comparison, determinism and repository hygiene.
These checks validate selected software behaviors, not economic identification
or live-source completeness.

## Research question and score interpretation

The working hypothesis distinguishes end-use consumption, refined-versus-scrap
input choices, repeated ownership/invoice turnover, and financing activity.
The proposed Physical Consistency Score is a descriptive contrast:

```text
PCS = average standardized physical inputs
    - average standardized commercial inputs
```

| Sign | What the calculation establishes |
|---|---|
| Positive | The physical-block average is higher than the commercial-block average |
| Near zero | The block averages are similar, possibly despite offsetting individual series |
| Negative | The commercial-block average is higher than the physical-block average |

The sign alone does not establish physical corroboration, fraud, financing,
causality or predictive power. For example, physical and commercial averages of
`-1` and `-2` produce a positive score even though both are below their own
historical means. Economic interpretation requires additional evidence.

Price premiums and arbitrage measures are excluded from the score. Examining
them as separate outcomes is a proposed validation step, not a completed result.
The China invoice-enforcement setting and candidate event dates also require
independent source review before empirical use.

## Live ingestion status

The following reflects this build's recorded acquisition work, not a guarantee
of continuing provider access. Raw data and the local database are not committed.

| Input | Available in this build | Main limit |
|---|---|---|
| SHFE daily copper trading | Adapter and archived observations; volume/open-interest activity proxy | Does not measure physical ownership transfers; warehouse-stock inputs remain unresolved |
| UN Comtrade HS 7403 trade | Import and export snapshots | Includes alloys; archived/default-request history ends at 2024-12; exact historical vintages unverified |
| NBS production / SHIBOR rates | Unavailable from the recorded build environment | Source access and parsers remain unresolved |
| LME licensed history | Not held | Missing licensed inputs remain absent |

To attempt new acquisition and the provisional monthly diagnostic:

```bash
make ingest
make monthly
make audit ARGS="--db warehouse/data/pit_store.db --asof 2026-09-20 --series volume_oi_churn --series refined_copper_trade_m --series refined_copper_trade_x --series cable_wire_output --archive ingest/archive"
```

Choose the audit date deliberately and list the expected raw inputs, including
absent ones. Fresh ingestion may produce different history and incomplete
coverage; successful acquisition or hash checks do not establish enough data for
a research conclusion. The monthly output is snapshot history at one as-of
date, not a sequence of historically tradable signals.

## Open research gap

The current data do not support an empirical channel-level exposure study.
There is no reported copper finding, and insufficient coverage is inconclusive,
not a demonstrated null effect. `FINDINGS.md` does not exist.

Four methodological corrections are implemented: comparable monthly treatment
in a separate exploratory specification, retrieval bounds for unknown Comtrade
publication times, missing net imports when either leg is absent, and removal
of a redundant common-factor subtraction. The original mixed-frequency
specification remains frozen and cannot be scored without a reviewed policy.
The residual sensitivity is explicitly unavailable, not counted as a pass.

`make realtime` and `make pcs` intentionally refuse that unresolved original
specification. `make robustness` and `make report` also fail because a complete
empirical validation/reporting path is unavailable; they are not part of the
offline quickstart.

## Technical documentation

- **[Offline evidence walkthrough](docs/DEMO.md):** reproducible synthetic
  examples and checked-in output, including deliberate failure cases.
- **[Research context and methodology](docs/RESEARCH_CONTEXT.md):** source-access
  history, provisional aggregation rules, corrections and proposed study design.
- **[Warehouse model and SQL guide](docs/DATA_MODEL.md):** observation grain,
  ER diagram, actual versus logical relationships and executable audit queries.
- **[Algorithms and data contracts](docs/ALGORITHMS.md):** pipeline pseudocode,
  vintage selection, missing-leg logic, normalization and coverage.
- **[Development lifecycle](docs/SDLC.md):** verification steps, release criteria
  and unresolved research/operational risks.
- **[Security scope](SECURITY.md):** implemented safeguards and their limits.
- **[Data dictionary](DATA_DICTIONARY.md) and [decision log](DECISIONS.md):**
  measurement definitions and original choices with dated corrections.

## Author and motivation

Fateha Zaman. My quantitative-development work at MRS Industries and engineering
work at BRB Cable Industries put me close to copper, aluminium and cable
manufacturing. The distinction between material consumption and transaction
activity motivates the question; professional context is not evidence for the
proposed statistical interpretation.

No employer data, prices, volumes, counterparties or internal figures are
included. The project uses independently acquired source data and synthetic
fixtures; the repository does not redistribute the local raw-data archive.
