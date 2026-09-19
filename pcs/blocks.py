"""Block means over AVAILABLE series only. No imputation, ever.

Missing data reduces coverage and says so. A pipeline that imputes its way
to a complete-looking panel would hide exactly the gaps this project exists
to measure.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def block_mean(z: pd.DataFrame, weights: str = "equal") -> tuple[pd.Series, pd.Series]:
    """Return (block mean, coverage ratio) per period.

    z: DataFrame of standardised series, columns = series ids.
    Coverage is computed against the number of EXPECTED series (all columns),
    not the number present, so a thin period is visible rather than flattering.
    """
    n_expected = z.shape[1]
    if n_expected == 0:
        raise ValueError("block has no series")

    available = z.notna()
    coverage = available.sum(axis=1) / n_expected

    if weights == "equal":
        mean = z.mean(axis=1, skipna=True)
    elif weights == "inverse_variance":
        var = z.var(axis=0, ddof=1)
        w = (1.0 / var.replace(0, np.nan)).fillna(0.0)
        if w.sum() == 0:
            raise ValueError("inverse-variance weights are all zero")
        mean = (z * w).sum(axis=1, min_count=1) / (available * w).sum(axis=1).replace(0, np.nan)
    else:
        raise ValueError(f"unknown weighting {weights!r}")

    # A period with no available series has no mean, not a zero.
    mean = mean.where(coverage > 0)
    return mean, coverage
