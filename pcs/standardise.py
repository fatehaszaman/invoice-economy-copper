"""Rolling standardisation using only prior information.

Full-sample normalisation would leak the event into the pre-event window.
The window is also required not to overlap the event window, and the
function refuses rather than warns.
"""
from __future__ import annotations

from datetime import date

import pandas as pd


class WindowOverlapError(RuntimeError):
    """Raised when a normalisation window overlaps the event window."""


def rolling_z(s: pd.Series, window: int = 252, min_periods: int | None = None) -> pd.Series:
    """z_t = (x_t - mu_{t-1}) / sigma_{t-1}.

    Mean and standard deviation are shifted by one observation so that the
    value being standardised is never part of its own moments.
    """
    mp = min_periods or max(20, window // 4)
    mu = s.rolling(window, min_periods=mp).mean().shift(1)
    sd = s.rolling(window, min_periods=mp).std(ddof=1).shift(1)
    return (s - mu) / sd.replace(0, pd.NA)


def assert_no_event_overlap(index: pd.DatetimeIndex, window: int, event_start: date) -> None:
    """Refuse a normalisation window that reaches into the event window."""
    pre = index[index < pd.Timestamp(event_start)]
    if len(pre) < window:
        raise WindowOverlapError(
            f"normalisation window of {window} observations cannot be filled from "
            f"{len(pre)} pre-event observations without overlapping the event at "
            f"{event_start}; shorten the window or extend the history"
        )
