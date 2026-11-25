"""Tests for drift_data.py helpers (synthetic files, no dataset needed)."""
import csv
import json

import numpy as np
import pytest

from drift_data import distinct_runs, load_rpe_points, local_loglog_slopes, plot_rpe_vs_delta, scoring_settings


def write_csv(path, rows):
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def make_results(tmp_path):
    write_csv(tmp_path / "vio_run_identity.csv", [
        {"run": "a_run1", "outcome": "a_A"}, {"run": "a_run2", "outcome": "a_B"}, {"run": "a_run3", "outcome": "a_B"}])
    rows = [{"delta_m": d, "n_segments": n, "rpe_trans_rmse_m": 0.01 * float(d) ** 0.5, "rpe_trans_median_m": 0.005}
            for d, n in [("1", 100), ("20", 5), ("50", 2), ("200", 0)]]
    for run in ("a_run1", "a_run2", "a_run3"):
        write_csv(tmp_path / f"{run}_rpe_vs_delta.csv", rows)
    (tmp_path / "vio_scores_settings.json").write_text(json.dumps({
        "drift_curve_alignment": {"method": "4dof_yaw_translation", "skip_start_s": 2.0},
        "rpe_skip_start_s": 2.0, "rpe_segments": "x", "alignment_ate_rpe": "y", "max_time_diff_s": 0.01, "other": 1}))
    return tmp_path


def test_distinct_runs_keeps_first_of_each_outcome(tmp_path):
    assert distinct_runs(make_results(tmp_path)) == ["a_run1", "a_run2"]


def test_load_rpe_points_limits_length_and_drops_empty(tmp_path):
    results = make_results(tmp_path)
    p = load_rpe_points(results, "a_run1", max_delta_m=20.0)
    assert list(p.delta_m) == [1.0, 20.0] and list(p.n_segments) == [100, 5] and p.sequence == "a"
    assert list(load_rpe_points(results, "a_run1").delta_m) == [1.0, 20.0, 50.0]  # 200 m: no segments


def test_scoring_settings_copies_alignment_and_skip(tmp_path):
    s = scoring_settings(make_results(tmp_path))
    assert s["drift_curve_alignment"]["skip_start_s"] == 2.0 and s["rpe_skip_start_s"] == 2.0 and "other" not in s


def test_local_slopes_of_power_law_are_constant():
    d = np.array([1.0, 2.0, 5.0, 10.0])
    assert local_loglog_slopes(d, 0.03 * d ** 0.7) == pytest.approx([0.7, 0.7, 0.7])


def test_plot_writes_file(tmp_path):
    results = make_results(tmp_path)
    pts = [load_rpe_points(results, r) for r in distinct_runs(results)]
    plot_rpe_vs_delta(tmp_path / "p.png", pts, "t", fits={"f": lambda d: 0.01 * d ** 0.5})
    assert (tmp_path / "p.png").stat().st_size > 0
