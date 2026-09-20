"""Audit tools must preserve research semantics and leave evidence untouched."""
import hashlib
import json
import sqlite3
from dataclasses import replace
from datetime import date

import pytest

from scripts.audit_warehouse import main
from warehouse.audit import coverage, open_readonly, report, verify_archives
from warehouse.pit import AS_OF_SQL, Observation, PITStore


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "evidence.db"
    store = PITStore(path)
    observation = Observation(
        canonical_series_id="production",
        economic_object="production_event",
        observation_ts=date(2026, 4, 30),
        publication_ts=date(2026, 5, 17),
        retrieval_ts=date(2026, 9, 19),
        canonical_value=100.0, unit="tonnes", source="nbs",
    )
    store.append(observation)
    store.append(replace(
        observation, publication_ts=date(2026, 6, 18),
        revision_number=1, canonical_value=110.0,
    ))
    store.append(replace(
        observation, canonical_series_id="trade",
        source="customs", source_url="https://comtradeapi.un.org/public/test",
        quality_flags="publication_time_unknown",
    ))
    yield path, store, observation
    store.conn.close()


def test_readonly_rejects_writes_and_missing_database(database, tmp_path):
    path, _, _ = database
    conn = open_readonly(path)
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("DELETE FROM observations")
        # Turning off query_only does not defeat filesystem-level mode=ro.
        conn.execute("PRAGMA query_only = OFF")
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("CREATE TABLE unwanted (x INTEGER)")
    finally:
        conn.close()
    missing = tmp_path / "missing.db"
    with pytest.raises(sqlite3.OperationalError):
        open_readonly(missing)
    assert not missing.exists()


def test_shared_query_matches_research_and_gates_retrieval(database):
    path, store, _ = database
    conn = open_readonly(path)
    try:
        for asof in (date(2026, 6, 1), date(2026, 6, 20), date(2026, 9, 19)):
            for sid in ("production", "trade"):
                rows = conn.execute(
                    AS_OF_SQL, {"sid": sid, "cid": None, "asof": asof.isoformat()},
                ).fetchall()
                assert [r["canonical_value"] for r in rows] == (
                    store.as_of(sid, asof)["canonical_value"].tolist()
                )
        got = coverage(conn, ["production", "trade", "absent"], date(2026, 6, 1))
        assert [row["eligible_rows"] for row in got] == [1, 0, 0]
        assert got[2]["status"] == "unavailable"
    finally:
        conn.close()


def test_bound_series_parameter_cannot_execute_sql(database):
    path, _, _ = database
    conn = open_readonly(path)
    try:
        malicious = "production'; DROP TABLE observations; --"
        assert report(conn, "revisions", malicious) == []
        assert coverage(conn, [malicious], date(2026, 9, 20))[0]["eligible_rows"] == 0
        assert conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 3
        with pytest.raises(ValueError, match="Unknown report"):
            report(conn, "DROP TABLE observations")
        with pytest.raises(ValueError, match="requires"):
            report(conn, "revisions")
    finally:
        conn.close()


def test_window_revisions_keep_channels_separate(database):
    path, store, observation = database
    store.append(replace(observation, channel_id="other", canonical_value=900.0))
    conn = open_readonly(path)
    try:
        rows = report(conn, "revisions", "production")
        aggregate = [r for r in rows if r["channel_id"] is None]
        other = [r for r in rows if r["channel_id"] == "other"]
        assert [r["revision_delta"] for r in aggregate] == [None, 10.0]
        assert other[0]["previous_value"] is None
    finally:
        conn.close()


def test_duplicate_query_catches_nullable_key_bypass(database):
    path, store, _ = database
    # Bypass the append method: expose SQLite's nullable composite-key weakness.
    store.conn.execute(
        "INSERT INTO observations SELECT * FROM observations WHERE rowid=1"
    )
    store.conn.commit()
    conn = open_readonly(path)
    try:
        rows = report(conn, "duplicates")
        assert len(rows) == 1
        assert rows[0]["duplicate_count"] == 2
        assert rows[0]["channel_id"] is None
    finally:
        conn.close()


@pytest.mark.parametrize(
    "mode,expected",
    [("valid", "ok"), ("changed", "hash_mismatch"), ("missing", "missing"),
     ("symlink", "symlink_rejected"), ("bad_id", "invalid_or_missing_hash"),
     ("null_id", "invalid_or_missing_hash")],
)
def test_archive_integrity_modes(database, tmp_path, mode, expected):
    path, store, _ = database
    payload = b"known source response"
    digest = hashlib.sha256(payload).hexdigest()
    archive = tmp_path / "archive"
    archive.mkdir()
    target = archive / f"{digest}.bin"
    if mode in {"valid", "changed"}:
        target.write_bytes(payload if mode == "valid" else b"changed response")
    elif mode == "symlink":
        outside = tmp_path / "outside.bin"
        outside.write_bytes(payload)
        target.symlink_to(outside)
    elif mode == "bad_id":
        digest = "../../outside"
    elif mode == "null_id":
        digest = None
    store.conn.execute("UPDATE observations SET payload_hash=?", (digest,))
    store.conn.commit()
    conn = open_readonly(path)
    try:
        results = verify_archives(conn, archive)
        assert len(results) == 1
        assert results[0]["status"] == expected
        if mode == "bad_id":
            assert results[0]["payload_hash"] is None
    finally:
        conn.close()


def test_cli_is_readonly_and_missing_coverage_is_not_integrity_failure(database, capsys):
    path, _, _ = database
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    assert main([
        "--db", str(path), "--asof", "2026-06-01",
        "--series", "production", "--series", "absent",
    ]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["requested_raw_series_asof"][1]["status"] == "unavailable"
    assert result["integrity_status"] == "passed_requested_checks"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_cli_fails_for_missing_payload_reference(database, tmp_path, capsys):
    path, _, _ = database
    archive = tmp_path / "archive"
    archive.mkdir()
    assert main([
        "--db", str(path), "--asof", "2026-06-01",
        "--series", "production", "--archive", str(archive),
    ]) == 1
    assert json.loads(capsys.readouterr().out)["integrity_status"] == "fail"
