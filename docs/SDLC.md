# Development lifecycle and release criteria

This is a small research repository, not a production service. The lifecycle
below defines how changes are reviewed and reproduced; it does not imply that
separate review teams, deployment infrastructure, or production controls exist.

## Scope and ownership

The current deliverable is reproducible research infrastructure with partial
real-source ingestion and an exploratory monthly diagnostic. It is not a
validated trading signal, an identified causal effect, or a live trading system.
The repository maintainer owns both code changes and specification decisions.
Independent methodological review has not been established.

### Two separate specifications

| Specification | Purpose | Execution |
|---|---|---|
| `config/pcs.yaml` and `pcs.lock` | Preserve the original declared instrument | Original mixed-frequency scoring refuses to run without an explicit alignment policy |
| `config/pcs_monthly_exploratory.yaml` | Provisional descriptive monthly construction | `make monthly`; clearly labeled exploratory and unvalidated |

Changing the exploratory file does not change the original locked specification.
Conversely, keeping the lock unchanged does not make new exploratory choices
preregistered. The lock fingerprints listed configuration documents, not all
implementation code, data snapshots, or external historical facts.

## Change lifecycle

| Stage | Required work | Evidence |
|---|---|---|
| Define | State the economic object, intended output, and unacceptable failure | Issue or change description; `DATA_DICTIONARY.md` where applicable |
| Specify | Record aggregation, timing, missingness, and sample-selection choices before inspecting the resulting diagnostic | `DECISIONS.md`, explicitly labeled configuration |
| Implement | Keep source parsing, vintage selection, feature construction, and estimation separate | Focused code diff and descriptive commit |
| Test | Add a fixture that would fail under the defective assumption, not only a successful execution example | Offline regression tests |
| Review | Compare formulas with code; identify assumptions that unit tests cannot validate | Change notes and limitations below |
| Verify | Run tests, lint, type checks, determinism, and original-lock verification | Command output and CI status |
| Release | Confirm intended branch, inspect authorship and diff, then push normally | Commit hash; no routine force-push |
| Reassess | Revisit source coverage, revisions, and methodological limitations before using the output | Updated dated source-status notes, not a recycled success label |

Passing one stage is not evidence of the others. For example, synthetic effect
recovery tests verify selected estimator behavior, not the identification
assumptions of the copper study.

## Local verification

From the repository root after `make install`:

```bash
make test
make lint
make determinism
python -c "from pcs.lock import verify_lock; verify_lock()"
git diff --check
git diff --exit-code -- pcs.lock config/pcs.yaml config/events.yaml \
  config/exposure.yaml PREREGISTRATION.md
git status --short
```

The final diff check is appropriate for a change that promises to preserve the
original specification. A deliberate specification revision requires its own
decision record and review; it must not be hidden by regenerating the lock.

### Data-dependent checks

```bash
make ingest
make monthly
```

These commands have different evidentiary value from offline tests. Ingestion
uses a network and can encounter missing or inaccessible sources. A completed
monthly command establishes that the descriptive construction executed, not that
coverage was adequate, the score was predictive, or a causal effect was found.
`make realtime` currently fails deliberately on the original unresolved
mixed-frequency specification.

`make all` runs offline synthetic stages. It is not the complete empirical
pipeline. `make report` and `make robustness` remain blocked.

## Continuous integration

The GitHub Actions workflow performs offline checks on pushes, pull requests,
and a weekly schedule:

- **Lint and type checks:** `make lint` fails on errors.
- **Regression tests:** `make test` uses offline fixtures.
- **Lock verification:** Checks the original listed specification files.
- **Ordering check:** Compares the recorded introduction times of the
  preregistration document and research code. This is a repository-history
  consistency check, not proof of external preregistration or of what the author
  knew at that time.
- **Determinism:** Runs the seeded synthetic demonstration twice and compares
  output.

The weekly schedule does **not** probe source APIs or detect external schema
drift. Live contract monitoring, exchange-calendar reconciliation, and alerting
are not implemented.

## Test-to-requirement map

| Requirement | Evidence in tests | What remains unproven |
|---|---|---|
| Unknown Comtrade vintages cannot leak into earlier as-of dates | `test_comtrade_availability.py` | Actual source publication/revision history |
| A missing trade leg is not zero | `test_build.py` | Completeness and commodity specificity of downloaded trade data |
| Monthly aggregation precedes transformation and normalization | `test_build.py` | Economic validity of each provisional aggregation rule |
| Current partial months and thin months do not create usable features | `test_build.py` | Complete exchange or release calendars |
| Redundant residual calculation cannot count as robustness | `test_sensitivity.py` | A valid alternative factor model |
| Missing or dissenting sensitivity paths cannot imply agreement | `test_sensitivity.py` | Causal robustness of a real estimate |
| Routine tests do not rewrite the research lock | `test_lock.py` | External provenance and resistance to deliberate history alteration |
| CLI labels exploratory snapshot output and rejects unsupported original scoring | `test_realtime_cli.py` | Real-time tradability or deployment reliability |

## Data, access, and rollback

Raw payloads are content-addressed locally; observations carry payload hashes
and source URLs. Raw archives and SQLite databases are excluded from Git.
Consequently, a code checkout alone does not reproduce the exact downloaded
dataset. Data manifests, redistribution permissions, backup verification, and
dependency lockfiles remain future release work.

Do not add credentials, employer data, counterparty information, or licensed
payloads to the repository. Public accessibility does not establish unrestricted
redistribution rights.

For code rollback, prefer a normal revert commit over rewriting published
history. Preserve the original raw snapshot and correction explanation.
Do not change a historical value in place to obtain a desired result.
SQLite is a local reference store; disaster recovery and concurrent-writer
operation have not been validated.

## Outstanding risks and release blockers

| Risk | Current limit | Required improvement |
|---|---|---|
| Empirical identification | No usable channel-level outcome/exposure panel has been ingested | Establish valid data, treatment measurement, sample design, and confounder strategy |
| Source failure reporting | SHFE/Comtrade fetchers can skip failed requests; ingestion can return success despite incomplete results | Per-request status, explicit missing-period manifest, and failure thresholds |
| Availability | Comtrade is conservatively retrieval-gated; exact historical vintages are absent; SHFE assumes same-day release | Verify exact-value release metadata and revision history before historical PIT claims |
| Confounder diagnostics | Missing rungs can be skipped; `survives_ladder` does not enforce the full intended ladder; collinearity is not rejected | Explicit completeness status, rank checks, comparable samples, and proper inference |
| Placebo diagnostics | Absolute coefficient tolerance is scale-dependent; cuts without variation are skipped | Report every attempted cut, define inferential criteria and minimum support |
| Normalization/event design | Snapshot rolling moments are not an event-safe causal normalization protocol | Separately specify pre-event fitting windows for any empirical event study |
| Monthly features | Thresholds and aggregation are provisional; combined/cumulative releases need special treatment | Source-specific validation, calendar checks, and sensitivity analysis |
| Commodity scope | HS 7403 is broader than cathode-only refined copper | Validate narrower commodity mapping or retain an explicit broad-proxy interpretation |
| Reproducibility | Code and synthetic results are reproducible more readily than mutable live inputs | Versioned data manifests, dependency pinning, supported-environment tests |
| Production readiness | No deployment, operational SLOs, alerting, or recovery validation | Separate production design and operational testing if deployment becomes a goal |

These are not hidden implementation promises. They define why the repository
can be reviewed as ongoing research, but cannot yet be released as a validated
indicator or an empirical causal study.

## Database and security extension

The read-only audit and SQL reports are documented in `DATA_MODEL.md`; the bounded
security controls and residual risks are documented in `../SECURITY.md`. For a
change to these features, run `make lint`, `make test`, `make determinism`, then
stage the intended files and run `make security` against the Git index. Verify
SQL query assets are included in the built wheel when changing packaging.

For local-data acceptance, run `scripts.audit_warehouse` with an explicit as-of
date, expected raw series and optional archive directory. Inspect missing series
separately from integrity failures: an exit code of zero does not establish
adequate research coverage. Do not upload the local database or raw payloads to
make CI pass; CI uses synthetic fixtures for these checks.
