"""PCS sensitivity variants, pre-registered in `config/pcs.yaml`
(`sensitivity_variants`) and `DECISIONS.md` #5.

Falsification condition (`PREREGISTRATION.md` §6): "The result holds only
under one PCS weighting variant." This module computes PCS under each
variant so that check is answerable, rather than reporting a single
construction and asserting robustness by assumption.

Variant definitions used here — `equal` and `inverse_variance` are already
implemented in `pcs/blocks.py::block_mean` and simply passed through.
`leave_one_out` and `residual` are new and their exact construction was NOT
specified beyond a name in the frozen config, so the choices below are
recorded plainly rather than presented as equally pre-registered:

  - `leave_one_out`: recompute the block mean once per series with that one
    series excluded; report the resulting PCS range across all N leave-outs.
    This tests whether the result depends on any single series, which is
    the plain reading of the name.
  - `residual`: cross-sectional demeaning within each block before
    averaging — subtract, at each period, the mean across ALL series in
    BOTH blocks combined, so common shocks that move physical and
    commercial series together (e.g. a broad copper demand swing) are
    removed before the physical-minus-commercial contrast is taken. This is
    one reasonable reading of "residual construction" as a way to isolate
    the physical-versus-commercial wedge from a common factor; it is an
    interpretation, not a specification recovered from the repository, and
    should be reviewed against the author's original intent before being
    relied on for a reported result.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .blocks import block_mean
from .score import compute_pcs

VARIANTS = ("equal", "inverse_variance", "leave_one_out", "residual")


@dataclass(frozen=True)
class SensitivityResult:
    variant: str
    pcs: pd.Series  # indexed by date; NaN where unavailable
    detail: dict


def _leave_one_out(physical_z: pd.DataFrame, commercial_z: pd.DataFrame) -> SensitivityResult:
    variants = {}
    for block_name, z in (("physical", physical_z), ("commercial", commercial_z)):
        for dropped in z.columns:
            kept = z.drop(columns=[dropped])
            if kept.shape[1] == 0:
                continue
            mean, _ = block_mean(kept)
            variants[f"drop_{block_name}:{dropped}"] = mean

    if not variants:
        raise ValueError("need at least two series in some block to leave one out")

    p_mean, _ = block_mean(physical_z)
    c_mean, _ = block_mean(commercial_z)

    pcs_by_dropout = {}
    for key, series in variants.items():
        if key.startswith("drop_physical:"):
            pcs_by_dropout[key] = series - c_mean.reindex(series.index)
        else:
            pcs_by_dropout[key] = p_mean.reindex(series.index) - series

    frame = pd.DataFrame(pcs_by_dropout)
    central = p_mean - c_mean
    spread = frame.max(axis=1) - frame.min(axis=1)
    return SensitivityResult(
        variant="leave_one_out",
        pcs=central,
        detail={"range_by_date": spread, "per_dropout": frame},
    )


def _residual(physical_z: pd.DataFrame, commercial_z: pd.DataFrame) -> SensitivityResult:
    combined = pd.concat([physical_z, commercial_z], axis=1)
    common_factor = combined.mean(axis=1, skipna=True)

    phys_resid = physical_z.sub(common_factor, axis=0)
    comm_resid = commercial_z.sub(common_factor, axis=0)

    p_mean, p_cov = block_mean(phys_resid)
    c_mean, c_cov = block_mean(comm_resid)
    pcs = p_mean - c_mean
    return SensitivityResult(
        variant="residual",
        pcs=pcs,
        detail={
            "common_factor": common_factor,
            "physical_coverage": p_cov,
            "commercial_coverage": c_cov,
        },
    )


def compute_all_variants(
    physical_z: pd.DataFrame, commercial_z: pd.DataFrame
) -> dict[str, SensitivityResult]:
    out = {}

    equal = compute_pcs(physical_z, commercial_z, weights="equal")
    out["equal"] = SensitivityResult(variant="equal", pcs=equal["pcs"], detail={})

    try:
        inv = compute_pcs(physical_z, commercial_z, weights="inverse_variance")
        out["inverse_variance"] = SensitivityResult(
            variant="inverse_variance", pcs=inv["pcs"], detail={}
        )
    except ValueError:
        pass  # all-zero-variance series; not every panel supports this variant

    try:
        out["leave_one_out"] = _leave_one_out(physical_z, commercial_z)
    except ValueError:
        pass

    out["residual"] = _residual(physical_z, commercial_z)
    return out


def coverage_floor_sensitivity(
    physical_z: pd.DataFrame,
    commercial_z: pd.DataFrame,
    floors: tuple[float, ...] = (0.50, 0.60, 0.70),
) -> pd.DataFrame:
    """DECISIONS.md #5: report the coverage floor at 0.50 and 0.70 alongside
    the pre-registered 0.60, so a result is not an artefact of exactly where
    that line was drawn."""
    rows = {}
    for floor in floors:
        out = compute_pcs(physical_z, commercial_z, coverage_floor=floor)
        rows[floor] = out["confidence"].value_counts()
    return pd.DataFrame(rows).fillna(0).astype(int)


def sign_agreement(results: dict[str, SensitivityResult]) -> bool:
    """Falsification check: does every variant agree on the sign of the
    mean PCS over the periods where it is defined? A single dissenting
    variant, per PREREGISTRATION.md §6, is enough to trigger the condition.
    """
    means = []
    for r in results.values():
        v = r.pcs.dropna()
        if not v.empty:
            means.append(float(v.mean()))
    if len(means) < 2:
        return False
    signs = {m > 0 for m in means}
    return len(signs) == 1
