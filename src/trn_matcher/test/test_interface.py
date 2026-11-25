"""Tests for the matcher interface helpers and the baseline matchers."""
import numpy as np
import pytest

from trn_matcher.baselines import PriorMatcher, RandomMatcher
from trn_matcher.interface import (as_result, DEFAULT_SEARCH, en_to_patch_px, MatchResult,
                                   patch_px_to_en, Prior, SearchSpace)
from trn_matcher.tile_store import MapPatch


def _patch(px=100, m_per_px=2.0, center=(1000.0, -500.0)):
    img = np.zeros((px, px, 3), np.uint8)
    return MapPatch(img, np.ones((px, px), bool), np.array(center), px * m_per_px, m_per_px, 't')


def test_patch_centre_and_corners():
    p = _patch()
    e, n = patch_px_to_en(p, 50.0, 50.0)
    assert (e, n) == pytest.approx((1000.0, -500.0))
    e, n = patch_px_to_en(p, 0.0, 0.0)          # north-west corner of the patch
    assert (e, n) == pytest.approx((900.0, -400.0))
    e, n = patch_px_to_en(p, 100.0, 100.0)      # south-east corner
    assert (e, n) == pytest.approx((1100.0, -600.0))


def test_px_en_round_trip():
    p = _patch()
    u = np.array([0.5, 12.25, 99.5])
    v = np.array([3.0, 50.0, 77.7])
    uu, vv = en_to_patch_px(p, *patch_px_to_en(p, u, v))
    np.testing.assert_allclose(uu, u)
    np.testing.assert_allclose(vv, v)


def test_search_space_contains():
    s = SearchSpace(window_m=100.0, scale_range=(0.8, 1.3), rot_range_deg=(-5.0, 5.0))
    pr = Prior(10.0, 20.0, 50.0, 120.0)
    assert s.contains(pr, 110.0, -80.0, 1.0, 0.0)
    assert not s.contains(pr, 110.1, 20.0, 1.0, 0.0)
    assert not s.contains(pr, 10.0, 20.0, 1.31, 0.0)
    assert not s.contains(pr, 10.0, 20.0, 1.0, -5.1)


def test_default_search_space_is_the_agreed_one():
    assert DEFAULT_SEARCH.scale_range == (0.8, 1.3)
    assert DEFAULT_SEARCH.rot_range_deg == (-20.0, 20.0)   # widened after the tune sweep


def test_patch_size_holds_the_largest_rotated_image():
    s = SearchSpace(window_m=150.0, scale_range=(0.8, 1.3), rot_range_deg=(-5.0, 5.0))
    a = np.radians(5.0)
    assert s.patch_size_m(100.0) == pytest.approx(300.0 + 130.0 * (np.cos(a) + np.sin(a)))


def test_as_result():
    assert as_result(None) is None
    r = as_result((1, 2, 1.1, -3, 0.5))
    assert r.astuple() == (1.0, 2.0, 1.1, -3.0, 0.5) and r.diag is None
    m = MatchResult(1.0, 2.0, 1.0, 0.0, 9.0, {'inliers': 12})
    assert as_result(m) is m


def test_prior_matcher_returns_prior():
    pr = Prior(5.0, -7.0, 50.0, 120.0)
    r = PriorMatcher().match(None, None, pr)
    assert r.astuple() == (5.0, -7.0, 1.0, 0.0, 0.0)


def test_random_matcher_inside_search_and_reproducible():
    s = DEFAULT_SEARCH
    rm = RandomMatcher(seed=3)
    priors = [Prior(float(e), float(n), 50.0, 120.0) for e, n in [(0, 0), (10, 5), (-300, 40)]]
    outs = [rm.match(None, None, p, s) for p in priors]
    for p, r in zip(priors, outs):
        assert s.contains(p, r.x, r.y, r.scale, r.rot_deg)
    again = [RandomMatcher(seed=3).match(None, None, p, s) for p in priors]
    assert [o.astuple() for o in outs] == [o.astuple() for o in again]
    assert outs[0].astuple() != RandomMatcher(seed=4).match(None, None, priors[0], s).astuple()
