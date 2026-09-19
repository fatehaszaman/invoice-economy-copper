"""Shanghai Futures Exchange fetcher — copper futures daily trading data.

Endpoint discovered from the exchange's own public page script
(`/eng/images/api.js`, function `api_futures_kx`), which is the mechanism
the exchange's own English site uses to render this page to visitors. It
requires no authentication and no license: it is the same JSON the public
website itself displays.

    https://www.shfe.com.cn/data/tradedata/future/dailydata/kx{YYYYMMDD}.dat

Feeds the PCS commercial block series `volume_oi_churn`: daily traded volume
divided by open interest, summed across all listed copper (cu) contract
months. A rising ratio means positions turn over faster relative to how many
are open — the commercial-circulation signal the block is meant to capture.

Known gap: the exchange's `dailystock` / `weeklystock` warehouse-receipt
endpoints (which would feed `warrant_churn` and
`deliveries_vs_warrant_change`) return 404 under every date and naming
pattern tried against the live site as of this build. That is reported
honestly in README/DECISIONS rather than guessed at with an unverified URL
shape.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta

from .base import Fetcher

BASE_URL = "https://www.shfe.com.cn/data/tradedata/future/dailydata/kx{date}.dat"
PRODUCT_GROUP = "cu"  # copper


@dataclass(frozen=True)
class ShfeDailyRecord:
    trade_date: date
    volume: float
    open_interest: float
    settlement_price: float
    close_price: float
    delivery_month: str


def _parse_kx_payload(payload: bytes, trade_date: date) -> list[ShfeDailyRecord]:
    text = payload.decode("utf-8", errors="strict")
    obj = json.loads(text)
    rows = obj.get("o_curinstrument", [])
    out = []
    for r in rows:
        if r.get("PRODUCTGROUPID") != PRODUCT_GROUP:
            continue
        # The exchange emits a trailing all-product-summary row with an
        # empty delivery month; skip anything that isn't a real contract.
        if not r.get("DELIVERYMONTH"):
            continue
        try:
            vol = float(r["VOLUME"])
            oi = float(r["OPENINTEREST"])
            settle = float(r["SETTLEMENTPRICE"])
            close = float(r["CLOSEPRICE"])
        except (KeyError, TypeError, ValueError):
            continue
        out.append(
            ShfeDailyRecord(
                trade_date=trade_date,
                volume=vol,
                open_interest=oi,
                settlement_price=settle,
                close_price=close,
                delivery_month=str(r["DELIVERYMONTH"]),
            )
        )
    return out


class ShfeCopperFetcher(Fetcher):
    """Daily copper (cu) trading data from the Shanghai Futures Exchange.

    License: public. This is the exchange's own public daily-data feed;
    no subscription or agreement is required to read it.
    """

    source = "shfe"
    license_class = "public"

    def __init__(self, start: date, end: date, archive=None) -> None:
        super().__init__(archive=archive)
        if end < start:
            raise ValueError("end must not precede start")
        self.start = start
        self.end = end

    def endpoints(self) -> list[str]:
        urls = []
        d = self.start
        while d <= self.end:
            # Exchange is closed weekends; still request weekdays only to
            # avoid hammering the server with URLs guaranteed to 404.
            if d.weekday() < 5:
                urls.append(BASE_URL.format(date=d.strftime("%Y%m%d")))
            d += timedelta(days=1)
        return urls

    def parse(self, payload: bytes, url: str) -> list[dict]:
        # Extract YYYYMMDD from the url to recover the trade date without
        # re-parsing the exchange's own (undocumented) date fields.
        digits = "".join(c for c in url.split("/")[-1] if c.isdigit())[:8]
        trade_date = date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))

        records = _parse_kx_payload(payload, trade_date)
        if not records:
            return []

        total_volume = sum(r.volume for r in records)
        total_oi = sum(r.open_interest for r in records)
        if total_oi <= 0:
            return []
        churn = total_volume / total_oi

        # Publication lag for SHFE settlement/volume/OI is same-day per
        # DATA_DICTIONARY.md; the exchange publishes at end of the trading
        # session it describes.
        return [
            {
                "canonical_series_id": "volume_oi_churn",
                "economic_object": "business_transaction",
                "observation_ts": trade_date,
                "publication_ts": trade_date,
                "unit": "ratio",
                "canonical_value": churn,
                "raw_value": total_volume,
                "source": self.source,
                "source_series_id": "cu_kx_volume_oi",
                "source_url": url,
                "license_class": self.license_class,
                "frequency": "daily",
                "quality_flags": (
                    None if total_oi > 0 else "zero_open_interest"
                ),
            }
        ]

    def fetch_all(self, max_workers: int = 10) -> list[dict]:
        """Fetch every endpoint, archive raw payloads, return parsed rows.

        Missing trading days (weekends already excluded, plus exchange
        holidays which still 404) are skipped rather than raising — a
        holiday calendar gap is expected, not a fetch failure. Fetches
        concurrently: this is a one-URL-per-trading-day public data feed,
        not an authenticated or rate-limited API, and a full multi-year
        backfill run sequentially would take too long to be practical.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        out: list[dict] = []

        def _one(url: str) -> list[dict]:
            try:
                payload = self.fetch_with_retry(url, attempts=2, base_delay=1.0)
            except RuntimeError:
                return []
            if not payload or payload.lstrip()[:1] not in (b"{", b"["):
                return []  # holiday/no-data response is an HTML 404 page
            digest = self.store_raw(payload, url)
            rows = self.parse(payload, url)
            for r in rows:
                r["payload_hash"] = digest
            return rows

        urls = self.endpoints()
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(_one, u) for u in urls]
            for f in as_completed(futures):
                out.extend(f.result())
        return out
