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
  - `residual`: unavailable pending a specified factor model. The earlier
    common-factor subtraction was algebraically identical to the baseline:
    (P-F)-(C-F) = P-C. It must not count as independent robustness evidence.

These are descriptive sensitivity diagnostics, not causal falsification
tests. Inverse-variance weighting uses the supplied sample and is not a
historical real-time weighting rule.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .score import compute_pcs

VARIANTS = ("equal", "inverse_variance", "leave_one_out", "residual")


@dataclass(frozen=True)
class SensitivityResult:
    variant: str
    pcs: pd.Series  # indexed by date; NaN where unavailable
    detail: dict
    status: str = "available"


def _eligible(frame: pd.DataFrame) -> pd.Series:
    return pd.to_numeric(frame["pcs"], errors="coerce").where(frame["confidence"] == "valid")


def _leave_one_out(
    physical_z: pd.DataFrame, commercial_z: pd.DataFrame, coverage_floor: float,
) -> SensitivityResult:
    pcs_by_dropout = {}
    for block_name, z in (("physical", physical_z), ("commercial", commercial_z)):
        for dropped in z.columns:
            kept = z.drop(columns=[dropped])
            if kept.shape[1] == 0:
                continue
            p = kept if block_name == "physical" else physical_z
            c = kept if block_name == "commercial" else commercial_z
            frame = compute_pcs(p, c, coverage_floor=coverage_floor)
            pcs_by_dropout[f"drop_{block_name}:{dropped}"] = _eligible(frame)

    if not pcs_by_dropout:
        raise ValueError("need at least two series in some block to leave one out")

    frame = pd.DataFrame(pcs_by_dropout)
    central = _eligible(compute_pcs(physical_z, commercial_z, coverage_floor=coverage_floor))
    spread = (frame.max(axis=1) - frame.min(axis=1)).where(frame.notna().all(axis=1))
    return SensitivityResult(
        variant="leave_one_out",
        pcs=central,
        detail={"range_by_date": spread, "per_dropout": frame},
    )


def _residual(physical_z: pd.DataFrame, commercial_z: pd.DataFrame) -> SensitivityResult:
    return SensitivityResult(
        variant="residual",
        pcs=pd.Series(float("nan"), index=physical_z.index.union(commercial_z.index)),
        detail={
            "reason": "No independent factor model specified; common subtraction cancels."
        },
        status="not_specified",
    )


def compute_all_variants(
    physical_z: pd.DataFrame, commercial_z: pd.DataFrame, coverage_floor: float = 0.60,
) -> dict[str, SensitivityResult]:
    out = {}

    equal = compute_pcs(physical_z, commercial_z, weights="equal", coverage_floor=coverage_floor)
    out["equal"] = SensitivityResult(variant="equal", pcs=_eligible(equal), detail={})

    try:
        inv = compute_pcs(
            physical_z, commercial_z, weights="inverse_variance", coverage_floor=coverage_floor
        )
        out["inverse_variance"] = SensitivityResult(
            variant="inverse_variance", pcs=_eligible(inv), detail={}
        )
    except ValueError as error:
        out["inverse_variance"] = SensitivityResult(
            "inverse_variance", _eligible(equal) * float("nan"),
            {"reason": str(error)}, status="unavailable",
        )

    try:
        out["leave_one_out"] = _leave_one_out(physical_z, commercial_z, coverage_floor)
    except ValueError as error:
        out["leave_one_out"] = SensitivityResult(
            "leave_one_out", _eligible(equal) * float("nan"),
            {"reason": str(error)}, status="unavailable",
        )

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
    """Conservative diagnostic, NOT a causal falsification verdict.

    Require every declared variant, a specified model, and common valid
    periods. Also check each leave-one-out path rather than counting the
    baseline again. False can mean unavailable/inconclusive, not disagreement.
    """
    if not set(VARIANTS) <= results.keys():
        return False
    columns = {}
    for name in VARIANTS:
        result = results[name]
        if result.status != "available":
            return False
        columns[name] = result.pcs
        if name == "leave_one_out":
            dropouts = result.detail.get("per_dropout")
            if dropouts is None or dropouts.empty:
                return False
            columns.update({f"loo:{col}": dropouts[col] for col in dropouts})
    common = pd.DataFrame(columns).dropna()
    if common.empty:
        return False
    signs = {0 if mean == 0 else (1 if mean > 0 else -1) for mean in common.mean()}
    return len(signs) == 1
