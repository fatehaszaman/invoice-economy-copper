"""`make realtime`: PIT-constrained PCS score computed from the live PIT
store built by `scripts/run_ingest.py`.

This is a genuine live-data computation, not a demonstration against
synthetic data. It is intentionally NOT `FINDINGS.md`: it reports the score
and its coverage, with no causal or interpretive claim, because the
per-channel exposure panel needed for that claim does not exist yet (see
README "Live ingestion status").
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from pcs.build import build_physical_commercial, load_pcs_config
from pcs.score import compute_pcs
from warehouse.pit import PITStore

DEFAULT_DB = Path(__file__).resolve().parent.parent / "warehouse" / "data" / "pit_store.db"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--asof", type=str, default=None, help="YYYY-MM-DD, default today")
    ap.add_argument("--tail", type=int, default=15)
    args = ap.parse_args()

    if not args.db.exists():
        print(f"No PIT store at {args.db}. Run `make ingest` first.")
        return 1

    asof = date.fromisoformat(args.asof) if args.asof else date.today()
    store = PITStore(args.db)
    config = load_pcs_config()

    try:
        physical_z, commercial_z = build_physical_commercial(store, asof, config)
    except ValueError as e:
        print(f"Cannot build a panel: {e}")
        return 1

    out = compute_pcs(
        physical_z,
        commercial_z,
        coverage_floor=config["aggregation"]["coverage_floor"],
    )

    print(f"PCS as of {asof} — {len(out)} periods computed, most recent {args.tail}:\n")
    cols = ["pcs", "physical_coverage", "commercial_coverage", "confidence"]
    print(out[cols].tail(args.tail).to_string())

    print("\nConfidence label counts (entire series):")
    print(out["confidence"].value_counts().to_string())

    print(
        "\nNo causal claim is made here. This is the aggregate PCS instrument only "
        "— the exposure/monotonicity analysis needs a per-channel panel this build "
        "does not have live access to (see README)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
