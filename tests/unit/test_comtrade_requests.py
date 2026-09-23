"""Offline request reporting and date-selection regressions; no live downloads."""
import argparse
import json
from datetime import date
from urllib.parse import parse_qs, urlsplit

import pytest

from ingest.comtrade import ComtradeCopperFetcher
from scripts import run_ingest
from warehouse.pit import PITStore


def _payload(flow="M", weight=1000):
    return json.dumps({"data": [
        {"period": 202412, "flowCode": flow, "netWgt": weight},
    ]}).encode()


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Network access is forbidden in these tests")

    monkeypatch.setattr("ingest.base.Fetcher._get", forbidden)
    monkeypatch.setattr("time.sleep", lambda _: None)


def _fetcher(tmp_path, monkeypatch, responses):
    fetcher = ComtradeCopperFetcher(
        ["202412"], archive=tmp_path / "archive", retrieved_on=date(2026, 9, 23),
    )

    def fetch(url, **kwargs):
        flow = parse_qs(urlsplit(url).query)["flowCode"][0]
        result = responses[flow]
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(fetcher, "fetch_with_retry", fetch)
    return fetcher


def test_failed_request_preserves_successful_rows_and_reason(tmp_path, monkeypatch):
    fetcher = _fetcher(tmp_path, monkeypatch, {
        "M": _payload(), "X": RuntimeError("retry budget exhausted"),
    })
    rows = fetcher.fetch_all()
    assert len(rows) == 1
    assert rows[0]["canonical_value"] == 1.0
    assert rows[0]["payload_hash"]
    assert [r.status for r in fetcher.request_results] == ["DATA", "FAILED"]
    failure = fetcher.request_results[1]
    assert (failure.period, failure.flow) == ("202412", "X")
    assert "retry budget exhausted" in failure.error
    summary, failed = run_ingest._comtrade_summary(fetcher)
    assert failed
    assert summary.startswith("PARTIAL")
    assert "failed=1" in summary


def test_empty_response_is_not_zero_or_failure(tmp_path, monkeypatch):
    fetcher = _fetcher(tmp_path, monkeypatch, {
        "M": b'{"data":[]}', "X": _payload("X", 0),
    })
    rows = fetcher.fetch_all()
    assert len(rows) == 1
    assert rows[0]["canonical_value"] == 0.0
    assert [r.status for r in fetcher.request_results] == ["EMPTY", "DATA"]
    summary, failed = run_ingest._comtrade_summary(fetcher)
    assert not failed
    assert "empty=1" in summary


@pytest.mark.parametrize("payload", [
    b"invalid json", b'{"error":"unavailable"}', b'{"data":null}',
    b'{"data":{}}', b'{"data":[null]}', b"[]",
    b'{"data":[{"period":202412,"netWgt":1000,"flowCode":"invalid"}]}',
])
def test_malformed_response_is_failed_not_empty(tmp_path, monkeypatch, payload):
    fetcher = _fetcher(tmp_path, monkeypatch, {"M": payload, "X": b'{"data":[]}'})
    assert fetcher.fetch_all() == []
    assert [r.status for r in fetcher.request_results] == ["FAILED", "EMPTY"]
    summary, failed = run_ingest._comtrade_summary(fetcher)
    assert failed
    assert summary.startswith("FAILED")


def test_missing_weight_is_incomplete_not_empty(tmp_path, monkeypatch):
    fetcher = _fetcher(tmp_path, monkeypatch, {
        "M": _payload(weight=None), "X": b'{"data":[]}',
    })
    assert fetcher.fetch_all() == []
    result = fetcher.request_results[0]
    assert result.status == "INCOMPLETE"
    assert result.skipped_rows == 1
    assert run_ingest._comtrade_summary(fetcher)[1]


def test_results_reset_between_runs(tmp_path, monkeypatch):
    fetcher = _fetcher(tmp_path, monkeypatch, {
        "M": b'{"data":[]}', "X": b'{"data":[]}',
    })
    fetcher.fetch_all()
    fetcher.fetch_all()
    assert len(fetcher.request_results) == 2
    summary, failed = run_ingest._comtrade_summary(fetcher)
    assert summary.startswith("NO_DATA")
    assert not failed


def test_default_periods_and_year_boundary():
    assert run_ingest._comtrade_periods(2) == ["202411", "202412"]
    assert run_ingest._comtrade_periods(3, (2025, 2)) == ["202412", "202501", "202502"]
    assert run_ingest._comtrade_periods(1, (1, 1)) == ["000101"]
    assert run_ingest._comtrade_end("2025-12") == (2025, 12)


@pytest.mark.parametrize("value", ["2025-13", "2025-00", "2025-1", "25-12", "0000-01", "x"])
def test_invalid_ending_month(value):
    with pytest.raises(argparse.ArgumentTypeError):
        run_ingest._comtrade_end(value)


@pytest.mark.parametrize("months,end", [(0, (2024, 12)), (-1, (2024, 12)), (2, (1, 1))])
def test_invalid_month_count(months, end):
    with pytest.raises(ValueError):
        run_ingest._comtrade_periods(months, end)


@pytest.mark.parametrize("arguments", [
    ["--comtrade-months", "0"],
    ["--comtrade-months", "-1"],
    ["--comtrade-end", "2025-13"],
])
def test_invalid_cli_arguments_stop_before_database_creation(tmp_path, monkeypatch, arguments):
    db = tmp_path / "not-created" / "data.db"
    monkeypatch.setattr("sys.argv", ["ingest", "--db", str(db), *arguments])
    with pytest.raises(SystemExit) as exc:
        run_ingest.main()
    assert exc.value.code == 2
    assert not db.parent.exists()


@pytest.mark.parametrize("export,expected_code,expected_status", [
    (RuntimeError("request failed"), 1, "PARTIAL"),
    (b'{"data":[]}', 0, "OK"),
    (_payload("X", 0), 0, "OK"),
    (_payload("X", None), 1, "PARTIAL"),
])
def test_cli_exit_status_and_successful_row_retention(
    tmp_path, monkeypatch, capsys, export, expected_code, expected_status,
):
    fetcher = _fetcher(tmp_path, monkeypatch, {"M": _payload(), "X": export})
    requested = []

    def factory(*, periods):
        requested.extend(periods)
        return fetcher

    monkeypatch.setattr(run_ingest, "ComtradeCopperFetcher", factory)
    monkeypatch.setattr(run_ingest.ShfeCopperFetcher, "fetch_all", lambda _: [])
    db = tmp_path / "data.db"
    monkeypatch.setattr("sys.argv", [
        "ingest", "--db", str(db), "--comtrade-months", "2", "--comtrade-end", "2025-01",
    ])
    assert run_ingest.main() == expected_code
    assert requested == ["202412", "202501"]
    output = capsys.readouterr().out
    assert "requested 202412..202501" in output
    assert f"comtrade   {expected_status}" in output
    if expected_code:
        assert "202412 X:" in output
    store = PITStore(db)
    assert len(store.as_of("refined_copper_trade_m", date(2026, 9, 23))) == 1
    store.conn.close()
