"""Placebo machinery: must stay null on data with no effect planted there."""

from research.placebos import run_negative_control, run_placebo_dates
from tests.synthetic.make_panel import make_panel


def test_placebo_dates_are_null_when_no_effect_is_planted():
    """beta=0 planted; relabelling `post` at an arbitrary placebo date must
    not manufacture a large beta."""
    panel = make_panel(beta=0.0, seed=11)
    mid = panel["period"].sort_values().iloc[len(panel) // 2]
    results = run_placebo_dates(panel, placebo_dates=[mid])
    assert results, "expected at least one placebo result"
    assert all(r.passes for r in results)


def test_placebo_dates_can_fail_when_the_real_effect_is_planted_at_that_date():
    """Sanity check on the test itself: if the placebo date IS the real
    event date, of course it 'fails' (finds the real effect) — the module
    must not always report pass regardless of input."""
    panel = make_panel(beta=-2.0, seed=11)
    cut = panel[~panel["post"]]["period"].max()
    results = run_placebo_dates(panel, placebo_dates=[cut], beta_tolerance=0.15)
    assert not all(r.passes for r in results)


def test_negative_control_is_null_when_no_effect_is_planted():
    control_panel = make_panel(beta=0.0, seed=99)
    result = run_negative_control(control_panel, metal_label="aluminium")
    assert result.passes


def test_negative_control_flags_when_the_control_metal_also_shows_the_effect():
    """If a 'negative control' metal shows the same ordered effect, that is
    exactly the failure this test exists to catch."""
    control_panel = make_panel(beta=-2.0, seed=99)
    result = run_negative_control(control_panel, metal_label="aluminium", beta_tolerance=0.15)
    assert not result.passes
