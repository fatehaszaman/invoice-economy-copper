"""National Bureau of Statistics (NBS) fetcher — refined production, cable
and wire output, grid investment.

**Status: verified blocked from this build environment, not merely
unimplemented.** `data.stats.gov.cn` returns HTTP 403 from this sandbox's
egress IP for both the query API and the plain query-string GET, via `curl`
with a browser user agent AND via a full CDP-driven browser session
(`data.stats.gov.cn/english/easyquery.htm` renders the literal page title
"403 Forbidden"). This is the WAF-level block `WZWS-RAY` headers, not a
missing referer or a JS challenge a headless fetch could clear.

Feeds `cable_wire_output`, `semis_production`, `refined_production` in the
physical block — half of it. Their absence is the single largest hole in
this build's live PCS coverage; see README "Live ingestion status".

This class still implements the `Fetcher` contract so the pipeline fails
LOUDLY and NAMES the reason (`NbsUnavailable`) rather than the ingest step
silently producing zero rows that look like "no data today." Re-run from an
environment with access to `data.stats.gov.cn` — e.g. the user's own
network — to fill this gap; the parse logic below is written against the
portal's documented JSON shape and is untested against a live response
because none was obtainable.
"""
from __future__ import annotations

from .base import Fetcher

QUERY_URL = "https://data.stats.gov.cn/english/easyquery.htm"

# Indicator codes on the English "National Data" portal (zb = 指标, monthly
# industrial output tables). Recorded here for whoever runs this with
# working access; NOT verified against a live response.
INDICATOR_CODES = {
    "refined_production": "A0402",  # refined copper output, monthly industrial output table
    "cable_wire_output": "A0B0B",  # placeholder: cable/wire is not a single NBS line item
    "semis_production": "A0402",  # placeholder pending a confirmed code
}


class NbsUnavailable(RuntimeError):
    """Raised instead of a silent empty result. See module docstring."""


class NbsFetcher(Fetcher):
    source = "nbs"
    license_class = "public"

    def endpoints(self) -> list[str]:
        return [f"{QUERY_URL}?m=QueryData&dbcode=hgyd&rowcode=zb&colcode=sj"]

    def parse(self, payload: bytes, url: str) -> list[dict]:
        raise NbsUnavailable(
            "NBS parsing is unverified: no live payload was ever obtained "
            "(data.stats.gov.cn returns 403 from this build environment). "
            "Do not trust this method against a payload it has not been "
            "tested on."
        )

    def fetch_all(self) -> list[dict]:
        raise NbsUnavailable(
            "data.stats.gov.cn returned HTTP 403 (WAF) to every request tried "
            "from this build environment, including a full browser session. "
            "cable_wire_output, semis_production, and refined_production "
            "cannot be live-ingested from here. Run this fetcher from a "
            "network with access to data.stats.gov.cn, or source these three "
            "series from a licensed reseller (CEIC, Wind, Mysteel)."
        )
