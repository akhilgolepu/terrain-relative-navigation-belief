"""Tests for the mixture error model."""
import math

import numpy as np
import pytest

from trn_calibration.covariance import fit, MixtureModel, SIGMA_OUT_MIN


def _sample(n, seed=0):
    """Feature x in [-1, 1]: sigma = 10 exp(0.5 x) m, outlier weight logistic(-1.5 - 1.5 x)."""
    rng = np.random.default_rng(seed)
    x = rng.uniform(-1, 1, (n, 1))
    sigma = 10 * np.exp(0.5 * x[:, 0])
    w = 1 / (1 + np.exp(1.5 + 1.5 * x[:, 0]))
    out = rng.random(n) < w
    e = rng.normal(0, 1, (n, 2)) * np.where(out, 150.0, sigma)[:, None]
    return x, e


def test_fit_recovers_feature_dependence():
    x, e = _sample(4000)
    m = fit(x, e, ['f'], lam=0.0)
    sig, w, so = m.predict(np.array([[-1.0], [1.0]]))
    assert sig[0] == pytest.approx(10 * math.exp(-0.5), rel=0.15)
    assert sig[1] == pytest.approx(10 * math.exp(0.5), rel=0.15)
    assert w[0] > w[1] and so == pytest.approx(150.0, rel=0.15)


def test_feature_model_beats_constant_on_fit_data():
    x, e = _sample(2000, seed=1)
    m1 = fit(x, e, ['f'], lam=1.0)
    m0 = fit(np.zeros((len(e), 0)), e, [], lam=1.0)
    assert m1.nll(x, e).mean() < m0.nll(np.zeros((len(e), 0)), e).mean()


def test_radius_inverts_cdf_and_p_wrong_matches():
    m = MixtureModel([], [], [], a0=math.log(12.0), b0=-1.0, c=math.log(50.0))
    x = np.zeros((3, 0))
    r = m.radius(x, 0.9)
    assert np.allclose(m.cdf_radius(x, r), 0.9, atol=1e-6)
    w = 1 / (1 + math.exp(1.0))
    so = SIGMA_OUT_MIN + 50.0
    expected = ((1 - w) * math.exp(-50 ** 2 / (2 * 12.0 ** 2))
                + w * math.exp(-50 ** 2 / (2 * so ** 2)))
    assert m.p_wrong(x)[0] == pytest.approx(expected)


def test_nll_is_a_proper_density():
    m = MixtureModel([], [], [], a0=math.log(8.0), b0=-0.5, c=math.log(20.0))
    g = np.linspace(-400, 400, 801)
    ee, nn = np.meshgrid(g, g)
    e = np.c_[ee.ravel(), nn.ravel()]
    dens = np.exp(-m.nll(np.zeros((len(e), 0)), e))
    assert dens.sum() * 1.0 == pytest.approx(1.0, abs=2e-3)   # 1 m grid
