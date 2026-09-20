"""Offline reviewer walkthrough using synthetic evidence in a temporary directory."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from dataclasses import asdict, replace
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pandas as pd

from pcs.build import net_refined_imports
from warehouse.audit import coverage, open_readonly, report, verify_archives
from warehouse.pit import Observation, PITStore


def collect_evidence() -> dict[str, Any]:
    """Exercise real project functions, without network calls or the user's data."""
    production = Observation(
        canonical_series_id="synthetic_production",
        economic_object="production_event",
        observation_ts=date(2026, 4, 30),
        publication_ts=date(2026, 5, 17),
        retrieval_ts=date(2026, 9, 19),
        canonical_value=100.0, unit="tonnes", source="synthetic",
    )
    trade = Observation(
        canonical_series_id="refined_copper_trade_m",
        economic_object="import_event",
        observation_ts=date(2026, 1, 31),
        publication_ts=date(2026, 5, 17),
        retrieval_ts=date(2026, 9, 19),
        canonical_value=500.0, unit="tonnes", source="synthetic",
        quality_flags="publication_time_unknown;synthetic_fixture",
    )
    observations = [
        production,
        replace(
            production, publication_ts=date(2026, 6, 18),
            revision_number=1, canonical_value=110.0,
        ),
        trade,
        replace(
            trade, canonical_series_id="refined_copper_trade_x",
            economic_object="export_event", canonical_value=0.0,
        ),
        replace(trade, observation_ts=date(2026, 2, 28), canonical_value=600.0),
    ]
    # The archived fixture actually contains the source fields for these rows.
    payload = json.dumps(
        [asdict(obs) for obs in observations], default=str, sort_keys=True,
    ).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    with TemporaryDirectory(prefix="copper-reviewer-demo-") as directory:
        root = Path(directory)
        raw = root / f"{digest}.bin"
        raw.write_bytes(payload)
        store = PITStore(root / "synthetic.db")
        try:
            for obs in observations:
                store.append(replace(obs, payload_hash=digest))
            first = store.as_of("synthetic_production", date(2026, 6, 1))
            revised = store.as_of("synthetic_production", date(2026, 6, 20))
            early_trade = store.as_of("refined_copper_trade_m", date(2026, 6, 1))
            net = net_refined_imports(store, date(2026, 9, 20))
            reader = open_readonly(root / "synthetic.db")
            try:
                missing = coverage(
                    reader, ["expected_but_absent"], date(2026, 9, 20),
                )[0]
                intact = verify_archives(reader, root)
                blocked = False
                try:
                    reader.execute("DELETE FROM observations")
                except sqlite3.OperationalError:
                    blocked = True
                # Deliberate negative case, only inside the temporary fixture.
                raw.write_bytes(b"deliberately changed synthetic fixture")
                changed = verify_archives(reader, root)
                return {
                    "production_before_revision": float(first["canonical_value"].iloc[0]),
                    "production_after_revision": float(revised["canonical_value"].iloc[0]),
                    "trade_rows_before_retrieval": len(early_trade),
                    "net_with_reported_zero_export": float(net.loc["2026-01-31"]),
                    "net_with_missing_export": (
                        None if pd.isna(net.loc["2026-02-28"])
                        else float(net.loc["2026-02-28"])
                    ),
                    "absent_series_rows": missing["eligible_rows"],
                    "duplicate_groups": len(report(reader, "duplicates")),
                    "matching_payloads": sum(row["status"] == "ok" for row in intact),
                    "tampered_payload_status": changed[0]["status"],
                    "readonly_delete_blocked": blocked,
                    "rows_after_delete_attempt": reader.execute(
                        "SELECT COUNT(*) FROM observations"
                    ).fetchone()[0],
                }
            finally:
                reader.close()
        finally:
            store.conn.close()


def render(evidence: dict[str, Any]) -> str:
    cases = [
        ("April production as of June 1", "production_before_revision", "Original vintage"),
        ("April production as of June 20", "production_after_revision", "Revision now eligible"),
        ("Trade rows before September retrieval", "trade_rows_before_retrieval",
         "Unknown publication is retrieval-gated"),
        ("January net imports; export explicitly zero", "net_with_reported_zero_export",
         "Reported zero is valid"),
        ("February net imports; export absent", "net_with_missing_export",
         "Missing is not zero"),
        ("Requested absent-series rows", "absent_series_rows", "Absence remains visible"),
        ("Duplicate logical-key groups", "duplicate_groups", "No duplicate fixture vintages"),
        ("Matching referenced payloads", "matching_payloads", "Fixture bytes match their hash"),
        ("Deliberately altered payload", "tampered_payload_status", "Tampering is detected"),
        ("DELETE through read-only connection", "readonly_delete_blocked", "Write is blocked"),
        ("Rows after attempted DELETE", "rows_after_delete_attempt", "All fixture rows remain"),
    ]
    lines = [
        "# Offline evidence walkthrough", "",
        "All values below are SYNTHETIC fixtures, not copper-market observations or findings.",
        "Run `make demo` from the repository root to reproduce this output. No provider",
        "credentials, market-data downloads or existing database are required.", "",
        "## Observed behavior", "",
        "| Scenario | Output | Interpretation |",
        "|---|---|---|",
    ]
    for label, key, interpretation in cases:
        value = evidence[key]
        shown = "missing" if value is None else str(value)
        lines.append(f"| {label} | {shown} | {interpretation} |")
    lines.extend([
        "", "## What this demonstrates", "",
        "The demo calls the actual vintage store, net-import builder, SQL audit and",
        "payload verifier. It creates five synthetic observation rows in a temporary",
        "database, checks an archived fixture, deliberately changes that temporary",
        "fixture, and attempts a write through a read-only connection. Temporary data",
        "are removed when the run finishes; the local research archive is not touched.",
        "",
        "The production fixture supplies simulated known release dates. The trade",
        "fixture deliberately marks publication time unknown. These cases exercise",
        "different availability rules; they do not authenticate any real release date.",
        "",
        "This walkthrough does not fetch or parse live sources, build the complete",
        "monthly PCS, establish historical source authenticity, or validate a causal",
        "claim. Integrity checks are not evidence of adequate market-data coverage.",
        "",
        "## Reproducibility check", "",
        "`make demo-check` reruns the fixture and compares the full output with this",
        "document. A mismatch fails the check; the expected output is never updated",
        "automatically. Review behavioral changes before changing this snapshot.", "",
    ])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", type=Path, help="Compare with an existing expected-output document",
    )
    args = parser.parse_args(argv)
    output = render(collect_evidence())
    if args.check is not None:
        if not args.check.is_file() or args.check.read_text(encoding="utf-8") != output:
            print("Demo output differs from the expected document; review before updating it.")
            return 1
        print("Offline evidence walkthrough matches its checked-in output.")
        return 0
    print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
