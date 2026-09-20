"""Stationary transforms. Choice per series is read from config, never chosen
by looking at results."""
from __future__ import annotations

import numpy as np
import pandas as pd

TRANSFORMS = ("log_diff", "diff", "pct", "level", "surprise")


def apply_transform(s: pd.Series, kind: str) -> pd.Series:
    if kind not in TRANSFORMS:
        raise ValueError(f"unknown transform {kind!r}; declared options {TRANSFORMS}")
    if kind == "log_diff":
        pos = s.where(s > 0)
        return np.log(pos).diff()
    if kind == "diff":
        return s.diff()
    if kind == "pct":
        return s.pct_change(fill_method=None)
    if kind == "level":
        return s.astype(float)
    raise ValueError("surprise transform requires an expectation series; use surprise()")


def surprise(actual: pd.Series, expected: pd.Series) -> pd.Series:
    """Economic surprise. Requires a declared expectation, not a fitted one."""
    return actual - expected.reindex(actual.index)
