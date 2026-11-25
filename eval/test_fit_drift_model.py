"""Tests for fit_drift_model.py on synthetic RPE-vs-length data with a known model."""
from pathlib import Path

import numpy as np
import pytest

from drift_data import RpePoints
from fit_drift_model import (MODELS, aicc, choose, fit_model, floorwalk, leave_one_sequence_out, power,
                             power_sensitivity, threeterm)

DELTAS = np.array([1.0, 2.0, 5.0, 10.0, 20.0])


def runs_from(f, noise=0.02, seed=0):
    """Two sequences x two runs, multiplicative noise, segment counts like a 140 m path."""
    rng = np.random.default_rng(seed)
    pts = []
    for seq in ("s1", "s2"):
        for k in (1, 2):
            e = f(DELTAS) * (1 + noise * rng.standard_normal(DELTAS.size))
            pts.append(RpePoints(f"{seq}_run{k}", seq, DELTAS, e, e, (140 // DELTAS).astype(int), Path("x")))
    return pts


def test_power_law_recovered_and_kept():
    pts = runs_from(lambda d: power(d, 0.012, 0.5))
    fit = fit_model(MODELS["power"], pts)
    assert fit.values["c"] == pytest.approx(0.012, rel=0.05)
    assert fit.values["p"] == pytest.approx(0.5, abs=0.03)
    fits = {n: fit_model(s, pts) for n, s in MODELS.items()}
    loso = {n: leave_one_sequence_out(s, pts) for n, s in MODELS.items()}
    chosen, reason = choose(fits, loso)
    assert chosen == "power" and reason.startswith("The power law is kept")


def test_floor_plus_linear_growth_selects_threeterm():
    pts = runs_from(lambda d: threeterm(d, 0.02, 0.0, 0.01), noise=0.01)
    fits = {n: fit_model(s, pts) for n, s in MODELS.items()}
    loso = {n: leave_one_sequence_out(s, pts) for n, s in MODELS.items()}
    assert fits["threeterm"].values["a"] == pytest.approx(0.02, rel=0.1)
    assert fits["threeterm"].values["c"] == pytest.approx(0.01, rel=0.1)
    assert choose(fits, loso)[0] == "threeterm"


def test_parameters_respect_bounds():
    pts = runs_from(lambda d: power(d, 0.01, 0.4))
    fit = fit_model(MODELS["threeterm"], pts)
    assert min(fit.values.values()) >= 0.0
    assert fit_model(MODELS["power"], pts).at_bound == []


def test_leave_one_sequence_out_reports_each_and_pooled():
    out = leave_one_sequence_out(MODELS["power"], runs_from(lambda d: power(d, 0.01, 0.5)))
    assert set(out) == {"held_out_s1", "held_out_s2", "pooled"}
    assert out["pooled"] < 0.05


def test_aicc_penalises_parameters_and_tiny_samples():
    assert aicc(1.0, 20, 3) > aicc(1.0, 20, 2)
    assert aicc(1.0, 3, 2) == float("inf")


def test_floorwalk_recovered():
    pts = runs_from(lambda d: floorwalk(d, 0.01, 0.0002), noise=0.005)
    v = fit_model(MODELS["floorwalk"], pts).values
    assert v["a"] == pytest.approx(0.01, rel=0.1)
    assert v["b"] == pytest.approx(0.0002, rel=0.1)


def test_all_models_compared_on_same_points():
    pts = runs_from(lambda d: power(d, 0.012, 0.5))
    fits = {n: fit_model(s, pts) for n, s in MODELS.items()}
    assert len({f.n_points for f in fits.values()}) == 1
    loso = {n: leave_one_sequence_out(s, pts) for n, s in MODELS.items()}
    reason = choose(fits, loso)[1]
    assert "threeterm" in reason and "floorwalk" in reason


def test_power_sensitivity_variants():
    pts = runs_from(lambda d: power(d, 0.012, 0.5), noise=0.0)
    sens = power_sensitivity(pts)
    assert [v["variant"] for v in sens][:2] == ["baseline (segment weights, all runs)", "equal weights per point"]
    assert len(sens) == 2 + len(pts) and sens[2]["n_points"] == 15
    for v in sens:  # noise-free power law: every variant recovers it
        assert v["c"] == pytest.approx(0.012, rel=1e-3) and v["p"] == pytest.approx(0.5, abs=1e-3)


def test_unknown_weights_rejected():
    with pytest.raises(ValueError):
        fit_model(MODELS["power"], runs_from(lambda d: power(d, 0.01, 0.5)), weights="nope")
