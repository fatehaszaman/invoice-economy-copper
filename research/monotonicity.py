"""Monotonicity across exposure intensity: the PRIMARY reported result.

Enforcement was national, so no copper channel is untreated and "low
exposure" means less treated rather than clean. The claim is therefore an
ordering, not a magnitude:

    |effect_high| > |effect_moderate| > |effect_low|

A confounder that explains this must happen to align with the exposure
ranking, which is much harder to wave away than a single binary gap.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

TIER_ORDER = ["low", "moderate", "high"]


@dataclass(frozen=True)
class MonotonicityResult:
    effects: pd.Series
    spearman_rho: float
    spearman_p: float
    ordered_as_predicted: bool
    n_tiers: int

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"MonotonicityResult(ordered={self.ordered_as_predicted}, "
            f"rho={self.spearman_rho:.3f}, p={self.spearman_p:.4f})"
        )


def check_monotonicity(effects: pd.Series, expect_negative: bool = True) -> MonotonicityResult:
    """Rank-test the ordering of effects against exposure intensity.

    expect_negative: the pre-registered direction. Commercial activity in
    high-exposure channels is predicted to contract, so effects become MORE
    negative as exposure rises.
    """
    present = [t for t in TIER_ORDER if t in effects.index]
    if len(present) < 3:
        raise ValueError(
            f"monotonicity needs all three tiers; got {present}. "
            "Reporting an ordering across two points is not evidence of one."
        )
    e = effects.reindex(present)
    rank = np.arange(len(present), dtype=float)  # low=0, moderate=1, high=2

    rho, p = stats.spearmanr(rank, e.to_numpy(dtype=float))

    if expect_negative:
        ordered = bool(np.all(np.diff(e.to_numpy(dtype=float)) < 0))
    else:
        ordered = bool(np.all(np.diff(e.to_numpy(dtype=float)) > 0))

    return MonotonicityResult(
        effects=e,
        spearman_rho=float(rho),
        spearman_p=float(p),
        ordered_as_predicted=ordered,
        n_tiers=len(present),
    )
