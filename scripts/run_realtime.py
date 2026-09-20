"""Snapshot diagnostic from the store built by `scripts/run_ingest.py`.

The original mixed-frequency specification fails closed. An explicit
--config config/pcs_monthly_exploratory.yaml opts into a provisional monthly
construction. A history computed at ONE as-of date is not a sequence of
historically tradable signals. No empirical or causal validation is implied.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from pcs.build import CONFIG_PATH, build_physical_commercial, load_pcs_config
from pcs.score import compute_pcs
from warehouse.pit import PITStore

DEFAULT_DB = Path(__file__).resolve().parent.parent / "warehouse" / "data" / "pit_store.db"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--asof", type=str, default=None, help="YYYY-MM-DD, default today")
    ap.add_argument("--tail", type=int, default=15)
    ap.add_argument("--config", type=Path, default=CONFIG_PATH)
    args = ap.parse_args()

    if not args.db.exists():
        print(f"No PIT store at {args.db}. Run `make ingest` first.")
        return 1

    asof = date.fromisoformat(args.asof) if args.asof else date.today()
    store = PITStore(args.db)
    config = load_pcs_config(args.config)
    print(f"Specification: {args.config.name}; status: {config.get('status', 'locked_original')}")
    print(
        "Descriptive snapshot history using values available at this as-of date. "
        "Not a historical real-time backtest; unknown publication dates are retrieval-gated."
    )

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

    print(f"PCS snapshot as of {asof}: {len(out)} periods, most recent {args.tail}:\n")
    cols = ["pcs", "physical_coverage", "commercial_coverage", "confidence"]
    print(out[cols].tail(args.tail).to_string())

    print("\nConfidence label counts (entire series):")
    print(out["confidence"].value_counts().to_string())

    print(
        "\nNo causal claim or instrument validation. A channel-level outcome panel "
        "is still missing. Monthly aggregation also cannot resolve the two April "
        "event dates separately; this is not the original event-study design."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
