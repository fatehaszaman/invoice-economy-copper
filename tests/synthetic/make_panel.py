"""Synthetic panel generator with a KNOWN effect, for estimator validation.

Used two ways:
  - plant beta = -1 and check the estimator recovers it
  - plant beta = 0 and check the estimator does NOT manufacture significance
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TIERS = {"high": 0.90, "moderate": 0.45, "low": 0.10}


def make_panel(
    beta: float = -1.0,
    n_periods: int = 240,
    post_frac: float = 0.4,
    noise: float = 0.20,
    channels_per_tier: int = 2,
    pretrend: float = 0.0,
    seed: int = 7,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    periods = pd.date_range("2025-09-01", periods=n_periods, freq="B")
    cut = int(n_periods * (1 - post_frac))

    rows = []
    for tier, exposure in TIERS.items():
        for k in range(channels_per_tier):
            cid = f"{tier}_{k}"
            alpha = rng.normal(0, 0.5)
            for i, t in enumerate(periods):
                post = i >= cut
                gamma = 0.01 * np.sin(i / 12)
                trend = pretrend * exposure * i / n_periods if not post else 0.0
                y = (
                    alpha
                    + gamma
                    + beta * float(post) * exposure
                    + trend
                    + rng.normal(0, noise)
                )
                rows.append(
                    {
                        "channel": cid,
                        "tier": tier,
                        "period": t,
                        "exposure": exposure,
                        "post": post,
                        "y": y,
                    }
                )
    return pd.DataFrame(rows)
