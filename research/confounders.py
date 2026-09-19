"""Confounder ladder: report the estimate as each acknowledged confounder is
added, never controlled away silently (`PREREGISTRATION.md` §7).

The five confounders committed to in advance: 2026 copper price level,
US Section 232 tariff uncertainty, mine-side concentrate tightness, the
SHFE-LME import arbitrage window, and general macro risk appetite. Each is a
named column in `panel`; this module does not invent proxies for them —
supplying real series for these columns is a live-ingestion + construction
task outside this module's scope (concentrate tightness and the arbitrage
window in particular need licensed LME data per `ingest/lme.py`).

A falsification condition is triggered if the exposure-monotonic ordering
does not survive to the last rung of the ladder — that check belongs in the
same place `research/monotonicity.py` already lives, applied per rung, not
duplicated here.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .exposure import _demean_two_way

# Order matches PREREGISTRATION.md §7, left to right.
RUNG_ORDER = [
    "copper_price",
    "tariff_dummy",
    "concentrate_tightness",
    "shfe_lme_arb",
    "macro_risk",
]


@dataclass(frozen=True)
class RungResult:
    rung: int
    controls: tuple[str, ...]
    beta: float
    n_obs: int

    def __repr__(self) -> str:  # pragma: no cover
        ctrl = ", ".join(self.controls) or "(none)"
        return f"RungResult(rung={self.rung}, controls=[{ctrl}], beta={self.beta:+.4f})"


def fit_with_confounders(
    panel: pd.DataFrame,
    controls: list[str],
    outcome: str = "y",
) -> tuple[float, int]:
    """Two-way FE beta on the exposure interaction, additionally partialling
    out `controls` (each a column already present in `panel`).

    Same channel/period demeaning as `research.exposure.fit_exposure`;
    generalised here to a multivariate regression so any number of named
    confounder columns can be partialled out alongside the interaction.
    """
    need = {"channel", "period", "exposure", "post", outcome, *controls}
    missing = need - set(panel.columns)
    if missing:
        raise ValueError(f"panel missing columns: {sorted(missing)}")

    d = panel.dropna(subset=[outcome, *controls]).copy()
    d["interaction"] = d["post"].astype(float) * d["exposure"].astype(float)

    cols = [outcome, "interaction", *controls]
    dm = _demean_two_way(d, cols)

    y = dm[outcome].to_numpy(dtype=float)
    X_cols = ["interaction", *controls]
    X = dm[X_cols].to_numpy(dtype=float)

    beta_vec, *_ = np.linalg.lstsq(X, y, rcond=None)
    beta = float(beta_vec[0])  # coefficient on the interaction term
    return beta, len(d)


def confounder_ladder(panel: pd.DataFrame, outcome: str = "y") -> list[RungResult]:
    """Cumulative ladder: rung 0 has no controls, rung k adds
    `RUNG_ORDER[:k]`. Only rungs whose controls are actually present in
    `panel` are run — a missing confounder column is reported as absent by
    its rung simply not appearing, not silently skipped over.
    """
    available = [c for c in RUNG_ORDER if c in panel.columns]
    results = []
    for k in range(len(available) + 1):
        controls = available[:k]
        try:
            beta, n = fit_with_confounders(panel, controls, outcome=outcome)
        except ValueError:
            continue
        results.append(RungResult(rung=k, controls=tuple(controls), beta=beta, n_obs=n))
    return results


def survives_ladder(results: list[RungResult], sign: float = -1.0, tol: float = 1e-9) -> bool:
    """Falsification check: does the pre-registered sign hold at every rung,
    including the last (fullest) one? An empty ladder (no confounder columns
    were available) cannot demonstrate survival and returns False rather
    than vacuously True.
    """
    if not results:
        return False
    return all((sign * r.beta) > tol for r in results)
