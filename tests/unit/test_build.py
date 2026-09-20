"""pcs/build.py: PIT store -> physical/commercial panels.

Uses a small hand-built PITStore rather than the live network sources, so
this suite runs offline and deterministically.
"""
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from pcs.build import (
    FrequencyPolicyError,
    build_physical_commercial,
    load_pcs_config,
    monthly_feature,
    net_refined_imports,
    standardisation_policy,
)
from pcs.transform import apply_transform
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
            "physical": [{"id": "net_refined_imports", "transform": "diff", "frequency": "daily"}],
            "commercial": [
                {"id": "volume_oi_churn", "transform": "diff", "frequency": "daily"},
                {"id": "warrant_churn", "transform": "diff", "frequency": "daily"},
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
            "physical": [{"id": "net_refined_imports", "transform": "diff", "frequency": "daily"}],
            "commercial": [{"id": "volume_oi_churn", "transform": "diff", "frequency": "daily"}],
        },
    }
    with pytest.raises(ValueError, match="no live data"):
        build_physical_commercial(empty_store, asof=date(2026, 6, 1), config=config)


@pytest.mark.parametrize("present", ["m", "x"])
def test_missing_trade_leg_is_not_zero(present):
    store = PITStore()
    store.append(_obs(
        f"refined_copper_trade_{present}",
        "import_event" if present == "m" else "export_event",
        date(2026, 1, 31), 500.0 if present == "m" else -50.0,
    ))
    assert net_refined_imports(store, date(2026, 6, 1)).isna().all()


def test_reported_zero_export_is_valid(store):
    store.append(_obs("refined_copper_trade_m", "import_event", date(2026, 2, 28), 500.0))
    store.append(_obs("refined_copper_trade_x", "export_event", date(2026, 2, 28), 0.0))
    assert net_refined_imports(store, date(2026, 6, 1)).loc["2026-02-28"] == 500.0


def test_trade_legs_from_different_months_do_not_net():
    store = PITStore()
    store.append(_obs("refined_copper_trade_m", "import_event", date(2026, 1, 31), 500.0))
    store.append(_obs("refined_copper_trade_x", "export_event", date(2026, 2, 28), -50.0))
    assert net_refined_imports(store, date(2026, 6, 1)).isna().all()


def test_original_mixed_frequency_config_fails_before_reading_data():
    with pytest.raises(FrequencyPolicyError, match="Mixed-frequency PCS"):
        build_physical_commercial(PITStore(), date(2026, 6, 1), load_pcs_config())


def _single_frequency_config(frequency):
    return {
        "standardisation": {"window": 252},
        "blocks": {
            "physical": [{"id": "p", "transform": "level", "frequency": frequency}],
            "commercial": [{"id": "c", "transform": "level", "frequency": frequency}],
        },
    }


@pytest.mark.parametrize("frequency", ["weekly", "monthly"])
def test_non_daily_window_cannot_inherit_252(frequency):
    with pytest.raises(FrequencyPolicyError, match="window_by_frequency"):
        standardisation_policy(_single_frequency_config(frequency))


def test_explicit_monthly_window_is_used():
    config = _single_frequency_config("monthly")
    config["standardisation"].update(
        window_by_frequency={"monthly": 3}, min_periods_by_frequency={"monthly": 2},
    )
    store = PITStore()
    dates = pd.date_range("2025-01-31", periods=4, freq="ME")
    for sid in ("p", "c"):
        for day, value in zip(dates, [1.0, 2.0, 4.0, 8.0], strict=True):
            store.append(_obs(sid, "production_event", day.date(), value))
    physical, _ = build_physical_commercial(store, date(2026, 1, 1), config)
    assert len(physical) == 4
    assert physical["p"].iloc[:2].isna().all()
    assert physical["p"].iloc[2] == pytest.approx((4 - 1.5) / (0.5 ** 0.5))


def test_monthly_aggregation_precedes_transform_and_excludes_current_month():
    series = pd.Series(
        [1.0, 3.0, 10.0, 14.0, 999.0],
        index=pd.to_datetime(["2026-01-02", "2026-01-03", "2026-02-02",
                              "2026-02-03", "2026-03-01"]),
    )
    item = {"id": "x", "frequency": "daily", "monthly_aggregation": "mean",
            "min_observations_per_month": 2}
    feature, counts = monthly_feature(series, item, date(2026, 3, 20))
    assert feature.tolist() == [2.0, 12.0]
    assert counts.tolist() == [2, 2]
    assert apply_transform(feature, "diff").iloc[-1] == 10.0


def test_monthly_sum_does_not_turn_empty_month_into_zero():
    series = pd.Series([0.0, 5.0], index=pd.to_datetime(["2026-01-15", "2026-03-15"]))
    item = {"id": "x", "frequency": "weekly", "monthly_aggregation": "sum",
            "min_observations_per_month": 1}
    feature, counts = monthly_feature(series, item, date(2026, 4, 1))
    assert feature.iloc[0] == 0.0
    assert pd.isna(feature.iloc[1])
    assert counts.iloc[1] == 0


def test_thin_month_is_flagged_missing():
    series = pd.Series([1.0], index=pd.to_datetime(["2026-01-15"]))
    item = {"id": "x", "frequency": "daily", "monthly_aggregation": "mean",
            "min_observations_per_month": 15}
    feature, count = monthly_feature(series, item, date(2026, 2, 1))
    assert feature.isna().all()
    assert count.iloc[0] == 1


def test_pct_transform_does_not_fill_missing_trade_month():
    got = apply_transform(pd.Series([100.0, float("nan"), 150.0]), "pct")
    assert got.isna().all()


def test_exploratory_mixed_inputs_share_monthly_clock_and_prior_window():
    config = {
        "research_clock": "monthly",
        "standardisation": {
            "window_by_frequency": {"monthly": 3},
            "min_periods_by_frequency": {"monthly": 2},
        },
        "blocks": {
            "physical": [
                {"id": "p", "transform": "level", "frequency": "monthly",
                 "monthly_aggregation": "last", "min_observations_per_month": 1},
                {"id": "missing", "transform": "level", "frequency": "weekly",
                 "monthly_aggregation": "sum", "min_observations_per_month": 3},
            ],
            "commercial": [
                {"id": "c", "transform": "level", "frequency": "daily",
                 "monthly_aggregation": "mean", "min_observations_per_month": 2},
            ],
        },
    }
    store = PITStore()
    for month, value in enumerate([1.0, 2.0, 4.0, 8.0, 1000.0], start=1):
        end = (pd.Timestamp(2025, month, 1) + pd.offsets.MonthEnd()).date()
        store.append(_obs("p", "production_event", end, value))
        for day, delta in [(2, -0.5), (3, 0.5)]:
            store.append(_obs("c", "business_transaction", date(2025, month, day), value + delta))
    p, c = build_physical_commercial(store, date(2025, 5, 15), config)
    assert len(p) == 4  # May is partial and excluded.
    pd.testing.assert_index_equal(p.index, c.index)
    pd.testing.assert_series_equal(p["p"], c["c"], check_names=False)
    assert p["p"].iloc[2] == pytest.approx((4 - 1.5) / (0.5 ** 0.5))
    assert p["missing"].isna().all()
    # Later as-of dates may extend the snapshot; later values do not alter
    # the shifted moments of earlier months in this fixed-vintage fixture.
    extended, _ = build_physical_commercial(store, date(2025, 6, 1), config)
    pd.testing.assert_frame_equal(p, extended.loc[p.index])


def test_exploratory_config_requires_every_aggregation_rule():
    config = load_pcs_config(Path("config/pcs_monthly_exploratory.yaml"))
    assert standardisation_policy(config) == ("monthly", 36, 24)
    del config["blocks"]["commercial"][0]["monthly_aggregation"]
    with pytest.raises(FrequencyPolicyError, match="monthly_aggregation"):
        standardisation_policy(config)


def test_missing_trade_leg_reduces_monthly_block_coverage(store):
    from pcs.blocks import block_mean

    store.append(_obs("refined_copper_trade_m", "import_event", date(2026, 2, 28), 600.0))
    net = net_refined_imports(store, date(2026, 6, 1))
    _, coverage = block_mean(pd.DataFrame({"net": net}))
    assert coverage.loc["2026-01-31"] == 1.0
    assert coverage.loc["2026-02-28"] == 0.0
