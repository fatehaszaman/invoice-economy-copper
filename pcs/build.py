"""Assemble physical/commercial panels from the PIT store for `pcs.score`.

This is the integration layer between live ingestion (`ingest/`, loaded via
`scripts/run_ingest.py`) and the PCS construction machinery
(`pcs/transform.py`, `pcs/standardise.py`, `pcs/score.py`), which until now
only had synthetic-panel test coverage. Every series declared in
`config/pcs.yaml` gets a column, whether or not this build has live data for
it — see `build_block` for why an all-NaN column is correct, not a bug to
clean up.

Native-frequency windows must be explicitly specified for non-daily data.
Mixed-frequency scoring is refused until an alignment/release-calendar
policy is specified and reviewed; merely reindexing monthly values onto
daily dates is not such a policy. The locked config is not silently changed.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import yaml

from pcs.standardise import rolling_z
from pcs.transform import apply_transform
from warehouse.pit import PITStore

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "pcs.yaml"


class FrequencyPolicyError(ValueError):
    """The instrument does not specify a usable frequency policy."""


def standardisation_policy(config: dict) -> tuple[str, int, int]:
    """Validate the declared grid before reading any observations.

    A legacy window means daily observations only. For a single non-daily
    frequency, require window_by_frequency and min_periods_by_frequency.
    These are explicit alternative specifications, not inferred conversions
    of the locked daily window. Mixed frequencies deliberately fail closed.
    """
    items = [item for block in ("physical", "commercial") for item in config["blocks"][block]]
    frequencies = {item.get("frequency") for item in items}
    if None in frequencies or not frequencies:
        raise FrequencyPolicyError("Every PCS series must declare its frequency.")
    monthly = config.get("research_clock") == "monthly"
    if not frequencies <= {"daily", "weekly", "monthly"}:
        raise FrequencyPolicyError(f"Unsupported frequencies: {frequencies}")
    if monthly:
        for item in items:
            if item.get("monthly_aggregation") not in {"mean", "sum", "last"}:
                raise FrequencyPolicyError(f"Declare monthly_aggregation for {item['id']}")
            count = item.get("min_observations_per_month")
            if not isinstance(count, int) or count < 1:
                raise FrequencyPolicyError(f"Declare min_observations_per_month for {item['id']}")
    if len(frequencies) != 1 and not monthly:
        raise FrequencyPolicyError(
            "Mixed-frequency PCS is blocked: daily, weekly and monthly observations "
            "require an approved alignment/release-calendar policy. The locked "
            "252-day window cannot be applied as 252 monthly observations."
        )
    frequency = "monthly" if monthly else next(iter(frequencies))
    if frequency not in {"daily", "weekly", "monthly"}:
        raise FrequencyPolicyError(f"Unsupported frequency: {frequency}")
    spec = config["standardisation"]
    windows = spec.get("window_by_frequency", {})
    minima = spec.get("min_periods_by_frequency", {})
    if frequency == "daily":
        window = windows.get(frequency, spec.get("window"))
        minimum = minima.get(frequency, max(20, window // 4) if window else None)
    else:
        window, minimum = windows.get(frequency), minima.get(frequency)
    if (
        not isinstance(window, int)
        or not isinstance(minimum, int)
        or not 2 <= minimum <= window
    ):
        raise FrequencyPolicyError(
            f"Specify valid window_by_frequency and min_periods_by_frequency for {frequency}; "
            "both count native observations, with 2 <= min_periods <= window."
        )
    return frequency, window, minimum


def load_pcs_config(path: Path = CONFIG_PATH) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _native_series(store: PITStore, series_id: str, asof: date) -> pd.Series:
    """Raw canonical values for `series_id`, one row per period the source
    actually published, as known on `asof` (PIT-honest: never a value
    published after `asof`)."""
    df = store.as_of(series_id, asof)
    if df.empty:
        return pd.Series(dtype=float)
    s = df.set_index("observation_ts")["canonical_value"].sort_index()
    s.index = pd.DatetimeIndex(s.index)
    return s


def net_refined_imports(store: PITStore, asof: date) -> pd.Series:
    """China refined-copper net imports = imports + exports, where exports
    are already stored negative-signed (see `ingest/comtrade.py`).

    Live ingestion uses UN Comtrade HS 7403, a broad proxy including alloys,
    for the originally GACC-sourced input. The archived/default-request range
    ends at 2024-12; this does not establish a provider-wide access cap.
    See `ingest/comtrade.py` before interpreting it in the 2026 event window.
    """
    m = _native_series(store, "refined_copper_trade_m", asof)
    x = _native_series(store, "refined_copper_trade_x", asof)
    # Missing is not zero: both legs must be observed for the same month.
    return m.add(x).sort_index()


# Config series ids that are not a 1:1 read of a canonical_series_id in the
# PIT store, because they're derived from more than one raw series.
DERIVED = {
    "net_refined_imports": net_refined_imports,
}


def _raw_for_config_id(store: PITStore, series_id: str, asof: date) -> pd.Series:
    if series_id in DERIVED:
        return DERIVED[series_id](store, asof)
    return _native_series(store, series_id, asof)


def _series_z(
    store: PITStore, series_id: str, transform: str, asof: date, window: int,
    min_periods: int, item: dict, monthly: bool = False,
) -> pd.Series:
    raw = _raw_for_config_id(store, series_id, asof)
    if raw.empty:
        return pd.Series(dtype=float)
    if monthly:
        raw, _ = monthly_feature(raw, item, asof)
    transformed = apply_transform(raw, transform)
    return rolling_z(transformed, window=window, min_periods=min_periods)


def monthly_feature(raw: pd.Series, item: dict, asof: date) -> tuple[pd.Series, pd.Series]:
    """Aggregate raw observations BEFORE transforms and standardisation.

    Only completed calendar months enter. Counts accompany every feature;
    minimum counts are explicit exploratory thresholds, not a claim that an
    exchange calendar is complete. Monthly source gaps remain missing.
    """
    cutoff = pd.Timestamp(asof).to_period("M").start_time
    raw = raw.loc[raw.index < cutoff]
    if raw.empty:
        return pd.Series(dtype=float), pd.Series(dtype=int)
    if raw.index.has_duplicates:
        raise ValueError(f"Duplicate dates in {item['id']}")
    groups = raw.resample("ME")
    count = groups.count()
    if item["frequency"] == "monthly" and (count > 1).any():
        raise ValueError(f"Multiple observations in a monthly period for {item['id']}")
    aggregation = item["monthly_aggregation"]
    if aggregation == "sum":
        feature = groups.sum(min_count=1)
    elif aggregation == "mean":
        feature = groups.mean()
    elif aggregation == "last":
        feature = groups.last()
    else:
        raise FrequencyPolicyError(f"Unsupported monthly aggregation {aggregation!r}")
    return feature.where(count >= item["min_observations_per_month"]), count


def build_block(
    store: PITStore,
    block: list[dict],
    asof: date,
    common_index: pd.DatetimeIndex,
    window: int,
    min_periods: int,
    monthly: bool = False,
) -> pd.DataFrame:
    """One column per series DECLARED in config — present or not.

    `pcs.blocks.block_mean` computes coverage against the number of
    EXPECTED columns (`z.shape[1]`), which is exactly the point of that
    design: a thin period must look thin, not get a flattering denominator
    because an unavailable series was quietly dropped before it got there.
    Dropping the column here would silently defeat that guarantee.
    """
    cols = {}
    for item in block:
        sid = item["id"]
        z = _series_z(store, sid, item["transform"], asof, window, min_periods, item, monthly)
        cols[sid] = z.reindex(common_index)
    return pd.DataFrame(cols, index=common_index)


def build_physical_commercial(
    store: PITStore, asof: date, config: dict | None = None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (physical_z, commercial_z) ready for `pcs.score.compute_pcs`."""
    config = config or load_pcs_config()
    _, window, minimum = standardisation_policy(config)
    monthly = config.get("research_clock") == "monthly"

    all_ids = [item["id"] for blk in ("physical", "commercial") for item in config["blocks"][blk]]
    date_ranges = [
        pd.DatetimeIndex(_raw_for_config_id(store, sid, asof).index) for sid in all_ids
    ]
    date_ranges = [idx for idx in date_ranges if len(idx) > 0]
    if not date_ranges:
        raise ValueError(f"no live data in the PIT store as of {asof}")

    # Retain native observation dates; do not create artificial daily rows
    # for monthly/weekly data or forward-fill missing values.
    common_index = date_ranges[0]
    for idx in date_ranges[1:]:
        common_index = common_index.union(idx)
    common_index = common_index.sort_values()
    if monthly:
        last_complete = pd.Timestamp(asof).to_period("M").start_time - pd.Timedelta(days=1)
        common_index = pd.date_range(
            common_index.min().to_period("M").to_timestamp("M"),
            min(common_index.max().to_period("M").to_timestamp("M"), last_complete),
            freq="ME",
        )
        if common_index.empty:
            raise ValueError("No completed months available.")

    physical = build_block(
        store, config["blocks"]["physical"], asof, common_index, window, minimum, monthly
    )
    commercial = build_block(
        store, config["blocks"]["commercial"], asof, common_index, window, minimum, monthly
    )
    return physical, commercial
