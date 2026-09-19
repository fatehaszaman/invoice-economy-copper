"""Permutation of exposure labels across channels.

With few channels this is the honest cross-sectional test. It asks how
special the ACTUAL exposure labelling is, without relying on asymptotic
approximations that a handful of clusters cannot support.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .exposure import fit_exposure


def permutation_test(
    panel: pd.DataFrame,
    outcome: str = "y",
    n_perm: int = 2000,
    seed: int = 20260424,
) -> dict:
    """Reassign exposure values across channels; refit; locate the real beta."""
    rng = np.random.default_rng(seed)
    actual = fit_exposure(panel, outcome=outcome, cluster=False).beta

    chan = panel[["channel", "exposure"]].drop_duplicates().reset_index(drop=True)
    exposures = chan["exposure"].to_numpy(dtype=float)
    channels = chan["channel"].to_numpy()

    null = []
    for _ in range(n_perm):
        shuffled = rng.permutation(exposures)
        mapping = dict(zip(channels, shuffled, strict=True))
        p = panel.copy()
        p["exposure"] = p["channel"].map(mapping)
        try:
            null.append(fit_exposure(p, outcome=outcome, cluster=False).beta)
        except ValueError:
            continue

    null_arr = np.asarray(null, dtype=float)
    # Two-sided: how often is a permuted |beta| at least as large?
    p_value = float((np.abs(null_arr) >= abs(actual)).mean())
    pct = float((null_arr < actual).mean() * 100)

    return {
        "beta_actual": float(actual),
        "p_value": p_value,
        "percentile_in_null": pct,
        "n_permutations": int(null_arr.size),
        "null_mean": float(null_arr.mean()),
        "null_sd": float(null_arr.std(ddof=1)),
    }
