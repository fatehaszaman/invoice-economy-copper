"""Pre-trend test. This is a KILL CONDITION, not a footnote.

If high- and low-exposure channels were already diverging before t_A, the
design cannot attribute the post-event divergence to enforcement, and
PREREGISTRATION.md commits to reporting the hypothesis as rejected.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PretrendResult:
    slope: float
    t_stat: float
    p_value: float
    passes: bool
    n_obs: int

    def __repr__(self) -> str:  # pragma: no cover
        verdict = "PASS" if self.passes else "FAIL — design invalid"
        return f"PretrendResult({verdict}, slope={self.slope:.5f}, p={self.p_value:.4f})"


def check_pretrends(
    panel: pd.DataFrame,
    outcome: str = "y",
    alpha: float = 0.10,
) -> PretrendResult:
    """Regress the exposure-weighted outcome on time, PRE-event only.

    A slope indistinguishable from zero is required. The test is deliberately
    run at a lenient alpha, because here a false alarm is cheaper than a
    missed pre-trend.
    """
    from scipy import stats

    pre = panel[~panel["post"].astype(bool)].dropna(subset=[outcome]).copy()
    if pre.empty:
        raise ValueError("no pre-event observations")

    pre["t"] = pd.factorize(np.sort(pre["period"].astype(str)).searchsorted(
        pre["period"].astype(str)))[0].astype(float)
    pre["weighted"] = pre[outcome] * pre["exposure"]

    g = pre.groupby("t")["weighted"].mean().dropna()
    if len(g) < 5:
        raise ValueError("too few pre-event periods for a pre-trend test")

    res = stats.linregress(g.index.to_numpy(dtype=float), g.to_numpy(dtype=float))
    return PretrendResult(
        slope=float(res.slope),
        t_stat=float(res.slope / res.stderr) if res.stderr else float("nan"),
        p_value=float(res.pvalue),
        passes=bool(res.pvalue > alpha),
        n_obs=int(len(pre)),
    )
