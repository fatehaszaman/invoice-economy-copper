"""Exposure-intensity estimation with two-way fixed effects.

Y_{i,t} = alpha_i + gamma_t + beta * (Post_t * Exposure_i) + eps_{i,t}

Treatment is PRE-EXISTING INVOICE EXPOSURE, not material type. A
scrap-versus-cathode design was considered and rejected before estimation:
invoice friction pushes buyers from scrap toward cathode, so cathode is an
outcome of the treatment rather than a control. See MISTAKES.md.

Exposure values are loaded from config/exposure.yaml, which was committed
with PREREGISTRATION.md before this file existed. They are never hardcoded
here, where they could drift unnoticed.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

CONFIG = Path(__file__).resolve().parent.parent / "config" / "exposure.yaml"


def load_exposure(path: Path | None = None) -> pd.DataFrame:
    cfg = yaml.safe_load((path or CONFIG).read_text())
    df = pd.DataFrame(cfg["channels"]).set_index("id")
    if not df["exposure"].between(0, 1).all():
        raise ValueError("exposure must lie in [0,1]")
    return df


@dataclass(frozen=True)
class FitResult:
    beta: float
    se_cluster: float | None
    n_obs: int
    n_channels: int
    resid: np.ndarray

    def __repr__(self) -> str:  # pragma: no cover
        se = "n/a" if self.se_cluster is None else f"{self.se_cluster:.4f}"
        return (
            f"FitResult(beta={self.beta:.4f}, se_cluster={se}, "
            f"n_obs={self.n_obs}, n_channels={self.n_channels})"
        )


def _demean_two_way(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Absorb channel and period fixed effects by iterative demeaning."""
    out = df.copy()
    for _ in range(50):
        before = out[cols].to_numpy(copy=True)
        out[cols] = out[cols] - out.groupby("channel")[cols].transform("mean")
        out[cols] = out[cols] - out.groupby("period")[cols].transform("mean")
        if np.nanmax(np.abs(out[cols].to_numpy() - before)) < 1e-12:
            break
    return out


def fit_exposure(
    panel: pd.DataFrame,
    outcome: str = "y",
    cluster: bool = True,
) -> FitResult:
    """Two-way fixed effects estimate of the exposure interaction.

    panel columns required: channel, period, exposure, post, <outcome>
    """
    need = {"channel", "period", "exposure", "post", outcome}
    missing = need - set(panel.columns)
    if missing:
        raise ValueError(f"panel missing columns: {sorted(missing)}")

    d = panel.dropna(subset=[outcome]).copy()
    d["interaction"] = d["post"].astype(float) * d["exposure"].astype(float)

    dm = _demean_two_way(d, [outcome, "interaction"])
    x = dm["interaction"].to_numpy(dtype=float)
    y = dm[outcome].to_numpy(dtype=float)

    denom = float(x @ x)
    if denom <= 1e-12:
        raise ValueError(
            "no within-variation in the interaction after absorbing fixed effects"
        )
    beta = float(x @ y) / denom
    resid = y - beta * x

    se = None
    if cluster:
        # Cluster-robust by channel. SECONDARY ONLY: with few clusters these
        # asymptotics are unreliable. Permutation inference carries the weight.
        groups = d["channel"].to_numpy()
        meat = 0.0
        for g in np.unique(groups):
            m = groups == g
            meat += float((x[m] @ resid[m]) ** 2)
        n_g = len(np.unique(groups))
        if n_g > 1:
            scale = n_g / (n_g - 1)
            se = float(np.sqrt(scale * meat / denom**2))

    return FitResult(
        beta=beta,
        se_cluster=se,
        n_obs=len(d),
        n_channels=int(d["channel"].nunique()),
        resid=resid,
    )


def fit_by_tier(panel: pd.DataFrame, outcome: str = "y") -> pd.Series:
    """Post-minus-pre change in the outcome, by exposure tier.

    Used by monotonicity.py. Reported as the ordering across tiers rather
    than as a treated-versus-control contrast, because enforcement was
    national and no channel is untreated.
    """
    d = panel.dropna(subset=[outcome])
    pre = d[~d["post"].astype(bool)].groupby("tier")[outcome].mean()
    post = d[d["post"].astype(bool)].groupby("tier")[outcome].mean()
    return (post - pre).rename("effect")
