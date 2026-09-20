"""Offline adversarial tests for the exact downloaded vintage, not an assumed lag."""
import json
from dataclasses import replace
from datetime import date

import pytest

from ingest.comtrade import ComtradeCopperFetcher
from scripts.run_ingest import _rows_to_observations
from warehouse.pit import PITStore

URL = "https://comtradeapi.un.org/public/v1/preview/C/M/HS"
FETCHED = date(2026, 9, 19)


def _rows():
    payload = json.dumps({"data": [
        {"period": 202404, "netWgt": 100000, "flowCode": "M"},
        {"period": 202404, "netWgt": 0, "flowCode": "X"},
    ]}).encode()
    return ComtradeCopperFetcher(["202404"], retrieved_on=FETCHED).parse(payload, URL)


def test_unknown_publication_uses_retrieval_bound_not_23_day_assumption():
    rows = _rows()
    assert rows[0]["publication_ts"] == FETCHED
    assert "publication_time_unknown" in rows[0]["quality_flags"]
    store = PITStore()
    for observation in _rows_to_observations(rows, FETCHED):
        store.append(observation)
    assert store.as_of("refined_copper_trade_m", date(2026, 4, 24)).empty
    assert len(store.as_of("refined_copper_trade_m", FETCHED)) == 1


def test_legacy_lagged_comtrade_rows_are_also_retrieval_gated():
    obs = _rows_to_observations(_rows(), FETCHED)[0]
    legacy = replace(
        obs, publication_ts=date(2024, 5, 23),
        quality_flags="comtrade_free_tier_stale_beyond_202412", vintage_id="legacy",
    )
    store = PITStore()
    store.append(legacy)
    assert store.as_of(obs.canonical_series_id, date(2024, 6, 1)).empty
    got = store.as_of(obs.canonical_series_id, FETCHED)
    assert got["available_ts"].iloc[0].date() == FETCHED
    assert got["publication_ts"].iloc[0].date() == date(2024, 5, 23)  # provenance retained


def test_repeated_nullable_channel_insert_is_idempotent():
    obs = _rows_to_observations(_rows(), FETCHED)[0]
    store = PITStore()
    store.append(obs)
    store.append(obs)
    assert store.conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 1


def test_conflicting_vintage_cannot_overwrite():
    obs = _rows_to_observations(_rows(), FETCHED)[0]
    store = PITStore()
    store.append(obs)
    with pytest.raises(ValueError, match="Conflicting vintage"):
        store.append(replace(obs, canonical_value=999.0))
    assert store.as_of(obs.canonical_series_id, FETCHED)["canonical_value"].iloc[0] == 100.0


def test_later_snapshot_does_not_leak_into_earlier_asof():
    obs = _rows_to_observations(_rows(), FETCHED)[0]
    store = PITStore()
    store.append(obs)
    store.append(replace(
        obs, publication_ts=date(2026, 9, 20), retrieval_ts=date(2026, 9, 20),
        canonical_value=120.0, vintage_id="next-snapshot",
    ))
    assert store.as_of(obs.canonical_series_id, FETCHED)["canonical_value"].iloc[0] == 100.0
    assert store.as_of(
        obs.canonical_series_id, date(2026, 9, 20)
    )["canonical_value"].iloc[0] == 120.0


def test_reported_zero_is_kept_by_parser():
    assert _rows()[1]["canonical_value"] == 0.0


def test_unknown_flow_is_rejected():
    payload = b'{"data":[{"period":202404,"netWgt":1000,"flowCode":"RE"}]}'
    with pytest.raises(ValueError, match="Unsupported trade flow"):
        ComtradeCopperFetcher(["202404"], retrieved_on=FETCHED).parse(payload, URL)


def test_unknown_release_is_not_measured_as_publication_lag():
    obs = _rows_to_observations(_rows(), FETCHED)[0]
    store = PITStore()
    store.append(obs)
    assert store.publication_lag(obs.canonical_series_id).empty


def test_same_vintage_refetched_keeps_first_retrieval():
    obs = _rows_to_observations(_rows(), FETCHED)[0]
    store = PITStore()
    store.append(obs)
    store.append(replace(obs, retrieval_ts=date(2026, 9, 20)))
    assert store.conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 1
    assert store.as_of(obs.canonical_series_id, FETCHED)["retrieval_ts"].iloc[0].date() == FETCHED


def test_payload_hash_distinguishes_same_day_vintages():
    first, second = _rows()[0], _rows()[0]
    first["payload_hash"], second["payload_hash"] = "first", "second"
    second["canonical_value"] = 120.0
    observations = _rows_to_observations([first, second], FETCHED)
    assert observations[0].vintage_id != observations[1].vintage_id
    store = PITStore()
    for obs in observations:
        store.append(obs)
    got = store.as_of(observations[0].canonical_series_id, FETCHED)
    assert len(got) == 1
    assert got["canonical_value"].iloc[0] == 120.0
