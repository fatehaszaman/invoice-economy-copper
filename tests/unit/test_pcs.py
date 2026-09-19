"""PCS construction: sign convention, coverage, and the no-imputation rule."""
import numpy as np
import pandas as pd
import pytest

from pcs.blocks import block_mean
from pcs.coverage import label_confidence
from pcs.score import compute_pcs
from pcs.standardise import WindowOverlapError, assert_no_event_overlap, rolling_z

IDX = pd.date_range("2026-01-01", periods=12, freq="D")


def test_sign_convention_commercial_ahead_of_physical_is_negative():
    """Pre-registered: physical 0, commercial +2 MUST give negative PCS."""
    phys = pd.DataFrame({"a": np.zeros(12), "b": np.zeros(12)}, index=IDX)
    comm = pd.DataFrame({"x": np.full(12, 2.0), "y": np.full(12, 2.0)}, index=IDX)
    out = compute_pcs(phys, comm)
    assert (out["pcs"] < 0).all()
    assert out["pcs"].iloc[0] == pytest.approx(-2.0)


def test_sign_convention_reverse_case_is_positive():
    phys = pd.DataFrame({"a": np.full(12, 2.0)}, index=IDX)
    comm = pd.DataFrame({"x": np.zeros(12)}, index=IDX)
    out = compute_pcs(phys, comm)
    assert (out["pcs"] > 0).all()


def test_missing_series_is_dropped_not_imputed():
    """Coverage falls; the surviving mean is unaffected. No zero-filling."""
    z = pd.DataFrame({"a": np.full(4, 1.0), "b": [np.nan] * 4}, index=IDX[:4])
    mean, cov = block_mean(z)
    assert (mean == 1.0).all(), "a missing series must not drag the mean toward zero"
    assert (cov == 0.5).all()


def test_coverage_denominator_is_expected_not_available():
    """Coverage must be honest about thin periods."""
    z = pd.DataFrame(
        {"a": [1.0, 1.0], "b": [np.nan, 2.0], "c": [np.nan, np.nan]}, index=IDX[:2]
    )
    _, cov = block_mean(z)
    assert cov.iloc[0] == pytest.approx(1 / 3)
    assert cov.iloc[1] == pytest.approx(2 / 3)


def test_fully_missing_period_has_no_score_not_a_zero():
    z = pd.DataFrame({"a": [np.nan, 1.0]}, index=IDX[:2])
    mean, cov = block_mean(z)
    assert pd.isna(mean.iloc[0]), "an empty period must be NaN, never 0.0"
    assert cov.iloc[0] == 0.0


def test_coverage_floor_labels_confidence():
    assert label_confidence(1.0, 1.0) == "valid"
    assert label_confidence(0.5, 1.0) == "low_confidence"
    assert label_confidence(0.0, 1.0) == "unavailable"


def test_score_carries_coverage_metadata():
    """A PCS value without coverage metadata is incomplete."""
    phys = pd.DataFrame({"a": np.zeros(3)}, index=IDX[:3])
    comm = pd.DataFrame({"x": np.ones(3)}, index=IDX[:3])
    out = compute_pcs(phys, comm)
    for col in ("physical_coverage", "commercial_coverage", "confidence"):
        assert col in out.columns


def test_rolling_z_never_uses_the_current_observation():
    """A spike must not standardise itself into insignificance."""
    rng = np.random.default_rng(1)
    base = 1.0 + rng.normal(0, 0.05, 40)
    s = pd.Series(np.append(base, 50.0), index=pd.date_range("2026-01-01", periods=41))
    z = rolling_z(s, window=30, min_periods=20)
    assert z.iloc[-1] > 10, "the spike was absorbed into its own moments"


def test_zero_variance_window_yields_no_score_rather_than_infinity():
    """A constant history cannot standardise anything. NA is the honest answer."""
    s = pd.Series([1.0] * 41, index=pd.date_range("2026-01-01", periods=41))
    z = rolling_z(s, window=30, min_periods=20)
    assert pd.isna(z.iloc[-1]), "zero standard deviation must not produce inf or 0"


def test_normalisation_window_refuses_to_overlap_the_event():
    idx = pd.date_range("2026-04-01", periods=30, freq="D")
    with pytest.raises(WindowOverlapError):
        assert_no_event_overlap(idx, window=252, event_start=pd.Timestamp("2026-04-13").date())
