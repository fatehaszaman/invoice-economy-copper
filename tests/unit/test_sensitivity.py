"""PCS sensitivity variants: leave-one-out, residual construction, coverage
floor grid."""
from dataclasses import replace

import numpy as np
import pandas as pd

from pcs.sensitivity import (
    VARIANTS,
    SensitivityResult,
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


def test_common_subtraction_is_identical_to_baseline_not_robustness():
    """An adversarial demonstration of why the original residual was invalid."""
    shock = pd.Series(np.linspace(0, 5, 12), index=IDX)
    phys = pd.DataFrame({"a": shock, "b": shock}, index=IDX)
    comm = pd.DataFrame({"x": shock + 2.0, "y": shock + 2.0}, index=IDX)
    common = pd.concat([phys, comm], axis=1).mean(axis=1)
    old_residual = phys.sub(common, axis=0).mean(axis=1) - comm.sub(common, axis=0).mean(axis=1)
    baseline = phys.mean(axis=1) - comm.mean(axis=1)
    pd.testing.assert_series_equal(old_residual, baseline)
    result = compute_all_variants(phys, comm)["residual"]
    assert result.status == "not_specified"
    assert result.pcs.isna().all()


def test_missing_residual_cannot_pass_robustness():
    phys, comm = _panel()
    results = compute_all_variants(phys, comm)
    assert sign_agreement(results) is False


def test_sign_agreement_false_when_variants_disagree():
    results = _specified_results()
    results["inverse_variance"] = replace(
        results["inverse_variance"], pcs=pd.Series([-1.0, -2.0])
    )
    assert sign_agreement(results) is False


def test_coverage_floor_sensitivity_reports_three_floors():
    phys, comm = _panel()
    grid = coverage_floor_sensitivity(phys, comm, floors=(0.50, 0.60, 0.70))
    assert list(grid.columns) == [0.50, 0.60, 0.70]


def test_zero_variance_variant_is_explicitly_unavailable_not_omitted():
    phys = pd.DataFrame({"a": [0.0] * 12, "b": [0.0] * 12}, index=IDX)
    comm = pd.DataFrame({"x": [2.0] * 12, "y": [2.0] * 12}, index=IDX)
    result = compute_all_variants(phys, comm)["inverse_variance"]
    assert result.status == "unavailable"
    assert result.pcs.isna().all()


def test_leave_one_out_cannot_bypass_coverage_floor():
    phys, comm = _panel()
    for name in ("missing1", "missing2", "missing3"):
        phys[name] = float("nan")
    result = compute_all_variants(phys, comm)["leave_one_out"]
    assert result.pcs.isna().all()
    assert result.detail["per_dropout"].isna().all().all()
    assert result.detail["range_by_date"].isna().all()


def _specified_results():
    """Hypothetical future specified variants to test the diagnostic itself."""
    results = {
        name: SensitivityResult(name, pd.Series([1.0, 2.0]), {}) for name in VARIANTS
    }
    results["leave_one_out"].detail["per_dropout"] = pd.DataFrame({"drop_a": [1.0, 2.0]})
    return results


def test_specified_agreement_requires_common_valid_periods():
    results = _specified_results()
    assert sign_agreement(results) is True
    results["residual"] = replace(results["residual"], pcs=pd.Series([1.0, 2.0], index=[3, 4]))
    assert sign_agreement(results) is False


def test_leave_one_out_dissent_is_not_hidden_by_baseline_central_estimate():
    results = _specified_results()
    results["leave_one_out"].detail["per_dropout"]["drop_a"] = [-1.0, -2.0]
    assert sign_agreement(results) is False


def test_zero_is_not_classified_as_a_negative_sign():
    results = _specified_results()
    results = {name: replace(result, pcs=pd.Series([-1.0, -2.0]))
               for name, result in results.items()}
    results["leave_one_out"].detail["per_dropout"]["drop_a"] = [-1.0, -2.0]
    results["residual"] = replace(results["residual"], pcs=pd.Series([0.0, 0.0]))
    assert sign_agreement(results) is False
