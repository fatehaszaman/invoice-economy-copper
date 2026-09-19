"""UN Comtrade fetcher — substitute for China Customs (GACC) trade detail.

GACC does not publish a free, machine-readable copper trade feed; its
detailed bulletins are commentary, not a data API. UN Comtrade republishes
the same underlying customs declarations reporter-countries submit,
including China's, so it is used here as the accessible proxy the README
already frames as necessary ("Publicly accessible or individually licensed
source data").

**Material limitation, verified at build time, not assumed:** the free
`/public/v1/preview` tier caps China's HS-7403 (unwrought refined copper)
monthly series at December 2024 (`getDA` enumerates no later dataset). It
therefore CANNOT reach the April 2026 enforcement window this project
studies. This fetcher is real and returns real customs figures — it is
useful for historical / pre-event context, negative-control checks, and for
validating the ingestion and PIT-store plumbing end to end — but it is not
a substitute for a paid Comtrade subscription or GACC bulletin data when the
live event-window estimation eventually runs. Do not remove this docstring
warning when extending the date range: silently forgetting it is exactly the
kind of look-ahead-shaped gap `warehouse/pit.py` exists to prevent.
"""
from __future__ import annotations

import json
from datetime import date

from .base import Fetcher

BASE_URL = "https://comtradeapi.un.org/public/v1/preview/C/M/HS"
REPORTER_CHINA = 156
PARTNER_WORLD = 0
HS_REFINED_COPPER = "7403"  # unwrought refined copper and copper alloys
KG_PER_TONNE = 1000.0

# China customs trade release lag, per DATA_DICTIONARY.md: 20-25 days.
PUBLICATION_LAG_DAYS = 23


class ComtradeCopperFetcher(Fetcher):
    """Monthly China refined-copper (HS 7403) import/export volumes.

    License: public (UN Comtrade free-tier preview API, no key required).
    Coverage is capped by the provider — see module docstring.
    """

    source = "customs"
    license_class = "public"

    def __init__(self, periods: list[str], archive=None) -> None:
        """`periods`: list of 'YYYYMM' strings to request."""
        super().__init__(archive=archive)
        self.periods = periods

    def endpoints(self) -> list[str]:
        urls = []
        for period in self.periods:
            for flow in ("M", "X"):
                urls.append(
                    f"{BASE_URL}?reporterCode={REPORTER_CHINA}&period={period}"
                    f"&partnerCode={PARTNER_WORLD}&cmdCode={HS_REFINED_COPPER}"
                    f"&flowCode={flow}"
                )
        return urls

    def parse(self, payload: bytes, url: str) -> list[dict]:
        obj = json.loads(payload.decode("utf-8"))
        rows = obj.get("data", [])
        out = []
        for r in rows:
            period = str(r["period"])
            obs_year, obs_month = int(period[:4]), int(period[4:6])
            # observation_ts: last day of the reference month.
            if obs_month == 12:
                obs_ts = date(obs_year, 12, 31)
            else:
                next_month = date(obs_year, obs_month + 1, 1)
                obs_ts = date.fromordinal(next_month.toordinal() - 1)

            net_wgt_kg = r.get("netWgt")
            if net_wgt_kg is None:
                continue
            tonnes = float(net_wgt_kg) / KG_PER_TONNE
            flow = r.get("flowCode")
            sign = 1.0 if flow == "M" else -1.0  # imports positive, exports negative

            pub_ts = date.fromordinal(obs_ts.toordinal() + PUBLICATION_LAG_DAYS)

            out.append(
                {
                    # Two rows per period (import leg, export leg) let the
                    # warehouse layer net them into `net_refined_imports`
                    # without this fetcher performing arithmetic that would
                    # hide which leg a number came from.
                    "canonical_series_id": f"refined_copper_trade_{flow.lower()}",
                    "economic_object": "import_event" if flow == "M" else "export_event",
                    "observation_ts": obs_ts,
                    "publication_ts": pub_ts,
                    "unit": "tonnes",
                    "canonical_value": sign * tonnes,
                    "raw_value": net_wgt_kg,
                    "source": self.source,
                    "source_series_id": f"HS{HS_REFINED_COPPER}_{flow}",
                    "source_url": url,
                    "license_class": self.license_class,
                    "frequency": "monthly",
                    "quality_flags": "comtrade_free_tier_stale_beyond_202412",
                }
            )
        return out

    def fetch_all(self) -> list[dict]:
        """Sequential, deliberately: the free preview tier rate-limits
        (observed HTTP 429) and a small fixed pause between requests avoids
        burning retry budget on avoidable throttling."""
        import time

        out: list[dict] = []
        for url in self.endpoints():
            try:
                payload = self.fetch_with_retry(url, attempts=4, base_delay=2.0)
            except RuntimeError:
                continue
            digest = self.store_raw(payload, url)
            rows = self.parse(payload, url)
            for r in rows:
                r["payload_hash"] = digest
            out.extend(rows)
            time.sleep(1.5)
        return out
