"""Tests for the week 6 fusion core (needs gtsam: run with the venv interpreter)."""
import math

import numpy as np
import pytest

try:
    import gtsam
    from trn_fusion import validity
    from trn_fusion.core import FusionCore, load_config
    from trn_fusion.fix_factor import component_costs, mixture_factor
    from trn_fusion.odometry_sim import drift_b, simulate, step_sigma
    CFG = load_config()
except ImportError:   # gtsam is only in the venv; the ament lint tests still run without it
    gtsam = None

pytestmark = pytest.mark.skipif(gtsam is None, reason='gtsam not installed (use ~/venvs/trn)')


class FixedFixModel:
    """Stand-in for the calibrated model: fixed sigma_in, w, sigma_out, P(wrong)."""

    def __init__(self, sigma_in=20.0, w=0.1, sigma_out=100.0, p_wrong=0.1):
        self.p = (sigma_in, w, sigma_out, p_wrong)

    def params(self, log_ratio):
        return self.p


def straight(n, step=60.0):
    return np.c_[np.arange(n) * step, np.zeros(n)]


def test_drift_level_matches_definition():
    labels = straight(int(10000 / 50) + 1, 50.0)          # exactly 10 km
    b = drift_b(1.0, 10000.0)
    end = np.array([simulate(labels, b, 0.0, s)[-1] - labels[-1] for s in range(400)])
    rms = math.sqrt(np.mean(np.sum(end ** 2, axis=1)))
    assert rms == pytest.approx(100.0, rel=0.1)           # 1 % of 10 km


def test_step_sigma():
    assert step_sigma(np.array([30.0, 40.0]), 2.0, 0.0) == pytest.approx(math.sqrt(50.0))


def test_mixture_factor_picks_the_cheaper_component():
    (c_in, _), (c_out, _) = component_costs(0.0, 20.0, 0.1, 100.0)
    assert c_in < c_out
    (c_in, _), (c_out, _) = component_costs(300.0 ** 2, 20.0, 0.1, 100.0)
    assert c_out < c_in
    f = mixture_factor(gtsam.symbol('x', 0), np.array([0.0, 0.0]), 20.0, 0.1, 100.0)
    v = gtsam.Values()
    v.insert(gtsam.symbol('x', 0), np.array([10.0, 0.0]))
    r = f.unwhitenedError(v)
    assert r[0] == pytest.approx(0.5) and r[2] == pytest.approx(0.0)


def test_far_outlier_fix_barely_moves_the_estimate():
    # the factor itself: no gate, no inflation (the frozen gate would reject this fix)
    core = FusionCore({**CFG, 'gate_mode': 'off', 'fix_inflation': 1.0}, FixedFixModel(),
                      b=drift_b(1.0, 1e4))
    core.start(0.0, np.zeros(2), 50.0)
    core.fix(0.0, np.array([400.0, 0.0]), 0.0)
    # the outlier component (sigma_out 100 m) is chosen: 400 * 50^2 / (50^2 + 100^2) = 80 m;
    # a single inlier Gaussian (20 m) would pull 400 * 50^2 / (50^2 + 20^2) = 345 m
    assert core.belief().mean[0] == pytest.approx(80.0, abs=1.0)


def test_fixes_bound_the_error_and_outage_ages_then_stops_publishing():
    labels = straight(400)
    b = drift_b(2.0, 1e4)
    odo = simulate(labels, b, 0.0, 1)
    core = FusionCore(CFG, FixedFixModel(sigma_in=10.0, w=0.05, p_wrong=0.05), b=b)
    core.start(0.0, labels[0] + [30.0, -20.0], 50.0)
    rng = np.random.default_rng(0)
    states = []
    for k in range(1, 400):
        core.odometry(3.0 * k, odo[k] - odo[k - 1])
        if k < 100:
            core.fix(3.0 * k, labels[k] + rng.normal(0, 10.0, 2), 1.0)
        bel = core.belief()
        states.append(bel.validity)
        if k == 99:
            assert np.hypot(*(bel.mean - labels[k])) < 3 * validity.major_sigma(bel.cov)
            assert bel.validity == validity.STRONG
    assert validity.AGING in states[100:] and states[-1] == validity.DO_NOT_PUBLISH
    # predicted growth during the outage: variance adds b*d/2 per axis per step
    s_end = validity.major_sigma(core.belief().cov)
    s99 = 10.0
    assert s_end == pytest.approx(math.sqrt(s99 ** 2 + b * 60.0 * 300 / 2), rel=0.2)


def test_gate_rejects_and_thinning_skips():
    core = FusionCore(CFG, FixedFixModel(), b=drift_b(0.1, 1e4))
    core.start(0.0, np.zeros(2), 5.0)
    assert core.fix(0.0, np.array([500.0, 0.0]), 0.0) == 'gated'
    assert core.fix(0.0, np.array([1.0, 0.0]), 0.0) == 'fused'
    assert core.fix(CFG['thinning']['interval_s'] / 2, np.array([1.0, 0.0]), 0.0) == 'thinned'
    c = core.count
    assert (c.candidates, c.gated, c.fused, c.thinned) == (3, 1, 1, 1)


def test_validity_rules():
    v = CFG['validity']
    small, big = np.eye(2) * 10.0 ** 2, np.eye(2) * 50.0 ** 2
    assert validity.state(small, None, None, v)[0] == validity.DO_NOT_PUBLISH
    assert validity.state(small, 3.0, 0.05, v)[0] == validity.STRONG
    assert validity.state(small, 3.0, 0.30, v)[0] == validity.UNCERTAIN
    assert validity.state(big, 3.0, 0.05, v)[0] == validity.AGING
    assert validity.state(np.eye(2) * 200.0 ** 2, 3.0, 0.05, v)[0] == validity.DO_NOT_PUBLISH


def test_gate_modes_and_inflation():
    base = {**CFG, 'fix_inflation': 1.0}
    for mode, expect in (('off', 'fused'), ('chi2_inlier', 'gated'), ('mixture_pvalue', 'fused')):
        core = FusionCore({**base, 'gate_mode': mode}, FixedFixModel(sigma_in=10.0, w=0.3,
                                                                     sigma_out=200.0),
                          b=drift_b(0.1, 1e4))
        core.start(0.0, np.zeros(2), 5.0)
        # 60 m away: far for the 10 m inlier model, ordinary for a 200 m outlier with w = 0.3
        assert core.fix(0.0, np.array([60.0, 0.0]), 0.0) == expect, mode
    core = FusionCore({**base, 'gate_mode': 'mixture_pvalue'},
                      FixedFixModel(w=0.01, sigma_out=61.0), b=0.0)
    core.start(0.0, np.zeros(2), 5.0)
    assert core.fix(0.0, np.array([1000.0, 0.0]), 0.0) == 'gated'
    # inflation widens the inlier model: a 3x inflated 10 m fix no longer fails the chi-square gate
    core = FusionCore({**base, 'gate_mode': 'chi2_inlier', 'fix_inflation': 3.0},
                      FixedFixModel(sigma_in=10.0), b=0.0)
    core.start(0.0, np.zeros(2), 5.0)
    assert core.fix(0.0, np.array([60.0, 0.0]), 0.0) == 'fused'
