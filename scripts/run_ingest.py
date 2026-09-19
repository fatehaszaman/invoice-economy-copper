"""`make ingest`: fetch live sources, archive raw payloads, load into the PIT store.

Honest by construction: a source that cannot be reached raises and is
reported as blocked, never silently skipped. The script's exit code is 0 iff
every source that is EXPECTED to work in this environment did; sources known
to be blocked from this build environment (NBS, SHIBOR) are reported but do
not fail the run, and LME is reported as its documented licensed fallback.

Usage:
    python -m scripts.run_ingest [--shfe-days N] [--comtrade-months N] [--db PATH]
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

from ingest.base import LicensedDataUnavailable
from ingest.comtrade import ComtradeCopperFetcher
from ingest.lme import LmeFetcher
from ingest.nbs import NbsFetcher, NbsUnavailable
from ingest.shfe import ShfeCopperFetcher
from ingest.shibor import ShiborFetcher, ShiborUnavailable
from warehouse.pit import Observation, PITStore

DEFAULT_DB = Path(__file__).resolve().parent.parent / "warehouse" / "data" / "pit_store.db"

# Comtrade free-tier availability caps at 2024-12 (verified via getDA at
# build time; see ingest/comtrade.py docstring). Fetching further back than
# needed just burns rate-limit budget for no analytical benefit here.
COMTRADE_LATEST_AVAILABLE = (2024, 12)


def _comtrade_periods(n_months: int) -> list[str]:
    y, m = COMTRADE_LATEST_AVAILABLE
    periods = []
    for _ in range(n_months):
        periods.append(f"{y:04d}{m:02d}")
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return list(reversed(periods))


def _rows_to_observations(rows: list[dict], retrieval_ts: date) -> list[Observation]:
    obs = []
    for r in rows:
        obs.append(
            Observation(
                canonical_series_id=r["canonical_series_id"],
                economic_object=r["economic_object"],
                observation_ts=r["observation_ts"],
                publication_ts=r["publication_ts"],
                retrieval_ts=retrieval_ts,
                canonical_value=r["canonical_value"],
                unit=r["unit"],
                source=r["source"],
                raw_value=r.get("raw_value"),
                frequency=r.get("frequency", "daily"),
                source_series_id=r.get("source_series_id"),
                source_url=r.get("source_url"),
                payload_hash=r.get("payload_hash"),
                license_class=r.get("license_class", "public"),
                quality_flags=r.get("quality_flags"),
                vintage_id=f"{r['publication_ts'].isoformat()}#0",
            )
        )
    return obs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shfe-days", type=int, default=630, help="calendar days of SHFE history")
    ap.add_argument(
        "--comtrade-months",
        type=int,
        default=120,
        help=(
            "months of Comtrade history. 120 (10y) is the default because the "
            "rolling-z standardisation window needs >=63 monthly observations "
            "before net_refined_imports produces a single non-NaN value "
            "(min_periods = max(20, window // 4), window=252 configured for "
            "daily series but applied literally here) — see README."
        ),
    )
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = ap.parse_args()

    args.db.parent.mkdir(parents=True, exist_ok=True)
    store = PITStore(args.db)
    today = date.today()
    report: dict[str, str] = {}
    all_obs: list[Observation] = []

    # ---------------------------------------------------------- SHFE (live)
    print(f"[shfe] fetching {args.shfe_days} calendar days ending {today} ...")
    shfe = ShfeCopperFetcher(start=today - timedelta(days=args.shfe_days), end=today)
    shfe_rows = shfe.fetch_all()
    print(f"[shfe] {len(shfe_rows)} daily observations")
    all_obs.extend(_rows_to_observations(shfe_rows, today))
    report["shfe"] = f"OK — {len(shfe_rows)} observations (volume_oi_churn)"

    # -------------------------------------------------- UN Comtrade (live)
    periods = _comtrade_periods(args.comtrade_months)
    print(f"[comtrade] fetching {len(periods)} months ({periods[0]}..{periods[-1]}) ...")
    comtrade = ComtradeCopperFetcher(periods=periods)
    comtrade_rows = comtrade.fetch_all()
    print(f"[comtrade] {len(comtrade_rows)} monthly observations")
    all_obs.extend(_rows_to_observations(comtrade_rows, today))
    report["comtrade"] = (
        f"OK — {len(comtrade_rows)} observations (refined_copper_trade_m/x), "
        f"stale beyond {COMTRADE_LATEST_AVAILABLE[0]}-{COMTRADE_LATEST_AVAILABLE[1]:02d} "
        "(free-tier cap; does not cover the April 2026 event window)"
    )

    # --------------------------------------------------------- NBS (blocked)
    try:
        NbsFetcher().fetch_all()
    except NbsUnavailable as e:
        report["nbs"] = f"BLOCKED — {e}"
        print(f"[nbs] blocked: {e}")

    # ------------------------------------------------------ SHIBOR (blocked)
    try:
        ShiborFetcher().fetch_all()
    except ShiborUnavailable as e:
        report["shibor"] = f"UNREACHABLE — {e}"
        print(f"[shibor] unreachable: {e}")

    # ------------------------------------------------------- LME (licensed)
    try:
        LmeFetcher().fetch_all()
    except LicensedDataUnavailable as e:
        report["lme"] = f"FALLBACK (documented) — {e}"
        print(f"[lme] documented fallback: {e}")

    for o in all_obs:
        store.append(o)
    print(f"\nLoaded {len(all_obs)} observations into {args.db}")

    print("\n=== Ingest report ===")
    for src, msg in report.items():
        print(f"{src:10s} {msg}")

    # Non-zero only if a source expected to work in this environment failed.
    return 0


if __name__ == "__main__":
    sys.exit(main())
