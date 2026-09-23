"""UN Comtrade HS-7403 import/export snapshot adapter.

The archived build retrieved data through 2024-12. That observation is not
proof of a universal free-tier ceiling, nor that a paid key resolves the gap.
The default requested date range in run_ingest.py is fixed and must be
reviewed separately when seeking newer data.

HS 7403 includes unwrought refined copper AND copper alloys. The existing
internal refined_copper_trade_* identifiers are retained for compatibility,
but this is a broad proxy, not a cathode-only measure.

No verified release/vintage metadata accompanies these parsed values.
Retrieval is the conservative availability bound; historical snapshots
cannot reconstruct what was known in the event window.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from urllib.parse import parse_qs, urlsplit

from .base import Fetcher

BASE_URL = "https://comtradeapi.un.org/public/v1/preview/C/M/HS"
REPORTER_CHINA = 156
PARTNER_WORLD = 0
HS_REFINED_COPPER = "7403"  # unwrought refined copper and copper alloys
KG_PER_TONNE = 1000.0


@dataclass(frozen=True)
class ComtradeRequestResult:
    """One request outcome; EMPTY means a valid response with an empty data list."""

    period: str
    flow: str
    url: str
    status: str
    observation_count: int = 0
    skipped_rows: int = 0
    error: str | None = None


class ComtradeCopperFetcher(Fetcher):
    """Monthly China refined-copper (HS 7403) import/export volumes.

    License: public (UN Comtrade free-tier preview API, no key required).
    Coverage is capped by the provider — see module docstring.
    """

    source = "customs"
    license_class = "public"

    def __init__(self, periods: list[str], archive=None, retrieved_on: date | None = None) -> None:
        """`periods`: list of 'YYYYMM' strings to request."""
        super().__init__(archive=archive)
        self.periods = periods
        # For offline replay, this must be the archived payload's retrieval
        # date, never the historical period or an assumed release lag.
        self.retrieved_on = retrieved_on or date.today()
        self.request_results: list[ComtradeRequestResult] = []

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
        if not isinstance(obj, dict) or not isinstance(obj.get("data"), list):
            raise ValueError("Expected a Comtrade response with a data list")
        rows = obj["data"]
        out = []
        for r in rows:
            if not isinstance(r, dict):
                raise ValueError("Expected each Comtrade data row to be an object")
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
            if flow not in {"M", "X"}:
                raise ValueError(f"Unsupported trade flow: {flow!r}")
            sign = 1.0 if flow == "M" else -1.0  # imports positive, exports negative

            # This response has no verified publication timestamp for this
            # exact value/vintage. Retrieval is a conservative availability
            # bound, NOT a claim about the original statistical release.
            pub_ts = self.retrieved_on

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
                    "quality_flags": (
                        "publication_time_unknown;availability_from_retrieval;"
                        "historical_vintage_unverified"
                    ),
                }
            )
        return out

    def fetch_all(self) -> list[dict]:
        """Sequential, deliberately: the free preview tier rate-limits
        (observed HTTP 429) and a small fixed pause between requests avoids
        burning retry budget on avoidable throttling."""
        import time

        out: list[dict] = []
        self.request_results = []
        for url in self.endpoints():
            query = parse_qs(urlsplit(url).query)
            period, flow = query["period"][0], query["flowCode"][0]
            try:
                payload = self.fetch_with_retry(url, attempts=4, base_delay=2.0)
                digest = self.store_raw(payload, url)
                rows = self.parse(payload, url)
                response_rows = len(json.loads(payload.decode("utf-8"))["data"])
                skipped = response_rows - len(rows)
                status = "INCOMPLETE" if skipped else ("DATA" if rows else "EMPTY")
                self.request_results.append(ComtradeRequestResult(
                    period=period, flow=flow, url=url, status=status,
                    observation_count=len(rows), skipped_rows=skipped,
                    error="Rows without net weight were skipped" if skipped else None,
                ))
                for r in rows:
                    r["payload_hash"] = digest
                out.extend(rows)
            except (RuntimeError, OSError, ValueError, TypeError, KeyError) as exc:
                cause = exc.__cause__ or exc
                self.request_results.append(ComtradeRequestResult(
                    period=period, flow=flow, url=url, status="FAILED",
                    error=f"{type(cause).__name__}: {cause}",
                ))
            finally:
                # Preserve pacing after failures as well as successful requests.
                time.sleep(1.5)
        return out
