"""PCS sensitivity variants: leave-one-out, residual construction, coverage
floor grid."""
import numpy as np
import pandas as pd

from pcs.sensitivity import (
    compute_all_variants,
    coverage_floor_sensitivity,
    sign_agreement,
)

IDX = pd.date_range("2026-01-01", periods=12, freq="D")


def _panel():
    phys = pd.DataFrame(
        {"a": np.zeros(12), "b": np.full(12, 0.2)}, index=IDX
    )
    comm = pd.DataFrame(
        {"x": np.full(12, 2.0), "y": np.full(12, 2.2)}, index=IDX
    )
    return phys, comm


def test_all_variants_present():
    phys, comm = _panel()
    results = compute_all_variants(phys, comm)
    assert {"equal", "residual", "leave_one_out"} <= set(results.keys())


def test_leave_one_out_reports_a_range_not_a_point():
    phys, comm = _panel()
    results = compute_all_variants(phys, comm)
    loo = results["leave_one_out"]
    assert "range_by_date" in loo.detail
    assert (loo.detail["range_by_date"] >= 0).all()


def test_residual_removes_a_perfectly_common_shock():
    """If physical and commercial move by an identical common shock on top
    of their fixed gap, the residual variant's PCS must be flat (shock
    fully removed), unlike the raw equal-weight PCS which is not required to be."""
    shock = pd.Series(np.linspace(0, 5, 12), index=IDX)
    phys = pd.DataFrame({"a": shock, "b": shock}, index=IDX)
    comm = pd.DataFrame({"x": shock + 2.0, "y": shock + 2.0}, index=IDX)
    results = compute_all_variants(phys, comm)
    resid_pcs = results["residual"].pcs.dropna()
    assert resid_pcs.std() < 1e-9


def test_sign_agreement_true_when_variants_agree():
    phys, comm = _panel()
    results = compute_all_variants(phys, comm)
    assert sign_agreement(results) is True


def test_sign_agreement_false_when_variants_disagree():
    results = {
        "a": type("R", (), {"pcs": pd.Series([1.0, 2.0])})(),
        "b": type("R", (), {"pcs": pd.Series([-1.0, -2.0])})(),
    }
    assert sign_agreement(results) is False


def test_coverage_floor_sensitivity_reports_three_floors():
    phys, comm = _panel()
    grid = coverage_floor_sensitivity(phys, comm, floors=(0.50, 0.60, 0.70))
    assert list(grid.columns) == [0.50, 0.60, 0.70]
