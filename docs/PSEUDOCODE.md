# Pseudocode: follow the data pipeline

These algorithm cards explain the implemented data path in a consistent,
comment-first format. They are explanatory pseudocode, not a second executable
implementation. Follow the implementation links to inspect the actual functions;
run `make demo` to see selected safeguards operate on synthetic fixtures.

## Reading order

```text
Archive bytes -> select eligible vintages -> derive net imports
             -> aggregate monthly -> standardize using prior months
             -> calculate block means, score and coverage

Separate audit: re-hash archived bytes and report integrity failures
```

`MISSING` means an unavailable value, not zero. A reported zero is valid input.
`asof` is the information cutoff; `reference_date` is the economic period being
measured. They are not interchangeable.

Complexity notes use fixed-size identifiers and numeric fields. They describe
the stated operation, not the entire pipeline: network latency, retry delays and
repeated database calls are excluded unless named. Database bounds are
conservative logical-operation estimates, not promises about SQLite's query
plan or memory use. SQL may spill intermediate results to disk.

## Archive raw bytes by content hash

Implementation: [`Fetcher.store_raw`](../ingest/base.py).
This step receives an already-downloaded payload; it does not fetch the URL.

```text
# Raw Archive / SHA-256 Lookup
# Goal: preserve one blob per distinct payload and return its content identifier.
# Input: payload bytes, source URL, source name, license classification
# Output: SHA-256 digest; new blob and metadata files only if the blob is absent
# Time: O(B) for B payload bytes, including a new-file write when necessary
# Space: O(1) extra hashing state; caller already holds O(B) payload bytes
# Storage: O(B) new disk bytes when this payload is not already archived

FUNCTION archive(payload, source_url):
    digest = SHA256(payload)
    blob_path = archive_directory / (digest + ".bin")

    IF blob_path does not exist:
        WRITE payload TO blob_path
        WRITE {
            source,
            source_url,
            current_acquisition_time,
            byte_count(payload),
            license_class
        } TO metadata_path(digest)

    RETURN digest
```

Example: receiving identical bytes twice produces the same digest and does not
rewrite the existing metadata. This is content-addressed storage, not enforced
immutability: the current function does not recheck an existing blob or repair
a missing metadata sidecar, and the two writes are not an atomic transaction.

## Select the vintage available at a cutoff

Implementation: [`PITStore.as_of`](../warehouse/pit.py) and the shared
[`as_of.sql`](../warehouse/sql/as_of.sql).
The SQL uses bound parameters and a `ROW_NUMBER` window.

```text
# Vintage Selection / Filter + Partitioned Ranking
# Goal: choose one eligible vintage per reference date and channel.
# Input: observations, series_id, asof date, optional channel filter
# Output: selected observations with availability and provenance fields
# Time: O(N + V * log V), conservative scan-and-sort bound
# Space: O(V) logical intermediate rows; SQLite may use disk-backed sorting
# N = all warehouse rows; V = rows matching the series/channel filter

FUNCTION select_asof(observations, series_id, asof, channel_filter):
    candidates = rows whose series_id matches
    IF channel_filter is supplied:
        candidates = candidates whose channel matches

    FOR EACH row IN candidates:
        IF source_url identifies the current Comtrade API
           OR flags contain "publication_time_unknown"
           OR flags contain the legacy "comtrade_free_tier" marker:
            row.available_date = MAX(row.publication_date, row.retrieval_date)
        ELSE:
            row.available_date = row.publication_date

    eligible = candidates WHERE available_date <= asof
    groups = PARTITION eligible BY (reference_date, channel)

    FOR EACH group:
        SORT DESCENDING BY (
            available_date,
            publication_date,
            revision_number,
            insertion_order
        )
        EMIT first row

    RETURN emitted rows ordered by reference_date
```

Example: an April value of 100 published May 17 remains 100 at a June 1 cutoff,
even if a revision to 110 exists with a June 18 release date. An omitted channel
filter selects across all channels, not just the NULL channel; the current
returned columns do not expose the channel identifier, so this is not a complete
multi-channel panel interface.

Availability depends on stored dates and source/flag classification. This
algorithm enforces those inputs; it cannot authenticate missing release history.
Insertion order breaks otherwise tied vintages deterministically within a store.

## Derive net imports without inventing an export leg

Implementation: [`net_refined_imports`](../pcs/build.py).
Export values are already negative-signed by the trade adapter.

```text
# Net Imports / Date-Aligned Addition
# Goal: calculate net imports only when both legs exist for the same month.
# Input: eligible import and signed-export series
# Output: net-import series, retaining missing dates/legs
# Time: O(K * log K), conservative alignment-and-sort bound after database reads
# Space: O(K) for aligned values and output
# K = total rows returned across both trade legs
# As-of query costs are additional; this assumes at most one row per leg/date.

FUNCTION net_imports(store, asof):
    imports = select_asof(store, "refined_copper_trade_m", asof)
    exports = select_asof(store, "refined_copper_trade_x", asof)
    dates = SORTED UNION(imports.reference_dates, exports.reference_dates)

    FOR EACH date IN dates:
        IF import value is missing OR export value is missing:
            net[date] = MISSING
        ELSE:
            net[date] = imports[date] + exports[date]

    RETURN net
```

Example: imports of 500 and a reported export value of 0 produce 500.
Imports of 500 with no export observation produce `MISSING`, not 500.
The live HS 7403 input is a broad copper-and-alloys proxy, not cathode-only data.

## Convert raw inputs to completed monthly features

Implementation: [`monthly_feature`](../pcs/build.py).
Aggregation occurs before transforms and rolling standardization.

```text
# Monthly Features / Calendar Buckets + Minimum Counts
# Goal: put raw daily, weekly and monthly inputs on an explicit monthly clock.
# Input: dated values, aggregation rule, source frequency, minimum count, asof
# Output: monthly feature values and observed-value counts
# Time: O(D * log D + M), conservative bound allowing time-index sorting
# Space: O(D + M) for input grouping and monthly output
# D = input observations; M = calendar months spanned, including empty months

FUNCTION monthly_features(raw, rule, minimum_count, source_frequency, asof):
    cutoff = FIRST DAY OF MONTH CONTAINING asof
    raw = raw WHERE reference_date < cutoff
    IF raw is empty:
        RETURN empty feature series, empty count series
    IF raw contains duplicate dates:
        FAIL "duplicate dates"

    buckets = RESAMPLE raw BY calendar month, retaining empty months
    FOR EACH month IN buckets:
        count[month] = COUNT nonmissing values
        IF source_frequency == "monthly" AND count[month] > 1:
            FAIL "multiple monthly observations"

        IF rule == "mean":
            value = MEAN of nonmissing values
        ELSE IF rule == "sum":
            value = SUM if at least one value exists ELSE MISSING
        ELSE IF rule == "last":
            value = LAST nonmissing value, or MISSING
        ELSE:
            FAIL "unsupported aggregation"

        feature[month] = value IF count[month] >= minimum_count ELSE MISSING

    RETURN feature, count
```

Example: with a minimum count of 15, fourteen daily observations leave that
month's feature missing. An empty month is never manufactured as a zero sum,
and the current partial month is excluded even if it has some observations.
Count thresholds are provisional screens, not exchange-calendar completeness.

## Standardize using only prior positions

Implementation: [`rolling_z`](../pcs/standardise.py).
The caller supplies transformed values on the chosen calendar grid.

```text
# Rolling Z-Score / Prior-Window Mean and Sample Standard Deviation
# Goal: prevent a value from contributing to its own normalization moments.
# Input: transformed series x, window W, minimum valid observations R
# Output: one standardized value or MISSING per position
# Time: O(T * W) for the direct window-scan pseudocode below
# Space: O(T) output plus O(W) temporary window values
# T = positions on the input grid, including missing calendar positions
# Actual code delegates to pandas rolling aggregations, not this nested loop.

FUNCTION prior_window_zscore(x, W, R):
    FOR t FROM 0 TO LENGTH(x) - 1:
        prior = x[MAX(0, t - W) : t]    # excludes x[t]
        observed = prior WITH missing values removed

        IF x[t] is missing OR COUNT(observed) < R:
            z[t] = MISSING
            CONTINUE

        mean = AVERAGE(observed)
        sigma = SAMPLE_STANDARD_DEVIATION(observed)  # divisor: count - 1
        IF sigma is missing OR sigma == 0:
            z[t] = MISSING
        ELSE:
            z[t] = (x[t] - mean) / sigma

    RETURN z
```

Example: current value 4 with prior values 1 and 2 gives
`(4 - 1.5) / sqrt(0.5)`, provided the configured minimum is met.
Missing months still occupy positions in the window; they do not cause the
window to reach farther back for more observations. Prior-window normalization
does not itself make later-retrieved snapshots historically available.

## Calculate the score and preserve coverage

Implementation: [`block_mean`](../pcs/blocks.py),
[`compute_pcs`](../pcs/score.py) and
[`label_confidence`](../pcs/coverage.py).
This card covers equal weighting, not the separate inverse-variance variant.

```text
# PCS / Available-Value Means + Fixed Coverage Denominators
# Goal: compare the two block averages without hiding absent expected series.
# Input: standardized physical and commercial panels, coverage floor F
# Output: score, both block averages, both coverages, confidence label
# Time: O(T * S) once the panels share a date index
# Space: O(T * S) for the vectorized implementation's masks/intermediates
# T = dates; S = total declared physical and commercial series
# Any database, normalization and date-index alignment costs are additional.

FUNCTION score_blocks(physical, commercial, F):
    FAIL IF either block declares zero columns

    FOR EACH date:
        FOR EACH block IN [physical, commercial]:
            expected = NUMBER OF DECLARED COLUMNS
            observed = nonmissing values at this date
            coverage[block] = COUNT(observed) / expected
            mean[block] = AVERAGE(observed) IF any exist ELSE MISSING

        pcs = mean[physical] - mean[commercial]  # missing propagates
        IF both coverages >= F:
            confidence = "valid"
        ELSE IF either coverage == 0:
            confidence = "unavailable"
        ELSE:
            confidence = "low_confidence"

        EMIT pcs, both means, both coverages, confidence
```

Example: three available physical inputs out of six declared inputs give
coverage `0.50`, regardless of how many columns contain data elsewhere.
The raw scorer can emit a number labeled `low_confidence`; coverage-qualified
consumers must apply their documented filtering. The label `valid` means the
coverage threshold passed, not that the economic hypothesis was validated.

## Verify archived payload integrity

Implementation: [`verify_archives`](../warehouse/audit.py).
This is separate from the archive-writing routine.

```text
# Payload Audit / Identifier Validation + Streaming Hash Comparison
# Goal: detect invalid references, missing files and altered payload bytes.
# Input: read-only observation store, existing archive directory
# Output: a status for each distinct referenced hash, including missing hashes
# Time: O(N * log N + B), conservative DISTINCT/sort plus byte-reading bound
# Space: O(N + H) logical query state/results plus a fixed-size stream buffer
# N = warehouse rows; H = distinct hash references; B = total bytes examined
# SQLite may spill DISTINCT/sort state; payloads are not loaded whole into RAM.

FUNCTION verify_payloads(store, archive_directory):
    hashes = SELECT DISTINCT payload_hash FROM observations ORDER BY payload_hash

    FOR EACH hash IN hashes:
        IF hash is not exactly 64 lowercase hexadecimal characters:
            EMIT redacted identifier, "invalid_or_missing_hash"
            CONTINUE

        path = archive_directory / (hash + ".bin")
        IF path is a symbolic link:
            EMIT hash, "symlink_rejected"
        ELSE IF path is not a regular file:
            EMIT hash, "missing"
        ELSE:
            TRY:
                actual = STREAMING_SHA256(path)
                EMIT hash, ("ok" IF actual == hash ELSE "hash_mismatch")
            ON file-read error:
                EMIT hash, "unreadable"
```

Example: changing one byte in the temporary demo fixture produces
`hash_mismatch`. A match proves consistency with the stored hash, not authentic
source publication; changing both database and payload could defeat this check.
Metadata sidecars, unreferenced files and concurrent malicious path replacement
are outside the current verifier's protection.

## Continue into the implementation

- **[Offline walkthrough](DEMO.md):** computed synthetic examples you can reproduce.
- **[Algorithms and data contracts](ALGORITHMS.md):** integration boundaries,
  transformations, sensitivity rules and fuller pipeline pseudocode.
- **[Warehouse model](DATA_MODEL.md):** the ER diagram, SQL query inventory and grain.
- **[Research context](RESEARCH_CONTEXT.md):** why the economic interpretation
  remains provisional even when the software checks pass.
