"""Point-in-time store: bi-temporal observations with as-of resolution.

This is the single most important guarantee in the repository. Chinese
production and customs data revise. An analysis run against latest-vintage
data silently uses information that did not exist during the event window,
and the resulting bug leaves no trace while producing plausible results.

Three distinct times, never collapsed:

    observation_ts  when the economic event occurred
    publication_ts  when a researcher could first have known it
    retrieval_ts    when this system fetched it

Design decision, deliberate: there is no function returning "the current
value". The latest vintage is reachable only by passing an explicit date,
which makes the choice visible in calling code and in review.

SQLite is the reference implementation. It can enforce supplied vintage
metadata, not establish that metadata's historical authenticity. Comtrade
snapshots without verified release metadata are gated at retrieval.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

AS_OF_SQL = (Path(__file__).parent / "sql" / "as_of.sql").read_text(encoding="utf-8")

SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
    canonical_series_id   TEXT    NOT NULL,
    channel_id            TEXT,
    economic_object       TEXT    NOT NULL,
    observation_ts        TEXT    NOT NULL,
    publication_ts        TEXT    NOT NULL,
    retrieval_ts          TEXT    NOT NULL,
    vintage_id            TEXT    NOT NULL,
    revision_number       INTEGER NOT NULL,
    frequency             TEXT    NOT NULL,
    raw_value             REAL,
    canonical_value       REAL,
    unit                  TEXT    NOT NULL,
    currency              TEXT,
    region                TEXT,
    source                TEXT    NOT NULL,
    source_series_id      TEXT,
    source_url            TEXT,
    payload_hash          TEXT,
    license_class         TEXT    NOT NULL DEFAULT 'public',
    quality_flags         TEXT,
    PRIMARY KEY (canonical_series_id, channel_id, observation_ts, vintage_id)
);

CREATE INDEX IF NOT EXISTS ix_asof
    ON observations (canonical_series_id, observation_ts, publication_ts);
"""

VALID_OBJECTS = {
    "invoice_event",
    "business_transaction",
    "ownership_transfer",
    "funds_transfer",
    "financing_event",
    "physical_movement",
    "inventory_state",
    "production_event",
    "consumption_event",
    "import_event",
    "export_event",
    "price_observation",
}


class LookAheadError(RuntimeError):
    """Raised when a read would expose data published after its as-of date."""


@dataclass(frozen=True)
class Observation:
    canonical_series_id: str
    economic_object: str
    observation_ts: date
    publication_ts: date
    retrieval_ts: date
    canonical_value: float
    unit: str
    source: str
    channel_id: str | None = None
    vintage_id: str | None = None
    revision_number: int = 0
    frequency: str = "monthly"
    raw_value: float | None = None
    currency: str | None = None
    region: str | None = "CN"
    source_series_id: str | None = None
    source_url: str | None = None
    payload_hash: str | None = None
    license_class: str = "public"
    quality_flags: str | None = None

    def __post_init__(self) -> None:
        if self.economic_object not in VALID_OBJECTS:
            raise ValueError(
                f"unknown economic_object {self.economic_object!r}; "
                "every row must declare what real-world object it represents"
            )
        if self.publication_ts < self.observation_ts:
            raise ValueError(
                "publication_ts precedes observation_ts: a value cannot be "
                "published before the period it describes"
            )


class PITStore:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self.conn = sqlite3.connect(str(path))
        self.conn.executescript(SCHEMA)

    # ---------------------------------------------------------------- write

    def append(self, obs: Observation) -> None:
        """Append an observation. Values are NEVER updated in place.

        A revision is a new row with an incremented revision_number, which
        is what makes revision behaviour measurable instead of invisible.
        """
        vintage = obs.vintage_id or obs.publication_ts.isoformat()
        values = (
                obs.canonical_series_id,
                obs.channel_id,
                obs.economic_object,
                obs.observation_ts.isoformat(),
                obs.publication_ts.isoformat(),
                obs.retrieval_ts.isoformat(),
                vintage,
                obs.revision_number,
                obs.frequency,
                obs.raw_value,
                obs.canonical_value,
                obs.unit,
                obs.currency,
                obs.region,
                obs.source,
                obs.source_series_id,
                obs.source_url,
                obs.payload_hash,
                obs.license_class,
                obs.quality_flags,
            )
        existing = self.conn.execute(
            """SELECT * FROM observations
               WHERE canonical_series_id = ? AND channel_id IS ?
                 AND observation_ts = ? AND vintage_id = ?""",
            (obs.canonical_series_id, obs.channel_id, obs.observation_ts.isoformat(), vintage),
        ).fetchone()
        if existing is not None:
            if existing == values:
                return  # Idempotent, including SQLite's nullable channel key.
            if (
                existing[:5] == values[:5] and existing[6:] == values[6:]
                and existing[5] <= values[5]
            ):
                return  # Same vintage fetched again: retain its first retrieval.
            raise ValueError("Conflicting vintage: append a new vintage_id; do not overwrite.")
        self.conn.execute(
            """INSERT INTO observations VALUES
               (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            values,
        )
        self.conn.commit()

    # ----------------------------------------------------------------- read

    def as_of(
        self,
        series_id: str,
        asof: date,
        channel_id: str | None = None,
    ) -> pd.DataFrame:
        """Values for `series_id` as they were known on `asof`.

        Verified historical vintages use publication_ts. Comtrade snapshots
        and rows flagged publication_time_unknown use the later of retrieval
        and publication as a conservative availability bound. This also
        quarantines legacy Comtrade rows carrying the old assumed 23-day lag,
        without rewriting their provenance. Date-level resolution only.

        There is deliberately no `include_latest` or `override` parameter.
        """
        df = pd.read_sql_query(
            AS_OF_SQL,
            self.conn,
            params={"sid": series_id, "asof": asof.isoformat(), "cid": channel_id},
            parse_dates=["observation_ts", "publication_ts", "available_ts", "retrieval_ts"],
        )

        # Belt and braces: the guarantee is asserted, not just intended.
        if not df.empty and (df["available_ts"].dt.date > asof).any():
            raise LookAheadError(
                f"as_of({series_id!r}, {asof}) returned a row published later"
            )
        return df

    def revisions(self, series_id: str) -> pd.DataFrame:
        """Full revision history: magnitude, direction, and lag to final.

        Reported in FINDINGS.md. If a series revises enough to move the
        conclusion, that is a finding about Chinese data quality rather
        than something to hide.
        """
        df = pd.read_sql_query(
            """SELECT observation_ts, publication_ts, revision_number,
                      canonical_value
                 FROM observations
                WHERE canonical_series_id = ?
                ORDER BY observation_ts, publication_ts""",
            self.conn,
            params=(series_id,),
            parse_dates=["observation_ts", "publication_ts"],
        )
        if df.empty:
            return df
        first = df.groupby("observation_ts")["canonical_value"].transform("first")
        final = df.groupby("observation_ts")["canonical_value"].transform("last")
        df["revision_abs"] = final - first
        df["revision_rel"] = (final - first) / first.replace(0, pd.NA)
        df["lag_days"] = (df["publication_ts"] - df["observation_ts"]).dt.days
        return df

    def publication_lag(self, series_id: str) -> pd.Series:
        """Publication lag distribution for rows with verified release metadata.

        Excludes retrieval-bounded Comtrade/unknown-publication snapshots;
        their acquisition delay is not a measured statistical release lag.
        """
        df = pd.read_sql_query(
            """SELECT observation_ts, MIN(publication_ts) AS first_pub
                FROM observations
                WHERE canonical_series_id = ?
                  AND COALESCE(source_url, '') NOT LIKE '%comtradeapi.un.org/%'
                  AND COALESCE(quality_flags, '') NOT LIKE '%publication_time_unknown%'
                  AND COALESCE(quality_flags, '') NOT LIKE '%comtrade_free_tier%'
                GROUP BY observation_ts""",
            self.conn,
            params=(series_id,),
            parse_dates=["observation_ts", "first_pub"],
        )
        if df.empty:
            return pd.Series(dtype="int64")
        return (df["first_pub"] - df["observation_ts"]).dt.days.describe()
