"""Coverage, staleness, and confidence labelling.

A PCS value without coverage metadata is incomplete, and the system treats
it as such rather than reporting a bare number.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

COVERAGE_FLOOR_DEFAULT = 0.60


@dataclass(frozen=True)
class ScoreRecord:
    date: str
    pcs: float | None
    physical_score: float | None
    commercial_score: float | None
    physical_coverage: float
    commercial_coverage: float
    max_source_age_days: int | None
    confidence: str

    def to_dict(self) -> dict:
        return asdict(self)


def label_confidence(
    physical_coverage: float,
    commercial_coverage: float,
    floor: float = COVERAGE_FLOOR_DEFAULT,
) -> str:
    """Pre-registered floor. Below it, scores are excluded from primary estimation."""
    if physical_coverage >= floor and commercial_coverage >= floor:
        return "valid"
    if physical_coverage == 0 or commercial_coverage == 0:
        return "unavailable"
    return "low_confidence"
