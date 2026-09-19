"""SHIBOR fetcher — onshore rates, CNH forwards, USD funding.

**Status: verified unreachable from this build environment.** Every
request to `shibor.org` from this sandbox — plain `curl`, `curl` with a
full browser user agent, and a real CDP-driven browser navigation — either
returns HTTP 403 or the connection itself times out with no response. This
looks like a network-level block on this environment's egress IP rather
than a page-level bot check, since even the outer HTML shell never loads.

SHIBOR does not feed the core PCS score (no series in `config/pcs.yaml`
blocks sources from it); it is listed in the README as background financing
context for the eventual `research/confounders.py` ladder. Its absence
therefore does not lower PCS coverage, but the financing-activity
confounder cannot be tested against real rates until this is resolved.

Left as a stub with the real contract so a future run from an unblocked
network can implement `parse()` against the actual page/CSV shape, which
was never observed and so is not guessed at here.
"""
from __future__ import annotations

from .base import Fetcher

CANDIDATE_URL = "https://www.shibor.org/shibor/web/html/shibor.html"


class ShiborUnavailable(RuntimeError):
    """Raised instead of a silent empty result. See module docstring."""


class ShiborFetcher(Fetcher):
    source = "shibor"
    license_class = "public"

    def endpoints(self) -> list[str]:
        return [CANDIDATE_URL]

    def parse(self, payload: bytes, url: str) -> list[dict]:
        raise ShiborUnavailable(
            "No live SHIBOR payload has ever been observed from this build "
            "environment, so no parser has been written against a real "
            "response shape."
        )

    def fetch_all(self) -> list[dict]:
        raise ShiborUnavailable(
            "shibor.org is unreachable from this build environment (403 or "
            "connection timeout on every attempt, including a full browser "
            "session). Re-run from a network that can reach it."
        )
