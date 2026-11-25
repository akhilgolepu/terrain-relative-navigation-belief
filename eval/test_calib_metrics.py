"""Tests for the week 5 calibration metrics."""
import numpy as np
import pytest

import calib_metrics as cm


def test_auc_and_ece_extremes():
    y = np.array([0, 0, 1, 1])
    assert cm.auc(np.array([0.1, 0.2, 0.8, 0.9]), y) == 1.0
    assert cm.auc(np.array([0.5, 0.5, 0.5, 0.5]), y) == 0.5
    p = np.array([0.0, 0.0, 1.0, 1.0])
    assert cm.ece(p, y, bins=2) == 0.0
    assert cm.ece(np.full(4, 0.5), y, bins=2) == pytest.approx(0.5)


def test_risk_coverage_orders_by_risk():
    risk = np.array([0.9, 0.1, 0.5, 0.2])
    wrong = np.array([1, 0, 1, 0])
    thr, frac, rate = cm.risk_coverage(risk, wrong)
    assert thr.tolist() == [0.1, 0.2, 0.5, 0.9]
    assert frac.tolist() == [0.25, 0.5, 0.75, 1.0]
    assert rate.tolist() == pytest.approx([0.0, 0.0, 1 / 3, 0.5])
    assert cm.aurc(risk, wrong) == pytest.approx((0 + 0 + 1 / 3 + 0.5) / 4)


def test_blocks_and_n_eff():
    assert [len(b) for b in cm.contiguous_blocks(10, 3)] == [4, 3, 3]
    rng = np.random.default_rng(0)
    white = rng.normal(size=2000)
    assert cm.n_eff(white) == pytest.approx(2000, rel=0.15)
    smooth = np.convolve(rng.normal(size=2100), np.ones(20) / 20, mode="valid")[:2000]
    assert cm.n_eff(smooth) < 300


def test_block_bootstrap_brackets_the_mean():
    x = np.random.default_rng(1).normal(5, 1, 500)
    lo, hi = cm.block_bootstrap(lambda i: x[i].mean(), len(x), 10, reps=300)
    assert lo < 5 < hi and hi - lo < 0.5
