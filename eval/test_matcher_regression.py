"""Regression: the frozen matcher's best candidate must equal the committed frozen tune results.

Reruns three tune frames (two fixes, one rejection) through the current code and compares with
eval/results/week4/tune/frames_ncc.csv (frozen run of 2026-11-19, system Python 3.12 with OpenCV
4.6.0, numpy 1.26.4, scipy 1.11.4). In that environment the match must be exact. With other
library versions (e.g. the venv's OpenCV 5.0 / numpy 2.x) interpolation differs slightly, so the
test allows small tolerances there and says so. Skipped without the data.
"""
import csv
import json
from pathlib import Path

import cv2
import pytest

import eval_matcher
from trn_matcher.frames import footprints, prepare_frame
from trn_matcher.interface import DEFAULT_SEARCH
from trn_matcher.loader import LoaderConfig, VisLocDataset
from trn_matcher.matcher import FeatureMatcher

ROOT = Path.home() / "data/visloc/flights"
FROZEN = Path(__file__).parent / "results/week4/tune/frames_ncc.csv"
FROZEN_SETTINGS = Path(__file__).resolve().parents[1] / "src/trn_matcher/trn_matcher/matcher_frozen.json"
FRAMES = ["10_0001.JPG", "10_0007.JPG", "10_0013.JPG"]
REFERENCE_ENV = cv2.__version__ == "4.6.0"


@pytest.mark.skipif(not (ROOT / "10/UAV-image").is_dir() or not FROZEN.exists(),
                    reason="flight 10 or the frozen per-frame results (not distributed publicly) missing")
def test_frozen_best_candidate_unchanged():
    ref = {r["image"]: r for r in csv.DictReader(FROZEN.open())}
    splits = json.loads((Path(__file__).parent / "splits.json").read_text())
    ds = VisLocDataset(ROOT, splits, "tune", LoaderConfig(prior_sigma_m=50.0, image_px=1024, seed=0))
    foot = footprints(ds)
    idx = {r.filename: k for k, (_, r) in enumerate(ds.records)}
    m = FeatureMatcher()
    for name in FRAMES:
        fr = prepare_frame(ds, idx[name], DEFAULT_SEARCH, 50.0, 0.5, foot)
        row = eval_matcher.evaluate_frame(m, fr.image, fr.patch, fr.prior, fr.true_en, DEFAULT_SEARCH)
        r = ref[name]
        assert row["status"] == r["status"], name
        new, old = json.loads(row["diag"]), json.loads(r["diag"])
        if REFERENCE_ENV:   # exact
            for k in ("est_e", "est_n", "scale", "rot_deg", "err_m"):
                assert str(row[k]) == r[k], (name, k, row[k], r[k])
            for k in old:
                assert new[k] == old[k], (name, k)
        else:               # other library versions: small interpolation differences allowed
            if r["status"] == "fix":
                assert abs(float(row["est_e"]) - float(r["est_e"])) < 0.5, name
                assert abs(float(row["est_n"]) - float(r["est_n"])) < 0.5, name
            for k, tol in (("peak", 2e-3), ("ratio", 1e-2), ("scale", 1e-6), ("rot_deg", 1e-6)):
                assert abs(new[k] - old[k]) <= tol, (name, k, new[k], old[k])
        assert len(new["topk"]) >= 1 and new["topk"][0]["z"] == new["peak_z"]


@pytest.mark.skipif(not (ROOT / "10/UAV-image").is_dir() or not FROZEN.exists(),
                    reason="flight 10 or the frozen per-frame results (not distributed publicly) missing")
def test_accept_all_returns_frozen_best_candidates():
    """accept_all: same settings, and every frame's answer equals the frozen fix or rejected candidate."""
    ref = {r["image"]: r for r in csv.DictReader(FROZEN.open())}
    splits = json.loads((Path(__file__).parent / "splits.json").read_text())
    ds = VisLocDataset(ROOT, splits, "tune", LoaderConfig(prior_sigma_m=50.0, image_px=1024, seed=0))
    foot = footprints(ds)
    idx = {r.filename: k for k, (_, r) in enumerate(ds.records)}
    m = FeatureMatcher(accept_all=True)
    assert m.settings == FeatureMatcher().settings
    assert m.settings_dict() == json.loads(FROZEN_SETTINGS.read_text())["settings"]
    for name in FRAMES:
        fr = prepare_frame(ds, idx[name], DEFAULT_SEARCH, 50.0, 0.5, foot)
        res = m.match(fr.image, fr.patch, fr.prior, DEFAULT_SEARCH)
        r = ref[name]
        old = json.loads(r["diag"])
        assert res is not None, name
        assert res.diag["gate_pass"] == (r["status"] == "fix"), name
        want = ((float(r["est_e"]), float(r["est_n"])) if r["status"] == "fix"
                else (old["cand_east"], old["cand_north"]))
        tol = 1e-3 if REFERENCE_ENV else 0.5
        assert abs(res.x - want[0]) <= tol and abs(res.y - want[1]) <= tol, (name, res.x, res.y, want)
        for k, tol_other in (("peak", 2e-3), ("ratio", 1e-2), ("scale", 1e-6), ("rot_deg", 1e-6)):
            assert abs(res.diag[k] - old[k]) <= (1e-12 if REFERENCE_ENV else tol_other), (name, k)
