# Offline evidence walkthrough

All values below are SYNTHETIC fixtures, not copper-market observations or findings.
Run `make demo` from the repository root to reproduce this output. No provider
credentials, market-data downloads or existing database are required.

## Observed behavior

| Scenario | Output | Interpretation |
|---|---|---|
| April production as of June 1 | 100.0 | Original vintage |
| April production as of June 20 | 110.0 | Revision now eligible |
| Trade rows before September retrieval | 0 | Unknown publication is retrieval-gated |
| January net imports; export explicitly zero | 500.0 | Reported zero is valid |
| February net imports; export absent | missing | Missing is not zero |
| Requested absent-series rows | 0 | Absence remains visible |
| Duplicate logical-key groups | 0 | No duplicate fixture vintages |
| Matching referenced payloads | 1 | Fixture bytes match their hash |
| Deliberately altered payload | hash_mismatch | Tampering is detected |
| DELETE through read-only connection | True | Write is blocked |
| Rows after attempted DELETE | 5 | All fixture rows remain |

## What this demonstrates

The demo calls the actual vintage store, net-import builder, SQL audit and
payload verifier. It creates five synthetic observation rows in a temporary
database, checks an archived fixture, deliberately changes that temporary
fixture, and attempts a write through a read-only connection. Temporary data
are removed when the run finishes; the local research archive is not touched.

The production fixture supplies simulated known release dates. The trade
fixture deliberately marks publication time unknown. These cases exercise
different availability rules; they do not authenticate any real release date.

This walkthrough does not fetch or parse live sources, build the complete
monthly PCS, establish historical source authenticity, or validate a causal
claim. Integrity checks are not evidence of adequate market-data coverage.

## Reproducibility check

`make demo-check` reruns the fixture and compares the full output with this
document. A mismatch fails the check; the expected output is never updated
automatically. Review behavioral changes before changing this snapshot.
