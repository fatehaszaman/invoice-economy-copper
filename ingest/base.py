"""Fetcher base: retry, immutable raw archival, provenance.

Every observation keeps the raw bytes it came from, content-addressed by
hash, so every reported number traces back to a payload and a URL.
"""
from __future__ import annotations

import hashlib
import json
import time
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path

ARCHIVE = Path(__file__).resolve().parent / "archive"


class Fetcher(ABC):
    source: str
    license_class: str = "public"

    def __init__(self, archive: Path | None = None) -> None:
        self.archive = archive or ARCHIVE
        self.archive.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------ contract

    @abstractmethod
    def endpoints(self) -> list[str]:
        """URLs this fetcher reads."""

    @abstractmethod
    def parse(self, payload: bytes, url: str) -> list[dict]:
        """Raw payload -> canonical observation dicts. Pure; no I/O."""

    # ------------------------------------------------------------- archive

    def store_raw(self, payload: bytes, url: str) -> str:
        """Archive raw bytes immutably, content-addressed. Returns the hash."""
        digest = hashlib.sha256(payload).hexdigest()
        blob = self.archive / f"{digest}.bin"
        if not blob.exists():
            blob.write_bytes(payload)
            (self.archive / f"{digest}.meta.json").write_text(
                json.dumps(
                    {
                        "source": self.source,
                        "url": url,
                        "retrieved_at": datetime.now(UTC).isoformat(
                            timespec="seconds"
                        ),
                        "bytes": len(payload),
                        "license_class": self.license_class,
                    },
                    indent=2,
                )
            )
        return digest

    def fetch_with_retry(self, url: str, attempts: int = 4, base_delay: float = 1.5):
        """Exponential backoff. Raises the last error if all attempts fail."""
        last: Exception | None = None
        for i in range(attempts):
            try:
                return self._get(url)
            except Exception as exc:  # noqa: BLE001 - re-raised below
                last = exc
                if i < attempts - 1:
                    time.sleep(base_delay ** (i + 1))
        raise RuntimeError(f"{self.source}: all {attempts} attempts failed for {url}") from last

    def _get(self, url: str) -> bytes:  # pragma: no cover - network boundary
        import urllib.request

        with urllib.request.urlopen(url, timeout=30) as resp:
            return resp.read()


class LicensedDataUnavailable(RuntimeError):
    """Raised when licensed data is absent.

    The pipeline degrades to a documented fallback mode and LABELS the
    affected results. It does not silently substitute a different source.
    """
