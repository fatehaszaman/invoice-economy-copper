"""Assemble physical/commercial panels from the PIT store for `pcs.score`.

This is the integration layer between live ingestion (`ingest/`, loaded via
`scripts/run_ingest.py`) and the PCS construction machinery
(`pcs/transform.py`, `pcs/standardise.py`, `pcs/score.py`), which until now
only had synthetic-panel test coverage. Every series declared in
`config/pcs.yaml` gets a column, whether or not this build has live data for
it — see `build_block` for why an all-NaN column is correct, not a bug to
clean up.

The `window=252` standardisation parameter is read from config, not
hardcoded here, so a change to the locked instrument definition is
reflected here automatically (and re-running `pcs/lock.py` would then be
required, per the project's own pre-registration discipline).
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

    This is this build's UN Comtrade proxy for the pre-registered
    GACC-sourced `net_refined_imports` series. It is real customs data, but
    the free tier is stale beyond 2024-12 — see `ingest/comtrade.py` module
    docstring before using this for anything covering the 2026 event window.
    """
    m = _native_series(store, "refined_copper_trade_m", asof)
    x = _native_series(store, "refined_copper_trade_x", asof)
    return m.add(x, fill_value=0.0).sort_index()


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
    store: PITStore, series_id: str, transform: str, asof: date, window: int
) -> pd.Series:
    raw = _raw_for_config_id(store, series_id, asof)
    if raw.empty:
        return pd.Series(dtype=float)
    transformed = apply_transform(raw, transform)
    return rolling_z(transformed, window=window)


def build_block(
    store: PITStore,
    block: list[dict],
    asof: date,
    common_index: pd.DatetimeIndex,
    window: int,
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
        z = _series_z(store, sid, item["transform"], asof, window)
        cols[sid] = z.reindex(common_index)
    return pd.DataFrame(cols, index=common_index)


def build_physical_commercial(
    store: PITStore, asof: date, config: dict | None = None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (physical_z, commercial_z) ready for `pcs.score.compute_pcs`."""
    config = config or load_pcs_config()
    window = config["standardisation"]["window"]

    all_ids = [item["id"] for blk in ("physical", "commercial") for item in config["blocks"][blk]]
    date_ranges = [
        pd.DatetimeIndex(_raw_for_config_id(store, sid, asof).index) for sid in all_ids
    ]
    date_ranges = [idx for idx in date_ranges if len(idx) > 0]
    if not date_ranges:
        raise ValueError(f"no live data in the PIT store as of {asof}")

    lo = min(idx.min() for idx in date_ranges)
    hi = max(idx.max() for idx in date_ranges)
    common_index = pd.date_range(lo, hi, freq="D")

    physical = build_block(store, config["blocks"]["physical"], asof, common_index, window)
    commercial = build_block(store, config["blocks"]["commercial"], asof, common_index, window)
    return physical, commercial
