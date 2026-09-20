"""Offline, read-only warehouse audit. JSON goes to stdout; no files are repaired."""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from warehouse.audit import coverage, open_readonly, report, verify_archives


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--asof", type=date.fromisoformat, required=True)
    parser.add_argument(
        "--series", action="append", required=True,
        help="Expected raw series; repeat to retain missing inputs in the report.",
    )
    parser.add_argument("--revisions", help="Optional raw series revision history")
    parser.add_argument(
        "--archive", type=Path, help="Also hash-check referenced raw payloads in this directory",
    )
    args = parser.parse_args(argv)
    conn = open_readonly(args.db)
    try:
        duplicates = report(conn, "duplicates")
        result = {
            "scope": "local integrity and availability audit; not empirical validation",
            "inventory_all_vintages": report(conn, "inventory"),
            "duplicate_logical_keys": duplicates,
            "requested_raw_series_asof": coverage(conn, args.series, args.asof),
        }
        failed = bool(duplicates)
        if args.revisions is not None:
            result["revision_history_all_vintages"] = report(conn, "revisions", args.revisions)
        if args.archive is not None:
            archives = verify_archives(conn, args.archive)
            result["referenced_payload_integrity"] = archives
            failed |= any(row["status"] != "ok" for row in archives)
        result["integrity_status"] = "fail" if failed else "passed_requested_checks"
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
        return 1 if failed else 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
