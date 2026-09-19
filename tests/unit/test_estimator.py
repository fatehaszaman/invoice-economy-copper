"""Estimator validation on synthetic data with a KNOWN answer.

Two directions matter equally:
  - recovery: planted beta = -1 is recovered
  - null:     planted beta =  0 does NOT produce significance

Most projects test only the first. The second is what stops a pipeline from
manufacturing a result.
"""
import numpy as np
import pytest

from research.bootstrap import block_bootstrap_beta, percentile_ci
from research.exposure import fit_by_tier, fit_exposure, load_exposure
from research.monotonicity import check_monotonicity
from research.permutation import permutation_test
from research.pretrends import check_pretrends
from tests.synthetic.make_panel import make_panel


def test_recovers_known_effect():
    panel = make_panel(beta=-1.0, seed=11)
    fit = fit_exposure(panel)
    assert fit.beta == pytest.approx(-1.0, abs=0.08)


def test_recovers_a_different_known_effect():
    panel = make_panel(beta=-0.4, seed=12)
    fit = fit_exposure(panel)
    assert fit.beta == pytest.approx(-0.4, abs=0.08)


def test_null_case_does_not_manufacture_significance():
    """THE IMPORTANT ONE. Zero planted effect must not become a finding."""
    panel = make_panel(beta=0.0, seed=13)
    fit = fit_exposure(panel)
    assert abs(fit.beta) < 0.15, f"invented an effect of {fit.beta:.3f} from noise"

    perm = permutation_test(panel, n_perm=300, seed=13)
    assert perm["p_value"] > 0.10, (
        f"permutation p={perm['p_value']:.3f} on pure noise; the inference "
        "machinery is producing false positives"
    )


def test_bootstrap_interval_covers_the_truth():
    panel = make_panel(beta=-1.0, seed=14)
    betas = block_bootstrap_beta(panel, n_boot=120, seed=14)
    lo, hi = percentile_ci(betas, level=0.90)
    assert lo < -1.0 < hi, f"90% interval [{lo:.3f}, {hi:.3f}] excludes the truth"


def test_bootstrap_interval_on_noise_contains_zero():
    panel = make_panel(beta=0.0, seed=15)
    betas = block_bootstrap_beta(panel, n_boot=120, seed=15)
    lo, hi = percentile_ci(betas, level=0.90)
    assert lo < 0.0 < hi


def test_permutation_detects_a_real_effect():
    panel = make_panel(beta=-1.0, seed=16)
    perm = permutation_test(panel, n_perm=300, seed=16)
    assert perm["p_value"] < 0.10


def test_monotonicity_detects_planted_ordering():
    panel = make_panel(beta=-1.0, seed=17)
    effects = fit_by_tier(panel)
    res = check_monotonicity(effects)
    assert res.ordered_as_predicted, f"ordering not detected: {res.effects.to_dict()}"
    assert res.spearman_rho < 0


def test_monotonicity_rejects_a_flat_case():
    panel = make_panel(beta=0.0, seed=18)
    effects = fit_by_tier(panel)
    res = check_monotonicity(effects)
    assert not res.ordered_as_predicted or res.spearman_p > 0.10


def test_monotonicity_refuses_two_tiers():
    """An ordering claim across two points is not evidence of an ordering."""
    import pandas as pd

    with pytest.raises(ValueError, match="all three tiers"):
        check_monotonicity(pd.Series({"high": -1.0, "low": 0.0}))


def test_pretrend_passes_when_there_is_none():
    panel = make_panel(beta=-1.0, pretrend=0.0, seed=19)
    assert check_pretrends(panel).passes


def test_pretrend_fails_when_channels_were_already_diverging():
    """KILL CONDITION: a planted pre-trend must be caught."""
    panel = make_panel(beta=-1.0, pretrend=6.0, noise=0.05, seed=20)
    res = check_pretrends(panel)
    assert not res.passes, (
        "a strong pre-existing divergence was not detected; the design would "
        "have attributed it to enforcement"
    )


def test_exposure_config_is_loaded_not_hardcoded():
    df = load_exposure()
    assert df["exposure"].between(0, 1).all()
    assert set(df["tier"]) <= {"high", "moderate", "low"}
    assert df["basis"].str.len().gt(10).all(), "every tier needs a documented basis"
    assert set(df["confidence"]) <= {"high", "moderate", "low"}


def test_cluster_se_reported_but_secondary():
    panel = make_panel(beta=-1.0, seed=21)
    fit = fit_exposure(panel, cluster=True)
    assert fit.se_cluster is not None and fit.se_cluster > 0
    assert fit.n_channels == 6
