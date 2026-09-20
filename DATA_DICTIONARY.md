# Data dictionary

Every field a reported number depends on, with its economic object, unit,
publication lag, and known failure modes.

## Economic objects

A row's `economic_object` declares what real-world thing it measures. Rows with
different objects cannot be summed. This is enforced in `ontology/flows.pl` and
tested in `tests/unit/test_pit.py::test_every_row_declares_its_economic_object`.

| Object | Meaning | Recurring? | Carries tonnage |
|---|---|---|---|
| `invoice_event` | A tax invoice issued | yes | no |
| `business_transaction` | Commercial agreement | yes | no |
| `ownership_transfer` | Title change | yes | no |
| `funds_transfer` | Payment | yes | no |
| `financing_event` | Metal or paper pledged for credit | yes | no |
| `physical_movement` | Metal physically relocated | yes | yes |
| `inventory_state` | Stock at a point in time | yes | yes |
| `production_event` | Refined metal produced | yes | yes |
| `consumption_event` | Metal transformed into product | **no — terminal** | yes |
| `import_event` / `export_event` | Cross-border movement | yes | yes |
| `price_observation` | Quoted or settled price | yes | no |

Only `consumption_event` terminates a tonne's life. Every other object may
recur arbitrarily many times for the same physical metal. That asymmetry is the
entire reason "demand" is ambiguous in this market.

## Observation schema

| Field | Type | Meaning |
|---|---|---|
| `canonical_series_id` | text | Stable internal identifier |
| `economic_object` | enum | What the row measures; validated against the ontology |
| `observation_ts` | date | The period the value describes |
| `publication_ts` | date | Verified release date when known; new unknown-publication snapshots use retrieval as a flagged conservative availability bound |
| `available_ts` | date, read output | Effective availability used by `as_of`; includes retrieval gating of legacy Comtrade rows |
| `retrieval_ts` | date | When this pipeline fetched it |
| `canonical_value` | float | Value in canonical units |
| `unit` | text | tonnes, CNY/t, USD/t, index |
| `source` | enum | shfe, lme, customs, nbs, shibor |
| `revision_number` | int | 0 = first print |
| `vintage_id` | text | Explicit vintage identifier; live adapters use `publication_ts#payload_hash` |
| `payload_hash` | text | SHA-256 of the archived payload this came from |
| `quality_flags` | text | Semicolon-separated limitations, including unknown publication time and unverified historical vintage |

`publication_ts` must not precede `observation_ts`. Enforced at construction.

## Publication lag

`publication_lag()` excludes Comtrade and explicitly unknown-publication
snapshots: acquisition delay is not publication delay. The calendar ranges
below are contextual expectations, not dates assigned to downloaded values.
Verified release metadata for the exact vintage is required to establish
historical availability.

| Series | Frequency | Typical lag | Revised |
|---|---|---|---|
| SHFE settlement, volume, OI | daily | same day | rarely |
| SHFE warehouse stocks | weekly | 0–1 day | rarely |
| LME official stocks | daily | 1 day | rarely |
| China Customs trade | monthly | 20–25 days | yes |
| NBS refined production | monthly | 15–18 days | **yes, materially** |
| NBS cable and wire output | monthly | 15–18 days | yes |
| Grid investment | monthly | 20–30 days | yes |
| SHIBOR | daily | same day | no |

NBS monthly production revisions are the main look-ahead risk in this project,
which is why the adversarial PIT test is built around exactly that case.

## Stock states

A tonne occupies exactly one state at a time. Summing across states
double-counts the same metal. See `ontology/inventory.pl`.

`bonded` → `customs_declared` → {`on_warrant`, `off_warrant`} → `in_transit`
→ `at_fabricator` → `consumed`

`bonded` metal is VAT-exempt and pre-customs. Comparing bonded and
customs-declared quantities without acknowledging that difference is a
category error, and the comparison is refused rather than adjusted silently.

## Known failure modes

| Mode | Handling |
|---|---|
| Chinese New Year distortion | Not resolved by the exploratory monthly aggregation; combined Jan–Feb source releases need an explicit adapter policy |
| NBS revisions | Full vintage history retained; research reads as-of only |
| Unit inconsistency (dmt vs wmt) | Canonicalised at ingest; conversion declared |
| VAT-inclusive vs exclusive prices | Treated as distinct series, never mixed |
| Bonded vs onshore stocks | Distinct states; never summed |
| Licensed LME history absent | Documented SHFE-only fallback; affected results labelled |
| Source schema drift | Not monitored live; scheduled CI runs offline tests only |
| Cross-source disagreement | Flagged with both values preserved; never auto-reconciled |
| Missing import/export leg | Net imports missing; reported zero is retained, never inferred |
| Unknown Comtrade release/vintage | Retrieval-bounded; historical PIT claim withheld |
| Mixed frequencies | Original config blocked; separate exploratory monthly rules in README/config |
| HS-7403 scope | Includes unwrought refined copper and alloys; broader than a cathode-only measure |
