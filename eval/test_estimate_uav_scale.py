"""Tests for the phase-correlation step of estimate_uav_scale.py on synthetic images."""
import numpy as np
import pytest

from estimate_uav_scale import phase_correlation


def texture(h=256, w=256, seed=0):
    rng = np.random.default_rng(seed)
    big = rng.normal(size=(h + 64, w + 64)).astype(np.float32)
    k = np.ones(5, np.float32) / 5  # smooth a little so it looks like imagery
    big = np.apply_along_axis(lambda r: np.convolve(r, k, "same"), 1, big)
    big = np.apply_along_axis(lambda c: np.convolve(c, k, "same"), 0, big)
    return big


@pytest.mark.parametrize("dx,dy", [(12, -7), (-20, 15), (0, 30)])
def test_shift_recovered(dx, dy):
    big = texture()
    a = big[32:288, 32:288]
    b = big[32 - dy:288 - dy, 32 - dx:288 - dx]  # content of a moved by (+dx, +dy) in b
    mx, my, peak = phase_correlation(a, b)
    assert (mx, my) == pytest.approx((dx, dy), abs=0.5)
    assert peak > 20


def test_unrelated_images_have_weak_peak():
    a = texture(seed=1)[:256, :256]
    b = texture(seed=2)[:256, :256]
    assert phase_correlation(a, b)[2] < 20
