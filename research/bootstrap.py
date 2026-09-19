"""Block bootstrap over time blocks.

An i.i.d. bootstrap would destroy the serial dependence present in daily
commodity series and understate uncertainty. Blocks preserve it.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .exposure import fit_exposure


def block_bootstrap_beta(
    panel: pd.DataFrame,
    outcome: str = "y",
    block_len: int = 20,
    n_boot: int = 1000,
    seed: int = 20260424,
) -> np.ndarray:
    """Resample contiguous time blocks; refit; return the beta distribution."""
    rng = np.random.default_rng(seed)
    periods = np.sort(panel["period"].unique())
    n_blocks = max(1, int(np.ceil(len(periods) / block_len)))
    starts = np.arange(0, len(periods), block_len)

    betas = []
    for _ in range(n_boot):
        chosen = rng.choice(starts, size=n_blocks, replace=True)
        picks = [periods[s : s + block_len] for s in chosen]
        sel = np.concatenate(picks)
        # Relabel periods so repeated blocks are distinct fixed effects
        frames = []
        for k, blk in enumerate(picks):
            part = panel[panel["period"].isin(blk)].copy()
            part["period"] = part["period"].astype(str) + f"__b{k}"
            frames.append(part)
        boot = pd.concat(frames, ignore_index=True)
        try:
            betas.append(fit_exposure(boot, outcome=outcome, cluster=False).beta)
        except ValueError:
            continue
    return np.asarray(betas, dtype=float)


def percentile_ci(betas: np.ndarray, level: float = 0.90) -> tuple[float, float]:
    lo = (1 - level) / 2 * 100
    return float(np.percentile(betas, lo)), float(np.percentile(betas, 100 - lo))
