"""pcs/build.py: PIT store -> physical/commercial panels.

Uses a small hand-built PITStore rather than the live network sources, so
this suite runs offline and deterministically.
"""
from datetime import date

import pandas as pd
import pytest

from pcs.build import build_physical_commercial, net_refined_imports
from warehouse.pit import Observation, PITStore


def _obs(series, obj, obs_ts, value, unit="ratio", source="shfe"):
    return Observation(
        canonical_series_id=series,
        economic_object=obj,
        observation_ts=obs_ts,
        publication_ts=obs_ts,
        retrieval_ts=obs_ts,
        canonical_value=value,
        unit=unit,
        source=source,
    )


@pytest.fixture
def store():
    s = PITStore()
    # 70 daily churn observations -> just past min_periods for a short window.
    for i in range(70):
        d = date(2026, 1, 1) + pd.Timedelta(days=i)
        s.append(_obs("volume_oi_churn", "business_transaction", d, 1.0 + 0.01 * i))
    s.append(
        _obs("refined_copper_trade_m", "import_event", date(2026, 1, 31), 500_000.0,
             unit="tonnes", source="customs")
    )
    s.append(
        _obs("refined_copper_trade_x", "export_event", date(2026, 1, 31), -50_000.0,
             unit="tonnes", source="customs")
    )
    return s


def test_net_refined_imports_nets_the_two_legs(store):
    net = net_refined_imports(store, date(2026, 6, 1))
    assert net.loc[pd.Timestamp("2026-01-31")] == pytest.approx(450_000.0)


def test_build_physical_commercial_includes_every_configured_series_as_a_column(store):
    config = {
        "standardisation": {"window": 20},
        "blocks": {
            "physical": [{"id": "net_refined_imports", "transform": "diff"}],
            "commercial": [
                {"id": "volume_oi_churn", "transform": "diff"},
                {"id": "warrant_churn", "transform": "diff"},  # no data for this one
            ],
        },
    }
    phys, comm = build_physical_commercial(store, asof=date(2026, 6, 1), config=config)
    assert list(phys.columns) == ["net_refined_imports"]
    assert list(comm.columns) == ["volume_oi_churn", "warrant_churn"]
    # The series with no ingested data is present but entirely NaN, not dropped.
    assert comm["warrant_churn"].isna().all()
    # The series WITH data has at least one non-NaN z-score given enough history.
    assert comm["volume_oi_churn"].notna().any()


def test_build_physical_commercial_raises_when_store_is_empty():
    empty_store = PITStore()
    config = {
        "standardisation": {"window": 20},
        "blocks": {
            "physical": [{"id": "net_refined_imports", "transform": "diff"}],
            "commercial": [{"id": "volume_oi_churn", "transform": "diff"}],
        },
    }
    with pytest.raises(ValueError):
        build_physical_commercial(empty_store, asof=date(2026, 6, 1), config=config)
