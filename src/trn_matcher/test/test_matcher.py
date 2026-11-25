"""Synthetic tests: cut an aerial view with known shift/scale/rotation and recover it."""
import math

import cv2
import numpy as np
import pytest

from trn_matcher.features import feature_image
from trn_matcher.interface import en_to_patch_px, Prior, SearchSpace
from trn_matcher.masked_ncc import MaskedCorrelator
from trn_matcher.matcher import FeatureMatcher, MatcherSettings
from trn_matcher.tile_store import MapPatch

M_PER_PX = 0.5
PX = 600                  # patch 300 m
FOOT = 100.0              # nominal footprint [m]
SEARCH = SearchSpace(window_m=60.0)
ACCEPT_ALL = MatcherSettings(feature='gradient', coarse_px=64, peak_min=0.0, ratio_min=0.0)


def texture(seed, px=PX):
    """Return a non-repeating RGB map texture: smooth blobs plus roads and rectangles."""
    rng = np.random.default_rng(seed)
    base = cv2.GaussianBlur(rng.normal(0, 1, (px, px)).astype(np.float32), (0, 0), 6)
    base = (base - base.min()) / np.ptp(base)
    img = (base * 150 + 50).astype(np.float32)
    for _ in range(25):
        p1, p2 = rng.integers(0, px, 2), rng.integers(0, px, 2)
        cv2.line(img, tuple(int(v) for v in p1), tuple(int(v) for v in p2),
                 float(rng.uniform(0, 255)), int(rng.integers(2, 7)))
    for _ in range(40):
        x, y = rng.integers(0, px - 40, 2)
        w, h = rng.integers(8, 40, 2)
        cv2.rectangle(img, (int(x), int(y)), (int(x + w), int(y + h)),
                      float(rng.uniform(0, 255)), -1)
    rgb = np.stack([img, img * 0.9 + 10, img * 0.8 + 20], -1)
    return np.clip(rgb, 0, 255).astype(np.uint8)


def make_patch(rgb, valid=None, center=(500.0, -200.0)):
    valid = np.ones(rgb.shape[:2], bool) if valid is None else valid
    return MapPatch(rgb, valid, np.array(center), PX * M_PER_PX, M_PER_PX, 'synthetic')


def cut_image(patch, east, north, scale, rot_deg, n=400):
    """Render the aerial image: ground side FOOT*scale, up axis rot_deg clockwise from north."""
    u, v = en_to_patch_px(patch, east, north)
    f = FOOT * scale / n / M_PER_PX                      # map pixels per image pixel
    a = math.radians(rot_deg)
    lin = f * np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
    t = np.array([float(u), float(v)]) - lin @ np.array([n / 2, n / 2])
    m = np.hstack([lin, (lin @ [0.5, 0.5] + t - 0.5)[:, None]])
    return cv2.warpAffine(patch.image, m, (n, n), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                          borderMode=cv2.BORDER_REFLECT)


def prior_near(east, north, de=-25.0, dn=30.0):
    return Prior(east + de, north + dn, 50.0, FOOT)


@pytest.mark.parametrize('shift,scale,rot', [((30.0, -20.0), 1.0, 0.0),
                                             ((-15.0, 35.0), 1.15, 3.0),
                                             ((5.0, 5.0), 0.85, -4.0)])
def test_recovers_shift_scale_rotation(shift, scale, rot):
    patch = make_patch(texture(1))
    east, north = 500.0 + shift[0], -200.0 + shift[1]
    img = cut_image(patch, east, north, scale, rot)
    res = FeatureMatcher(ACCEPT_ALL).match(img, patch, prior_near(east, north), SEARCH)
    assert res is not None
    assert math.hypot(res.x - east, res.y - north) < 1.0
    assert res.scale == pytest.approx(scale, abs=0.02)
    assert res.rot_deg == pytest.approx(rot, abs=0.5)
    assert res.diag['peak'] > 0.5 and res.diag['ratio'] > 1.5


def test_masked_map_area_is_ignored():
    """Blank out 40 % of the patch, including a third of the true footprint."""
    rgb = texture(2)
    patch = make_patch(rgb)
    east, north = 500.0 + 20.0, -200.0 - 10.0
    img = cut_image(patch, east, north, 1.05, 2.0)
    valid = np.ones((PX, PX), bool)
    u, _ = en_to_patch_px(patch, east, north)
    cut = int(float(u) - FOOT / M_PER_PX / 6)    # mask everything west of this column
    valid[:, :cut] = False
    blanked = rgb.copy()
    blanked[~valid] = 0
    res = FeatureMatcher(ACCEPT_ALL).match(img, make_patch(blanked, valid),
                                           prior_near(east, north), SEARCH)
    assert res is not None
    assert math.hypot(res.x - east, res.y - north) < 1.5
    assert res.diag['overlap_valid_frac'] < 0.9


def test_robust_to_haze_and_contrast_inversion():
    patch = make_patch(texture(3))
    east, north = 500.0 - 30.0, -200.0 + 15.0
    img = cut_image(patch, east, north, 1.0, 1.0).astype(np.float32)
    img = (255 - img) * 0.4 + 120                      # inverted, washed-out
    res = FeatureMatcher(ACCEPT_ALL).match(img.astype(np.uint8), patch, prior_near(east, north),
                                           SEARCH)
    assert res is not None and math.hypot(res.x - east, res.y - north) < 1.5


def test_unrelated_image_has_low_ratio_and_is_rejected():
    patch = make_patch(texture(4))
    other = make_patch(texture(99))
    img = cut_image(other, 500.0, -200.0, 1.0, 0.0)
    m = FeatureMatcher(ACCEPT_ALL)
    m.match(img, patch, prior_near(500.0, -200.0), SEARCH)
    good = FeatureMatcher(ACCEPT_ALL).match(cut_image(patch, 500.0, -200.0, 1.0, 0.0), patch,
                                            prior_near(500.0, -200.0), SEARCH)
    assert m.last_diag['ratio'] < good.diag['ratio']
    assert m.last_diag['peak'] < good.diag['peak']
    strict = FeatureMatcher(MatcherSettings('gradient', 64, good.diag['peak'] * 0.8, 0.0))
    assert strict.match(img, patch, prior_near(500.0, -200.0), SEARCH) is None
    assert strict.last_diag['accepted'] is False and strict.last_diag['reason']


def test_answer_stays_in_search_space():
    patch = make_patch(texture(5))
    img = cut_image(patch, 500.0, -200.0, 1.0, 0.0)
    pr = Prior(500.0 + 200.0, -200.0, 50.0, FOOT)     # truth 200 m away, outside a 60 m window
    res = FeatureMatcher(ACCEPT_ALL).match(img, patch, pr, SEARCH)
    if res is not None:
        assert SEARCH.contains(pr, res.x, res.y, res.scale, res.rot_deg)


def test_masked_ncc_matches_direct_computation():
    rng = np.random.default_rng(0)
    image = rng.normal(size=(40, 50))
    mask = rng.random((40, 50)) > 0.2
    tpl = rng.normal(size=(9, 9))
    tmask = rng.random((9, 9)) > 0.3
    ncc, _ = MaskedCorrelator(image, mask, (9, 9)).ncc(tpl, tmask, 0.1)
    y, x = 7, 11
    both = mask[y:y + 9, x:x + 9] & tmask
    a, b = image[y:y + 9, x:x + 9][both], tpl[both]
    direct = np.corrcoef(a, b)[0, 1]
    assert ncc[y, x] == pytest.approx(direct, abs=1e-9)


def test_feature_mask_drops_pixels_next_to_no_imagery():
    rgb = texture(6, 100)
    valid = np.ones((100, 100), bool)
    valid[:, 60:] = False
    _, v = feature_image(rgb, valid, 'gradient', 6.0)
    assert not v[:, 56:].any() and v[:, :50].all()


def test_frozen_settings_file_holds_exactly_the_four_settings():
    import dataclasses
    import json
    from trn_matcher.interface import DEFAULT_SEARCH
    from trn_matcher.matcher import FROZEN_FILE
    frozen = json.loads(FROZEN_FILE.read_text())
    assert set(frozen['settings']) == {f.name for f in dataclasses.fields(MatcherSettings)}
    assert len(frozen['settings']) <= 4
    assert FeatureMatcher().settings == MatcherSettings(**frozen['settings'])
    s = frozen['search_space']
    assert tuple(s['rot_range_deg']) == DEFAULT_SEARCH.rot_range_deg
    assert tuple(s['scale_range']) == DEFAULT_SEARCH.scale_range
    assert s['window_m'] == DEFAULT_SEARCH.window_m


def test_topk_candidates_are_distinct_and_best_first():
    from trn_matcher.matcher import TOPK_SEPARATION_M
    patch = make_patch(texture(8))
    east, north = 500.0 + 10.0, -200.0 + 20.0
    img = cut_image(patch, east, north, 1.0, 1.0)
    res = FeatureMatcher(ACCEPT_ALL).match(img, patch, prior_near(east, north), SEARCH)
    top = res.diag['topk']
    assert 1 < len(top) <= 3
    assert top[0]['z'] == pytest.approx(res.diag['peak_z'], abs=1e-3)
    assert top[0]['ncc'] == pytest.approx(res.diag['peak'], abs=1e-4)
    assert math.hypot(top[0]['east'] - res.x, top[0]['north'] - res.y) < 5.0   # coarse vs fine
    assert all(a['z'] >= b['z'] for a, b in zip(top, top[1:]))
    for i, a in enumerate(top):
        for b in top[i + 1:]:
            assert math.hypot(a['east'] - b['east'], a['north'] - b['north']) > TOPK_SEPARATION_M


def test_rotation_prior_narrows_the_search_and_still_recovers():
    from dataclasses import replace
    patch = make_patch(texture(9))
    east, north = 500.0 - 20.0, -200.0 + 5.0
    img = cut_image(patch, east, north, 1.05, 12.0)
    pr = replace(prior_near(east, north), rot_deg=10.0, rot_sigma_deg=3.0)
    res = FeatureMatcher(ACCEPT_ALL).match(img, patch, pr, SEARCH)
    assert res.diag['rot_search_deg'] == [1.0, 19.0]
    assert res is not None and math.hypot(res.x - east, res.y - north) < 1.0
    assert res.rot_deg == pytest.approx(12.0, abs=0.5)


def test_rotation_prior_off_by_default_and_clipped_to_search_range():
    from dataclasses import replace
    from trn_matcher.matcher import _rot_range
    pr = prior_near(0.0, 0.0)
    assert pr.rot_deg is None and _rot_range(pr, SEARCH) == SEARCH.rot_range_deg
    assert _rot_range(replace(pr, rot_deg=18.0, rot_sigma_deg=3.0), SEARCH) == (9.0, 20.0)
    assert _rot_range(replace(pr, rot_deg=40.0, rot_sigma_deg=3.0), SEARCH) == (20.0, 20.0)
