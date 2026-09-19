"""Point-in-time guarantee. The most important test in the repository.

The adversarial case below is constructed so that a naive
"return the latest value" implementation passes every other test in this
suite and fails only here.
"""
from datetime import date

import pytest

from warehouse.pit import Observation, PITStore


def _obs(series, obs_ts, pub_ts, value, rev=0):
    return Observation(
        canonical_series_id=series,
        economic_object="production_event",
        observation_ts=obs_ts,
        publication_ts=pub_ts,
        retrieval_ts=date(2026, 9, 1),
        canonical_value=value,
        unit="tonnes",
        source="nbs",
        revision_number=rev,
        vintage_id=f"{pub_ts.isoformat()}#{rev}",
    )


@pytest.fixture
def store():
    s = PITStore()
    # April output, first published May 17
    s.append(_obs("refined_production", date(2026, 4, 30), date(2026, 5, 17), 1000.0))
    # ...then revised upward, published June 18
    s.append(_obs("refined_production", date(2026, 4, 30), date(2026, 6, 18), 1080.0, rev=1))
    # May output, published June 16
    s.append(_obs("refined_production", date(2026, 5, 31), date(2026, 6, 16), 1010.0))
    return s


def test_unpublished_value_is_invisible(store):
    """A value published June 16 must not exist on June 15."""
    got = store.as_of("refined_production", date(2026, 6, 15))
    assert date(2026, 5, 31) not in set(got["observation_ts"].dt.date)


def test_boundary_is_inclusive(store):
    """Published ON the as-of date is visible; a strict inequality would be wrong."""
    got = store.as_of("refined_production", date(2026, 6, 16))
    assert date(2026, 5, 31) in set(got["observation_ts"].dt.date)


def test_returns_the_vintage_of_its_time_not_the_final_value(store):
    """THE ADVERSARIAL CASE.

    On June 1, April output was known to be 1000.0. The revision to 1080.0
    was not published until June 18. A latest-value implementation returns
    1080.0 here and silently contaminates the entire event window.
    """
    got = store.as_of("refined_production", date(2026, 6, 1))
    april = got[got["observation_ts"].dt.date == date(2026, 4, 30)]
    assert len(april) == 1
    assert april["canonical_value"].iloc[0] == 1000.0, (
        "as_of returned the revised value. This is look-ahead bias: the "
        "revision did not exist on the as-of date."
    )


def test_revision_is_visible_once_published(store):
    got = store.as_of("refined_production", date(2026, 6, 20))
    april = got[got["observation_ts"].dt.date == date(2026, 4, 30)]
    assert april["canonical_value"].iloc[0] == 1080.0


def test_revisions_coexist_never_overwritten(store):
    hist = store.revisions("refined_production")
    april = hist[hist["observation_ts"].dt.date == date(2026, 4, 30)]
    assert len(april) == 2, "a revision must append, not replace"
    assert set(april["canonical_value"]) == {1000.0, 1080.0}


def test_revision_magnitude_measured(store):
    hist = store.revisions("refined_production")
    april = hist[hist["observation_ts"].dt.date == date(2026, 4, 30)]
    assert april["revision_abs"].iloc[0] == pytest.approx(80.0)


def test_publication_lag_is_measured_not_assumed(store):
    lag = store.publication_lag("refined_production")
    assert lag["min"] >= 16


def test_every_row_declares_its_economic_object():
    with pytest.raises(ValueError, match="unknown economic_object"):
        _obs_bad = Observation(
            canonical_series_id="x",
            economic_object="demand",  # not a real object — this is the whole point
            observation_ts=date(2026, 1, 1),
            publication_ts=date(2026, 2, 1),
            retrieval_ts=date(2026, 2, 1),
            canonical_value=1.0,
            unit="tonnes",
            source="nbs",
        )


def test_publication_cannot_precede_observation():
    with pytest.raises(ValueError, match="precedes"):
        _obs("x", date(2026, 5, 1), date(2026, 4, 1), 1.0)


def test_asof_has_no_override_parameter():
    """Design guarantee: there is no escape hatch to the latest vintage."""
    import inspect

    params = set(inspect.signature(PITStore.as_of).parameters)
    assert params == {"self", "series_id", "asof", "channel_id"}
