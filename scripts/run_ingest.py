"""`make ingest`: fetch live sources, archive raw payloads, load into the PIT store.

Comtrade request failures and unparseable responses are reported separately
from valid empty responses. Successful observations are retained, but failed
or incomplete Comtrade requests produce exit code 1. Exit code 0 does not
certify coverage, historical availability, or other adapters' completeness.
Known blocked sources (NBS, SHIBOR) do not fail the run, and LME is reported
as its documented licensed fallback.

Usage:
    python -m scripts.run_ingest [--comtrade-months N] [--comtrade-end YYYY-MM]
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
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

# Last month covered by the archived build, NOT a universal API entitlement
# limit. This default request range does not automatically discover updates.
DEFAULT_COMTRADE_END = (2024, 12)


def _comtrade_end(value: str) -> tuple[int, int]:
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}", value):
        raise argparse.ArgumentTypeError("expected YYYY-MM")
    y, m = map(int, value.split("-"))
    try:
        date(y, m, 1)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected a valid YYYY-MM") from exc
    return y, m


def _comtrade_periods(
    n_months: int, end: tuple[int, int] = DEFAULT_COMTRADE_END,
) -> list[str]:
    y, m = end
    date(y, m, 1)
    last = (y - 1) * 12 + m - 1
    if n_months < 1 or n_months > last + 1:
        raise ValueError("comtrade-months must be positive and not extend before year 0001")
    periods = []
    for index in range(last - n_months + 1, last + 1):
        year, month = divmod(index, 12)
        periods.append(f"{year + 1:04d}{month + 1:02d}")
    return periods


def _comtrade_summary(fetcher: ComtradeCopperFetcher) -> tuple[str, bool]:
    counts = Counter(result.status for result in fetcher.request_results)
    observations = sum(result.observation_count for result in fetcher.request_results)
    failed = bool(counts["FAILED"] or counts["INCOMPLETE"])
    if failed:
        status = "PARTIAL" if observations else "FAILED"
    else:
        status = "OK" if observations else "NO_DATA"
    return (
        f"{status} — {len(fetcher.request_results)} requests; "
        f"data={counts['DATA']}, empty={counts['EMPTY']}, "
        f"incomplete={counts['INCOMPLETE']}, failed={counts['FAILED']}; "
        f"{observations} observations; "
        "request status does not certify coverage or historical availability",
        failed,
    )


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
                vintage_id=(
                    f"{r['publication_ts'].isoformat()}#"
                    f"{r.get('payload_hash') or '0'}"
                ),
            )
        )
    return obs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shfe-days", type=int, default=630, help="calendar days of SHFE history")
    ap.add_argument(
        "--comtrade-months",
        type=int,
        default=36,
        help="months of descriptive trade history; does not resolve mixed-frequency scoring",
    )
    ap.add_argument(
        "--comtrade-end", type=_comtrade_end, default=DEFAULT_COMTRADE_END,
        metavar="YYYY-MM",
        help="inclusive last requested month (default: 2024-12); not a coverage guarantee",
    )
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = ap.parse_args()
    try:
        periods = _comtrade_periods(args.comtrade_months, args.comtrade_end)
    except ValueError as exc:
        ap.error(str(exc))

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
    print(f"[comtrade] fetching {len(periods)} months ({periods[0]}..{periods[-1]}) ...")
    comtrade = ComtradeCopperFetcher(periods=periods)
    comtrade_rows = comtrade.fetch_all()
    print(f"[comtrade] {len(comtrade_rows)} monthly observations")
    all_obs.extend(_rows_to_observations(comtrade_rows, today))
    report["comtrade"], comtrade_failed = _comtrade_summary(comtrade)
    report["comtrade"] += f"; requested {periods[0]}..{periods[-1]}"
    for result in comtrade.request_results:
        if result.status != "DATA":
            print(
                f"[comtrade] {result.period} {result.flow}: {result.status}; "
                f"observations={result.observation_count}, skipped={result.skipped_rows}"
                + (f"; {result.error}" if result.error else "")
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

    # Successful rows are retained even when another Comtrade request failed.
    return 1 if comtrade_failed else 0


if __name__ == "__main__":
    sys.exit(main())
