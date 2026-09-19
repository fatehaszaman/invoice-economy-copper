"""Placebo tests: pre-registered falsification conditions, not robustness
theater.

Two distinct placebos, both named in `PREREGISTRATION.md` §6 and both
required to come back null for the hypothesis to survive:

  1. **Placebo dates** — re-run the same estimator with the event date moved
     to one of the four dates fixed in `config/events.yaml` before any
     estimation (2025-04-24, 2025-10-24, 2024-04-24, 2026-01-24). A real
     enforcement effect should not appear at a date nothing happened.
  2. **Negative-control metals** — aluminium and lead (`config/events.yaml`
     `negative_control_metals`) share China's tax environment but were not
     targeted by the 2026 invoice enforcement action. A `beta` of similar
     size there would mean the estimator is picking up something economy-
     wide, not the copper-specific channel this project claims.

**What this module can and cannot do on real data, right now**: both tests
need a per-channel outcome panel with the same `channel / period / exposure
/ post / outcome` shape `research/exposure.py` expects. That panel does not
exist for copper (see README "Live ingestion status") and does not exist AT
ALL for aluminium or lead — no public source publishes invoice-exposure-
tiered channel activity for any of these three metals at the intermediary
level this design needs. So `run_placebo_dates` and `run_negative_control`
below are fully implemented and tested against the synthetic generator
(`tests/synthetic/make_panel.py`), which is genuinely useful — it is what
proves the machinery does not manufacture an effect at a placebo date on
data with none planted — but calling either with a real panel is not
possible until that panel exists. Do not point this at fabricated
per-channel data to make `make robustness` "pass"; an empty, clearly
labelled gap is worth more than a plausible-looking null run on invented
numbers.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .exposure import fit_by_tier, fit_exposure
from .monotonicity import check_monotonicity


@dataclass(frozen=True)
class PlaceboResult:
    label: str
    beta: float
    ordered_as_predicted: bool
    passes: bool  # True = placebo behaved as a placebo should (no effect)

    def __repr__(self) -> str:  # pragma: no cover
        verdict = "PASS (null, as expected)" if self.passes else "FAIL — placebo found an effect"
        return f"PlaceboResult({self.label!r}, {verdict}, beta={self.beta:+.4f})"


def _repost(panel: pd.DataFrame, placebo_period) -> pd.DataFrame:
    """Relabel `post` around a placebo event date instead of the real one."""
    d = panel.copy()
    d["post"] = d["period"] >= pd.Timestamp(placebo_period)
    return d


def run_placebo_dates(
    panel: pd.DataFrame,
    placebo_dates: list,
    beta_tolerance: float = 0.15,
) -> list[PlaceboResult]:
    """Re-estimate at each placebo date. Passes when |beta| stays below
    `beta_tolerance` — a small drift is expected noise, not a finding."""
    out = []
    for d in placebo_dates:
        relabelled = _repost(panel, d)
        try:
            fit = fit_exposure(relabelled, cluster=False)
        except ValueError:
            continue  # no within-variation at this cut — not a placebo failure
        out.append(
            PlaceboResult(
                label=f"placebo_date={pd.Timestamp(d).date()}",
                beta=fit.beta,
                ordered_as_predicted=False,
                passes=abs(fit.beta) < beta_tolerance,
            )
        )
    return out


def run_negative_control(
    control_panel: pd.DataFrame,
    metal_label: str,
    beta_tolerance: float = 0.15,
) -> PlaceboResult:
    """Same estimator, same real event date, applied to a metal that was not
    targeted by enforcement. `control_panel` must use copper's own real
    t_A/t_B for `post` (not a placebo date) — the metal is what's swapped.
    """
    fit = fit_exposure(control_panel, cluster=False)
    try:
        mono = check_monotonicity(fit_by_tier(control_panel))
        ordered = mono.ordered_as_predicted
    except ValueError:
        ordered = False
    return PlaceboResult(
        label=f"negative_control={metal_label}",
        beta=fit.beta,
        ordered_as_predicted=ordered,
        passes=abs(fit.beta) < beta_tolerance and not ordered,
    )
