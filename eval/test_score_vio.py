"""Tests for score_vio.py on synthetic trajectories with known error (no dataset needed)."""
import csv
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from score_vio import align_yaw_translation, cumulative_distance, n_poses_until_distance

HERE = Path(__file__).parent


def test_cumulative_distance_straight_line():
    pos = np.array([[0, 0, 0], [3, 4, 0], [3, 4, 12]], dtype=float)
    assert cumulative_distance(pos) == pytest.approx([0, 5, 17])


def test_n_poses_until_distance():
    dist = np.arange(0, 20, 1.0)  # one pose per metre
    assert n_poses_until_distance(dist, 5.0) == 6  # 0..5 m
    assert n_poses_until_distance(dist, 0.0) == 3  # never fewer than 3


def write_tum(path: Path, t: np.ndarray, pos: np.ndarray) -> None:
    with path.open("w") as fh:
        for ti, p in zip(t, pos):
            fh.write(f"{ti:.6f} {p[0]:.6f} {p[1]:.6f} {p[2]:.6f} 0 0 0 1\n")


def test_end_to_end_offset_plus_linear_drift(tmp_path):
    # Helix (non-degenerate for SE(3) alignment): radius 10 m, ~1 m/s, 100 s at 10 Hz.
    t = 1000.0 + np.arange(0, 100, 0.1)
    s = t - t[0]
    gt = np.stack([10 * np.cos(0.1 * s), 10 * np.sin(0.1 * s), 0.1 * s], axis=1)
    dist = cumulative_distance(gt)
    drift = np.outer(dist, [0.02, 0.0, 0.01])  # per metre travelled: 2 cm horizontal, 1 cm vertical
    est = gt + drift + [5.0, -3.0, 1.0]            # plus a constant offset the alignment must remove
    write_tum(tmp_path / "gt.tum", t, gt)
    write_tum(tmp_path / "est.tum", t, est)
    out = tmp_path / "out"
    subprocess.run([sys.executable, str(HERE / "score_vio.py"), "--out", str(out),
                    "--seq", "SYN", str(tmp_path / "est.tum"), str(tmp_path / "gt.tum")],
                   check=True, capture_output=True, text=True)

    row = next(csv.DictReader((out / "vio_scores.csv").open()))
    assert int(row["matched_poses"]) == len(t)
    assert float(row["gt_length_m"]) == pytest.approx(dist[-1], abs=0.01)  # CSV keeps 2 decimals
    assert float(row["ate_rmse_m"]) < 0.0224 * dist[-1]  # full alignment absorbs part of the drift
    header = (out / "SYN_error_vs_distance.csv").read_text().splitlines()[0].split(",")
    assert header == ["t_rel_s", "distance_m", "horiz_err_start_aligned_m", "vert_err_start_aligned_m",
                      "horiz_err_whole_se3_aligned_m", "horiz_err_whole_yaw_aligned_m"]
    errs = np.loadtxt(out / "SYN_error_vs_distance.csv", delimiter=",", skiprows=1)
    # start-aligned curves show the drift rates, split by direction
    assert np.polyfit(errs[:, 1], errs[:, 2], 1)[0] == pytest.approx(0.02, abs=0.005)  # horizontal
    assert np.polyfit(errs[:, 1], errs[:, 3], 1)[0] == pytest.approx(0.01, abs=0.001)  # vertical, signed
    # whole-trajectory alignment spreads the drift over the path: lower final error, and the summary
    # reports how far the two horizontal curves are apart
    assert errs[-1, 4] < errs[-1, 2]
    diff = np.abs(errs[:, 2] - errs[:, 4])
    assert float(row["horiz_mean_abs_diff_m"]) == pytest.approx(diff.mean(), abs=1e-3)
    assert float(row["horiz_max_abs_diff_m"]) == pytest.approx(diff.max(), abs=1e-3)
    assert float(row["final_horiz_err_start_aligned_m"]) == pytest.approx(errs[-1, 2], abs=1e-3)
    assert float(row["final_vert_err_start_aligned_m"]) == pytest.approx(errs[-1, 3], abs=1e-3)
    assert float(row["horiz_rmse_whole_se3_aligned_m"]) < float(row["horiz_rmse_start_aligned_m"])
    assert float(row["horiz_rmse_whole_yaw_aligned_m"]) < float(row["horiz_rmse_start_aligned_m"])
    for f in ["error_vs_distance.png", "SYN_trajectory.png"]:
        assert (out / f).exists()
    meta = json.loads((out / "vio_scores_settings.json").read_text())["drift_curve_alignment"]
    assert meta["method"] == "4dof_yaw_translation" and meta["window_m"] == 5.0


def test_align_yaw_translation_recovers_known_transform():
    rng = np.random.default_rng(0)
    ref = rng.normal(size=(50, 3)) * [5, 5, 1]
    yaw = 0.7
    c, s = np.cos(yaw), np.sin(yaw)
    rot = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    est = (ref - [1.0, 2.0, 3.0]) @ rot  # est = Rz(-yaw) applied to shifted ref
    got_yaw, aligned = align_yaw_translation(est, ref, n=50)
    assert got_yaw == pytest.approx(yaw)
    assert aligned == pytest.approx(ref, abs=1e-9)


def test_align_yaw_translation_does_not_remove_tilt():
    # A pitch error must stay visible: 4-DoF alignment may not rotate about x or y.
    ref = np.stack([np.linspace(0, 10, 50), np.zeros(50), np.zeros(50)], axis=1)
    est = ref.copy()
    est[:, 2] = 0.1 * ref[:, 0]  # trajectory tilted upward
    _, aligned = align_yaw_translation(est, ref, n=50)
    assert np.ptp(aligned[:, 2]) == pytest.approx(1.0)


def test_known_one_degree_tilt_is_reported(tmp_path):
    # Estimate = ground truth rotated by 1 degree about x (a roll tilt of the z axis), no other error.
    t = 1000.0 + np.arange(0, 100, 0.1)
    s = t - t[0]
    gt = np.stack([10 * np.cos(0.1 * s), 10 * np.sin(0.1 * s), 0.5 * np.sin(0.3 * s)], axis=1)
    a = np.radians(1.0)
    rot_x = np.array([[1, 0, 0], [0, np.cos(a), -np.sin(a)], [0, np.sin(a), np.cos(a)]])
    est = gt @ rot_x.T
    write_tum(tmp_path / "gt.tum", t, gt)
    write_tum(tmp_path / "est.tum", t, est)
    out = tmp_path / "out"
    run = subprocess.run([sys.executable, str(HERE / "score_vio.py"), "--out", str(out),
                          "--seq", "TILT", str(tmp_path / "est.tum"), str(tmp_path / "gt.tum")],
                         check=True, capture_output=True, text=True)
    row = next(csv.DictReader((out / "vio_scores.csv").open()))
    assert float(row["se3_align_tilt_deg"]) == pytest.approx(1.0, abs=0.01)
    assert float(row["se3_align_roll_deg"]) == pytest.approx(-1.0, abs=0.01)  # rotation that undoes the tilt
    assert float(row["se3_align_pitch_deg"]) == pytest.approx(0.0, abs=0.01)
    assert float(row["ate_rmse_m"]) < 1e-3          # SE(3) removes the tilt completely
    assert float(row["vert_rmse_start_aligned_m"]) > 0.05  # yaw+translation alignment cannot
    assert "SE(3) alignment rotation roll -1.000 deg" in run.stdout


def test_rpe_vs_delta_grows_with_segment_length(tmp_path):
    # Linear drift of [0.02, 0, 0.01] m per metre travelled, identity orientations: over a segment that is
    # L metres of ground-truth path the relative translation error is L * |drift| = 0.02236 L, whatever the
    # SE(3) alignment. evo picks segments along the estimate's path, which differs from the ground-truth
    # path by up to ~2 % here, and ends each at the first pose past d metres (poses ~0.1 m apart).
    t = 1000.0 + np.arange(0, 100, 0.1)
    s = t - t[0]
    gt = np.stack([10 * np.cos(0.1 * s), 10 * np.sin(0.1 * s), 0.1 * s], axis=1)
    est = gt + np.outer(cumulative_distance(gt), [0.02, 0.0, 0.01])
    write_tum(tmp_path / "gt.tum", t, gt)
    write_tum(tmp_path / "est.tum", t, est)
    out = tmp_path / "out"
    subprocess.run([sys.executable, str(HERE / "score_vio.py"), "--out", str(out),
                    "--rpe-curve-deltas", "1", "2", "5", "10", "20", "50", "200",
                    "--seq", "SYN", str(tmp_path / "est.tum"), str(tmp_path / "gt.tum")],
                   check=True, capture_output=True, text=True)
    rows = list(csv.DictReader((out / "SYN_rpe_vs_delta.csv").open()))
    assert [r["delta_m"] for r in rows] == ["1", "2", "5", "10", "20", "50", "200"]
    rate = np.hypot(0.02, 0.01)
    for r in rows[:-1]:
        d = float(r["delta_m"])
        assert 100.5 / (1.03 * d + 0.11) - 1 <= int(r["n_segments"]) <= 1.03 * 100.5 / d
        assert float(r["rpe_trans_rmse_m"]) / rate == pytest.approx(d, rel=0.03, abs=0.11)
    assert rows[-1]["n_segments"] == "0" and rows[-1]["rpe_trans_rmse_m"] == ""  # longer than the path
    score_row = next(csv.DictReader((out / "vio_scores.csv").open()))
    assert float(score_row["rpe_trans_rmse_50m"]) == pytest.approx(float(rows[5]["rpe_trans_rmse_m"]))
    assert int(score_row["rpe_pairs_50m"]) == int(rows[5]["n_segments"])


def test_max_rpe_segment_located_and_path_lengths_reported(tmp_path):
    # A single 0.5 m step in the estimate at t_rel = 50 s: the worst 1 m segment must contain it, and the
    # estimate path is longer by |normal step + jump| - |normal step|.
    t = 1000.0 + np.arange(0, 100, 0.1)
    s = t - t[0]
    gt = np.stack([10 * np.cos(0.1 * s), 10 * np.sin(0.1 * s), 0.1 * s], axis=1)
    est = gt.copy()
    est[s >= 50.0] += [0.0, 0.0, 0.5]
    write_tum(tmp_path / "gt.tum", t, gt)
    write_tum(tmp_path / "est.tum", t, est)
    out = tmp_path / "out"
    run = subprocess.run([sys.executable, str(HERE / "score_vio.py"), "--out", str(out),
                          "--seq", "JUMP", str(tmp_path / "est.tum"), str(tmp_path / "gt.tum")],
                         check=True, capture_output=True, text=True)
    seg = next(r for r in csv.DictReader((out / "JUMP_rpe_vs_delta.csv").open()) if r["delta_m"] == "1")
    assert float(seg["max_seg_start_t_rel_s"]) < 50.0 <= float(seg["max_seg_end_t_rel_s"])
    assert float(seg["max_seg_start_stamp"]) == pytest.approx(1000.0 + float(seg["max_seg_start_t_rel_s"]), abs=1e-3)
    assert float(seg["rpe_trans_max_m"]) > 0.3
    row = next(csv.DictReader((out / "vio_scores.csv").open()))
    assert float(row["rpe_trans_median_1m"]) < 0.05 < float(row["rpe_trans_rmse_1m"])  # one outlier segment
    k = int(np.argmax(s >= 50.0))  # the step from pose k-1 to k carries the jump
    step = gt[k] - gt[k - 1]
    extra = np.linalg.norm(step + [0.0, 0.0, 0.5]) - np.linalg.norm(step)
    assert float(row["est_length_m"]) - float(row["gt_length_m"]) == pytest.approx(extra, abs=0.011)  # 2-decimal CSV
    assert "path length estimate" in run.stdout


def test_first_kept_index():
    from score_vio import first_kept_index
    t = 1000.0 + np.arange(0, 10, 0.5)
    assert first_kept_index(t, est_first_t=1000.0, skip_s=0.0) == 0
    assert first_kept_index(t, est_first_t=1000.0, skip_s=2.0) == 4    # first pose at or after 1002.0
    assert first_kept_index(t, est_first_t=999.0, skip_s=2.0) == 2     # skip counts from the first ESTIMATED pose
    with pytest.raises(ValueError):
        first_kept_index(t, est_first_t=1000.0, skip_s=60.0)


def test_skip_start_removes_start_jump_from_rpe_and_alignment(tmp_path):
    # Estimate = ground truth, except a 0.3 m sideways offset on its first 0.5 s (a start-up jump).
    t = 1000.0 + np.arange(0, 100, 0.1)
    s = t - t[0]
    gt = np.stack([10 * np.cos(0.1 * s), 10 * np.sin(0.1 * s), 0.1 * s], axis=1)
    est = gt.copy()
    est[s < 0.5] += [0.0, 0.3, 0.0]
    write_tum(tmp_path / "gt.tum", t, gt)
    write_tum(tmp_path / "est.tum", t, est)
    rows = {}
    for skip in ("0", "2"):
        out = tmp_path / f"skip{skip}"
        subprocess.run([sys.executable, str(HERE / "score_vio.py"), "--out", str(out), "--skip-start-s", skip,
                        "--seq", "S", str(tmp_path / "est.tum"), str(tmp_path / "gt.tum")],
                       check=True, capture_output=True, text=True)
        rows[skip] = next(csv.DictReader((out / "vio_scores.csv").open()))
        rows[skip]["curve"] = list(csv.DictReader((out / "S_rpe_vs_delta.csv").open()))
    assert rows["0"]["skipped_poses"] == "0" and rows["2"]["skipped_poses"] == "20"
    assert float(rows["0"]["curve"][0]["rpe_trans_max_m"]) > 0.25        # jump inside the first 1 m segment
    assert float(rows["2"]["curve"][0]["rpe_trans_max_m"]) < 1e-4        # skipped
    assert float(rows["2"]["rpe_trans_rmse_1m"]) < 1e-4
    # with skip 0 the alignment window includes the offset poses and biases the whole start-aligned curve
    assert float(rows["0"]["final_horiz_err_start_aligned_m"]) > 0.01
    assert float(rows["2"]["final_horiz_err_start_aligned_m"]) < 1e-4
