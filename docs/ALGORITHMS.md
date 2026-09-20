# Algorithms and data contracts

This document describes the implemented descriptive data path and its research
boundaries. Pseudocode is explanatory, not a second implementation or a claim
that the unresolved empirical study has been completed.

## System boundary

```text
SHFE / Comtrade requests
          |
          v
raw payload archive ---------> payload hash + retrieval metadata
          |
          v
source-specific parsing
          |
          v
SQLite vintage store
          |
          v
as_of(snapshot_date)
          |
          +--> original mixed-frequency config: REFUSE unsupported scoring
          |
          v
exploratory monthly features
          |
          v
transform --> prior-month normalization --> block scores + coverage
          |
          v
descriptive snapshot diagnostic, explicitly unvalidated

Separate path:
synthetic channel panel --> estimator / inference tests

Missing connection:
validated real channel panel --> empirical causal analysis
```

The store uses economic reference dates and availability dates for different
purposes. A value can describe April while first becoming admissible to this
build in September. Labeling it with an April reference month does not make it
April information.

## Ingestion and provenance

Implemented primarily in `ingest/base.py`, `ingest/shfe.py`,
`ingest/comtrade.py`, and `scripts/run_ingest.py`.

```text
for each requested source endpoint:
    request with bounded retries
    if a payload is obtained:
        digest = SHA256(raw bytes)
        archive the bytes and retrieval metadata
        parse observations using the source's units and economic objects
        attach source URL and digest

    otherwise:
        current implementation may skip the request
        do not interpret omitted observations as zero

for each parsed observation:
    assign a vintage identifier
    append to the local store
    refuse a conflicting value under an existing vintage identifier
    retain first retrieval when the identical vintage is fetched again
```

The skipped-request behavior is an outstanding reliability risk, not a success
condition. See `SDLC.md` before treating an ingestion exit code as a completeness
check.

### SHFE daily feature

For valid copper contract rows in the daily payload:

```text
total_volume = sum(contract volume)
total_open_interest = sum(contract open interest)
if total_open_interest <= 0:
    no observation
else:
    daily_churn = total_volume / total_open_interest
```

This is exchange-traded turnover relative to open interest. It is a commercial
activity proxy, not an observed number of physical ownership transfers.

## As-of snapshot selection

Implemented in `warehouse/pit.py`.

```text
for each stored row in the requested series:
    if row is a Comtrade snapshot or has unknown-publication flags:
        available_date = max(publication_field, retrieval_date)
    else:
        available_date = publication_field

    retain only rows with available_date <= requested_asof

within each economic reference date and channel:
    choose latest available vintage
    break same-date ties by publication date, revision number, ingestion order
```

This rule also retrieval-gates legacy Comtrade rows carrying the old assumed
23-day release lag. It preserves their original stored provenance rather than
rewriting the rows.

New Comtrade rows use retrieval as a conservative value in the publication
field and include explicit unknown-publication flags. That field is therefore
not presented as a measured statistical release date; the publication-lag
diagnostic excludes these rows.

Selection is date-level, not intraday. Same-day tie resolution does not prove
which value could have been traded on at a particular time.

## Net trade with missingness

Implemented in `pcs/build.py::net_refined_imports`. Import observations are
positive; export observations are stored negative.

```text
for each reference month present in either trade leg:
    if import is missing OR export is missing:
        net_imports = missing
    else:
        net_imports = import + signed_export
```

A reported export of zero is an observation. An absent export is not.
An import from one month cannot be paired with an export from another month.
The HS-7403 aggregate remains a broader proxy than a cathode-only series.

## Exploratory monthly clock

Implemented in `pcs/build.py::monthly_feature` and declared in
`config/pcs_monthly_exploratory.yaml`.

```text
validate every series has:
    native frequency
    explicit monthly aggregation
    explicit minimum observation count

discard observations in the current partial calendar month

for each series and each calendar month:
    count observed, nonmissing values
    aggregate RAW values using the declared mean / sum / last rule
    if count is below that series' declared minimum:
        monthly_feature = missing
    if sum has no observations:
        monthly_feature = missing, NOT zero

create a common month-end index for all declared series
keep missing source columns and missing months
apply the declared transform to each monthly feature
```

Monthly source series allow only one observation per calendar month. Duplicate
source dates and multiple monthly observations are rejected rather than silently
averaged. Weekly records are assigned by their reference date; the provisional
withdrawal-sum rule still requires validation of non-overlapping flow periods.

| Feature type | Aggregation | Provisional minimum |
|---|---|---|
| Daily volume/OI ratio | Mean of observed daily ratios | 15 observations |
| Weekly ratios and proxies | Mean | 3 observations |
| Weekly withdrawals | Sum | 3 observations |
| Monthly quantities | Single monthly value | 1 observation |

These rules are not optimized thresholds or verified exchange calendars.
No forward-fill is used to make a thin month look complete.

## Transform and normalization

Implemented in `pcs/transform.py` and `pcs/standardise.py`.

```text
transformed = declared_transform(monthly_feature)
    log_diff: log(positive value) minus previous month's log value
    diff: value minus previous month's value
    pct: percentage change WITHOUT filling missing values
    level: unchanged numerical value

for month t:
    history = transformed observations in the preceding 36 calendar months
    if fewer than 24 valid values in history:
        z[t] = missing
    else:
        mu = mean(history)
        sd = sample standard deviation(history)
        if sd == 0:
            z[t] = missing
        else:
            z[t] = (transformed[t] - mu) / sd
```

The current observation never contributes to its own moments. A missing month
stays in the calendar window and does not become a zero or a carried value.
Nonpositive inputs to a log transform become unavailable.

This avoids self-normalization, but it does not reconstruct historical vintages.
All rows in this descriptive run come from a snapshot selected at one as-of
date. A causal event study additionally needs an event-safe estimation window;
this monthly diagnostic does not claim to supply one.

## Score and coverage

Implemented in `pcs/blocks.py`, `pcs/score.py`, and `pcs/coverage.py`.

```text
for each month:
    physical_mean = mean(available physical z-scores)
    commercial_mean = mean(available commercial z-scores)

    physical_coverage =
        available physical series / ALL declared physical series
    commercial_coverage =
        available commercial series / ALL declared commercial series

    raw_pcs = physical_mean - commercial_mean

    if either block has no data:
        confidence = unavailable
    else if both coverages >= 0.60:
        confidence = valid
    else:
        confidence = low_confidence
```

`compute_pcs` can retain a numerical low-confidence diagnostic alongside its
label. That number is not eligible primary evidence. The sensitivity wrapper
masks scores whose confidence is not `valid`; downstream consumers must not
discard the coverage columns and assume every numeric output is usable.

## Sensitivity diagnostics

Implemented in `pcs/sensitivity.py`.

```text
equal:
    compute coverage-qualified baseline score

inverse_variance:
    compute weights from the supplied sample
    if weights are undefined:
        return explicit unavailable status
    otherwise return coverage-qualified descriptive score

leave_one_out:
    drop each series in turn
    recompute the score and coverage on the reduced specification
    retain each qualifying path
    report range only where all dropout paths have valid values

residual:
    return not_specified and no scores
    never count common-factor subtraction as independent evidence

sign_agreement:
    require every declared variant to be specified and available
    require common valid periods
    include each leave-one-out path, not just its baseline central value
    compare signs, treating zero separately
```

The removed formula was `(P-F)-(C-F) = P-C`, so it did not measure robustness to
a common factor. A replacement would require a separately specified model with
series-specific loadings and an explicit estimation window.

Inverse-variance weights are sample-based, not a historically tradable weighting
rule. `sign_agreement = False` can mean incomplete evidence, not necessarily
disagreement or rejection of a causal hypothesis.

## Empirical boundary

The synthetic estimator demonstration is separate from the real-data snapshot.
It does not create channel-level outcomes from exchange or customs aggregates.
Neither completing the data path above nor passing its tests establishes an
exposure-response relationship, a profitable signal, or an absence of an effect.
