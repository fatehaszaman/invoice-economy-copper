"""PCS = mean_z(physical) - mean_z(commercial).

The original sign convention is retained: a negative value means the
standardized commercial-block average exceeds the physical-block average.
It does not establish physical corroboration, causality, fraud, financing
or predictive power. Economic interpretation remains a research hypothesis;
similar block averages can conceal offsetting individual series.
"""
from __future__ import annotations

import pandas as pd

from .blocks import block_mean
from .coverage import ScoreRecord, label_confidence


def compute_pcs(
    physical_z: pd.DataFrame,
    commercial_z: pd.DataFrame,
    weights: str = "equal",
    coverage_floor: float = 0.60,
    source_age_days: pd.Series | None = None,
) -> pd.DataFrame:
    """Compute PCS with coverage metadata attached to every value."""
    p_mean, p_cov = block_mean(physical_z, weights=weights)
    c_mean, c_cov = block_mean(commercial_z, weights=weights)

    idx = p_mean.index.union(c_mean.index)
    p_mean, c_mean = p_mean.reindex(idx), c_mean.reindex(idx)
    p_cov, c_cov = p_cov.reindex(idx).fillna(0.0), c_cov.reindex(idx).fillna(0.0)

    pcs = p_mean - c_mean

    records = []
    for t in idx:
        conf = label_confidence(float(p_cov[t]), float(c_cov[t]), floor=coverage_floor)
        age = None
        if source_age_days is not None and t in source_age_days.index:
            v = source_age_days.get(t)
            age = None if pd.isna(v) else int(v)
        records.append(
            ScoreRecord(
                date=pd.Timestamp(t).date().isoformat(),
                pcs=None if pd.isna(pcs[t]) else float(pcs[t]),
                physical_score=None if pd.isna(p_mean[t]) else float(p_mean[t]),
                commercial_score=None if pd.isna(c_mean[t]) else float(c_mean[t]),
                physical_coverage=round(float(p_cov[t]), 4),
                commercial_coverage=round(float(c_cov[t]), 4),
                max_source_age_days=age,
                confidence=conf,
            ).to_dict()
        )

    out = pd.DataFrame.from_records(records)
    out["date"] = pd.to_datetime(out["date"])
    return out.set_index("date")
