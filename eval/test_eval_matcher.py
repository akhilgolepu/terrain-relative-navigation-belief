"""Tests for the week 4 evaluation harness, its reporting rules and the label-offset diagnostic."""
import csv
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

import eval_matcher
import label_offset
import matcher_report
from trn_matcher.interface import MatchResult, Prior, SearchSpace

SEARCH = SearchSpace(window_m=100.0)
PRIOR = Prior(0.0, 0.0, 50.0, 120.0)
TRUE = np.array([30.0, -40.0])


class Fixed:
    def __init__(self, out):
        self.out = out

    def match(self, image, patch, prior, search):
        return self.out


def test_frame_fix_error_is_estimate_minus_label():
    r = eval_matcher.evaluate_frame(Fixed((33.0, -44.0, 1.0, 0.0, 5.0)), None, None, PRIOR, TRUE, SEARCH)
    assert r["status"] == "fix"
    assert (r["err_e"], r["err_n"], r["err_m"]) == pytest.approx((3.0, -4.0, 5.0))


def test_frame_diag_is_written_as_json():
    r = eval_matcher.evaluate_frame(Fixed(MatchResult(30.0, -40.0, 1.0, 0.0, 1.0, {"inliers": 7})),
                                    None, None, PRIOR, TRUE, SEARCH)
    assert r["status"] == "fix" and r["err_m"] == 0 and r["diag"] == '{"inliers": 7}'


@pytest.mark.parametrize("out,status", [
    (None, "no_fix"),
    ((101.0, 0.0, 1.0, 0.0, 1.0), "outside_search"),     # outside the 100 m window
    ((0.0, 0.0, 1.4, 0.0, 1.0), "outside_search"),       # scale above 1.3
    ((0.0, 0.0, 1.0, 21.0, 1.0), "outside_search"),      # rotation above the default 20 deg
    ((math.nan, 0.0, 1.0, 0.0, 1.0), "invalid"),
])
def test_frame_non_fixes(out, status):
    r = eval_matcher.evaluate_frame(Fixed(out), None, None, PRIOR, TRUE, SEARCH)
    assert r["status"] == status and r["err_m"] == ""


def test_matcher_exception_propagates():
    class Broken:
        def match(self, *a):
            raise NotImplementedError

    with pytest.raises(NotImplementedError):
        eval_matcher.evaluate_frame(Broken(), None, None, PRIOR, TRUE, SEARCH)


def test_load_matcher_specs():
    assert eval_matcher.load_matcher("prior", 0).name == "prior"
    assert eval_matcher.load_matcher("random", 0).name == "random"
    m = eval_matcher.load_matcher("trn_matcher.baselines:PriorMatcher", 0)
    assert m.name == "prior"


def _rows(method, flight="10", split="tune", errs=(1.0, 2.0, 3.0, 4.0), status="fix"):
    return [{"split": split, "flight": flight, "image": f"{flight}_{k:04d}.JPG", "method": method,
             "status": status, "err_e": e, "err_n": 0.0, "err_m": e} for k, e in enumerate(errs)]


def test_table_refuses_missing_baseline():
    with pytest.raises(ValueError, match="random"):
        matcher_report.flight_tables(_rows("prior") + _rows("feature"))


def test_table_refuses_different_frames():
    rows = _rows("prior") + _rows("random") + _rows("feature", errs=(1.0, 2.0))
    with pytest.raises(ValueError, match="different frames"):
        matcher_report.flight_tables(rows)


def test_tables_are_per_flight_and_carry_the_floor():
    rows = (_rows("prior", errs=(60.0,) * 4) + _rows("random", errs=(100.0,) * 4) + _rows("feature")
            + _rows("prior", flight="05", split="calibrate") + _rows("random", flight="05", split="calibrate"))
    t = matcher_report.flight_tables(rows)
    assert set(t) == {("tune", "10", "all frames"), ("calibrate", "05", "all frames")}   # no pooled table
    feat = next(r for r in t[("tune", "10", "all frames")] if r["method"] == "feature")
    assert feat["role"] == "matcher" and feat["median_m"] == 2.5
    assert feat["floor_prior_median_m"] == 60.0 and feat["floor_random_median_m"] == 100.0
    assert [r["method"] for r in t[("tune", "10", "all frames")]] == ["prior", "random", "feature"]
    md = matcher_report.markdown(t, 50.0)
    assert md.count(matcher_report.LABEL_NOTE) == 2                 # the 15 m note under every table
    assert md.count("Floor: prior median") == 2


def test_no_fix_counts_in_rates_not_in_errors():
    rows = _rows("m", errs=(10.0, 70.0)) + _rows("m", errs=(0.0, 0.0), status="no_fix")
    for k, r in enumerate(rows):
        r["image"] = f"i{k}"
    s = matcher_report.stats(rows, 50.0)
    assert s["n_frames"] == 4 and s["n_fix"] == 2 and s["no_fix_rate"] == 0.5
    assert s["median_m"] == 40.0 and s["within_15m_rate"] == 0.25 and s["wrong_over_50m_rate"] == 0.25
    assert s["acceptance"] == 0.5 and s["within_15m_of_fixes"] == 0.5 and s["wrong_over_50m_of_fixes"] == 0.5


def test_label_offset_medians_and_filter():
    rows = [{"split": "tune", "flight": "10", "method": "m", "status": "fix", "err_e": e, "err_n": n,
             "err_m": math.hypot(e, n)} for e, n in [(10, -5), (12, -7), (8, -6), (300, 300)]]
    rows.append({"split": "tune", "flight": "10", "method": "m", "status": "no_fix", "err_e": "", "err_n": "",
                 "err_m": ""})
    r = label_offset.offsets(rows)[0]
    assert r["n_frames"] == 5 and r["n_used"] == 4 and r["note"] == label_offset.NOTE
    assert (r["median_e_m"], r["median_n_m"]) == (11.0, -5.5)
    r = label_offset.offsets(rows, max_err_m=100.0)[0]
    assert r["n_used"] == 3 and (r["median_e_m"], r["median_n_m"]) == (10.0, -6.0)


def test_test_split_refused_without_flag(tmp_path):
    p = subprocess.run([sys.executable, str(Path(eval_matcher.__file__)), "--split", "test", "--out", str(tmp_path)],
                       capture_output=True, text=True)
    assert p.returncode == 2 and "refusing the test split" in p.stdout
    assert not list(tmp_path.iterdir())


REF_PY = "/usr/bin/python3"   # the reference environment of the reported runs (eval/reference_env.json)


def test_env_mismatch_fails_loudly(tmp_path):
    import envcheck
    ref = tmp_path / "ref.json"
    ref.write_text('{"python": "0", "numpy": "0", "opencv": "0", "scipy": "0"}')
    assert len(envcheck.mismatches(ref)) == 4
    with pytest.raises(SystemExit) as e:
        envcheck.require_reference_env(ref)
    assert e.value.code == 3


@pytest.mark.skipif(not (Path.home() / "data/visloc/flights/10/UAV-image").is_dir(), reason="flight 10 not on disk")
@pytest.mark.skipif(not Path(REF_PY).exists(), reason="reference interpreter missing")
@pytest.mark.skipif(not all("enu_origin" in r for r in json.loads((Path(__file__).parent / "splits.json")
                                                                   .read_text())["regions"].values()),
                    reason="splits.json without coordinates (public copy): regenerate with make_splits.py")
def test_baselines_on_real_tune_frames(tmp_path):
    p = subprocess.run([REF_PY, str(Path(eval_matcher.__file__)), "--split", "tune", "--every", "48",
                        "--out", str(tmp_path)], capture_output=True, text=True, timeout=600)
    assert p.returncode == 0, p.stdout[-2000:] + p.stderr[-2000:]
    rows = list(csv.DictReader((tmp_path / "frames_prior.csv").open()))
    assert len(rows) == 3 and all(r["flight"] == "10" and r["status"] == "fix" for r in rows)
    for r in rows:   # the prior baseline's error is exactly the prior noise
        assert float(r["err_m"]) == pytest.approx(float(r["prior_err_m"]), abs=2e-3)
        assert float(r["map_valid_frac"]) > 0.5
    md = (tmp_path / "summary.md").read_text()
    assert "all frames" in md and md.count(matcher_report.LABEL_NOTE) == md.count("### Flight")
    assert (tmp_path / "cdf_10.png").is_file()


def test_coverage_subsets_have_their_own_floor():
    rows = []
    for m in ("prior", "random", "feature"):
        for k, (e, cov) in enumerate([(10.0, 0.5), (20.0, 0.95), (30.0, 1.0)]):
            rows.append({"split": "tune", "flight": "10", "image": f"i{k}", "method": m, "status": "fix",
                         "err_e": e, "err_n": 0.0, "err_m": e * (2 if m != "feature" else 1),
                         "map_valid_frac": cov})
    t = matcher_report.flight_tables(rows, coverage=0.9)
    low = t[("tune", "10", "map imagery < 90% of patch")]
    assert low[0]["n_frames"] == 1 and low[0]["floor_prior_median_m"] == 20.0
    high = t[("tune", "10", "map imagery >= 90% of patch")]
    assert high[0]["n_frames"] == 2 and high[0]["floor_prior_median_m"] == 50.0
    md = matcher_report.markdown(t, 50.0)
    assert md.count(matcher_report.LABEL_NOTE) == 3
