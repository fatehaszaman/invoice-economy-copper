"""Read-only evidence checks. No ingestion, repair, or empirical validity verdict."""
from __future__ import annotations

import hashlib
import re
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

from warehouse.pit import AS_OF_SQL

SQL_DIR = Path(__file__).parent / "sql"
REPORTS = {
    name: (SQL_DIR / f"{name}.sql").read_text(encoding="utf-8")
    for name in ("inventory", "duplicates", "revisions")
}


def open_readonly(path: str | Path) -> sqlite3.Connection:
    """Fail for missing databases; never create a new empty database."""
    conn = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def report(
    conn: sqlite3.Connection, name: str, series_id: str | None = None,
) -> list[dict[str, Any]]:
    """Only fixed reviewed queries; values are bound parameters, never SQL text."""
    if name not in REPORTS:
        raise ValueError(f"Unknown report: {name}")
    if name == "revisions" and series_id is None:
        raise ValueError("revisions requires a series_id")
    return [dict(row) for row in conn.execute(REPORTS[name], {"sid": series_id})]


def coverage(
    conn: sqlite3.Connection, series_ids: list[str], asof: date,
) -> list[dict[str, Any]]:
    """One summary per requested RAW series, including entirely absent inputs.

    This is row availability, not PCS block coverage or exchange-calendar coverage.
    Derived net_refined_imports must be audited through both raw trade legs.
    """
    result = []
    for sid in dict.fromkeys(series_ids):
        rows = conn.execute(
            AS_OF_SQL, {"sid": sid, "cid": None, "asof": asof.isoformat()},
        ).fetchall()
        valid = sum(row["canonical_value"] is not None for row in rows)
        result.append({
            "series_id": sid,
            "asof": asof.isoformat(),
            "eligible_rows": len(rows),
            "non_null_rows": valid,
            "first_reference_date": min((row["observation_ts"] for row in rows), default=None),
            "last_reference_date": max((row["observation_ts"] for row in rows), default=None),
            "status": "available" if valid else "unavailable",
        })
    return result


def verify_archives(conn: sqlite3.Connection, archive: str | Path) -> list[dict[str, Any]]:
    """Verify every distinct referenced payload, not unreferenced files or metadata.

    A hash match is byte integrity only, not source authenticity. Reject symlinks
    and malformed identifiers before reading. Assumes a trusted local filesystem;
    it does not defend against concurrent malicious path replacement.
    """
    root = Path(archive).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Archive must be a directory")
    result = []
    for row in conn.execute(
        "SELECT DISTINCT payload_hash FROM observations ORDER BY payload_hash"
    ):
        digest = row["payload_hash"]
        # Do not echo an invalid identifier: it could contain sensitive content.
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            result.append({"payload_hash": None, "status": "invalid_or_missing_hash"})
            continue
        path = root / f"{digest}.bin"
        if path.is_symlink():
            status = "symlink_rejected"
        elif not path.is_file():
            status = "missing"
        else:
            try:
                with path.open("rb") as stream:
                    actual = hashlib.file_digest(stream, "sha256").hexdigest()
                status = "ok" if actual == digest else "hash_mismatch"
            except OSError:
                status = "unreadable"
        result.append({"payload_hash": digest, "status": status})
    return result
