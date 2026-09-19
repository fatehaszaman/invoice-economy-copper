"""LME fetcher — reference prices, official stocks.

Not implemented, by design, not oversight. `README.md` and `PREREGISTRATION.md`
§9 both commit in advance to this: "Where licensed LME history is
unavailable, the pipeline runs in documented SHFE-only fallback mode and
labels affected results." LME historical data is individually licensed
(https://www.lme.com/Market-data/Accessing-market-data/Historical-data) and
no license is held by this project.

This class exists so the ingest orchestrator (`scripts/run_ingest.py`) can
name the gap explicitly and set `license_class="restricted"` on any
downstream computation that would have used it (the `market_confirmation`
block's `shfe_lme_arb_state`, `nearby_spread`, `curve_structure` — see
`config/pcs.yaml`), rather than that computation silently returning nothing
with no recorded reason.
"""
from __future__ import annotations

from .base import Fetcher, LicensedDataUnavailable


class LmeFetcher(Fetcher):
    source = "lme"
    license_class = "restricted"

    def endpoints(self) -> list[str]:
        return []

    def parse(self, payload: bytes, url: str) -> list[dict]:
        return []

    def fetch_all(self) -> list[dict]:
        raise LicensedDataUnavailable(
            "LME historical price and stock data is individually licensed "
            "and not held by this project. Running in documented SHFE-only "
            "fallback mode per README/PREREGISTRATION.md §9. Series depending "
            "on LME (shfe_lme_arb_state, nearby_spread, curve_structure) are "
            "absent from the market_confirmation block until a license is "
            "obtained; PCS itself does not require LME (see config/pcs.yaml — "
            "no LME-sourced series is inside the score)."
        )
