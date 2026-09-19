"""Confounder ladder: partialling-out must actually move the estimate."""
import numpy as np
import pytest

from research.confounders import confounder_ladder, fit_with_confounders, survives_ladder
from research.exposure import fit_exposure
from tests.synthetic.make_panel import make_panel


def _add_controls(panel, rng_seed=0):
    rng = np.random.default_rng(rng_seed)
    d = panel.copy()
    d["copper_price"] = rng.normal(0, 1, len(d))
    d["tariff_dummy"] = rng.integers(0, 2, len(d)).astype(float)
    return d


def test_zero_controls_matches_plain_two_way_fe():
    panel = _add_controls(make_panel(beta=-1.0, seed=5))
    plain = fit_exposure(panel, cluster=False).beta
    beta, n = fit_with_confounders(panel, controls=[])
    assert beta == pytest.approx(plain)
    assert n == len(panel.dropna(subset=["y"]))


def test_confounder_uncorrelated_with_interaction_barely_moves_beta():
    panel = _add_controls(make_panel(beta=-1.0, seed=5))
    plain = fit_exposure(panel, cluster=False).beta
    beta, _ = fit_with_confounders(panel, controls=["copper_price"])
    assert abs(beta - plain) < 0.05


def test_confounder_collinear_with_interaction_absorbs_the_effect():
    """A control identical to the interaction splits the effect between the
    two collinear columns under minimum-norm least squares. It must shrink
    beta well below the plain estimate, proving the partialling actually
    works rather than merely running."""
    panel = _add_controls(make_panel(beta=-1.0, seed=5))
    plain = fit_exposure(panel, cluster=False).beta
    panel["shadow"] = panel["post"].astype(float) * panel["exposure"].astype(float)
    beta, _ = fit_with_confounders(panel, controls=["shadow"])
    assert abs(beta) < abs(plain) * 0.6


def test_ladder_runs_only_available_columns_and_is_ordered():
    panel = _add_controls(make_panel(beta=-1.0, seed=5))
    results = confounder_ladder(panel)
    # only copper_price, tariff_dummy exist on this panel
    assert [r.rung for r in results] == [0, 1, 2]
    assert results[1].controls == ("copper_price",)
    assert results[2].controls == ("copper_price", "tariff_dummy")


def test_survives_ladder_requires_the_sign_at_every_rung():
    panel = _add_controls(make_panel(beta=-1.0, seed=5))
    results = confounder_ladder(panel)
    assert survives_ladder(results, sign=-1.0)


def test_survives_ladder_false_on_empty_results():
    assert survives_ladder([]) is False
