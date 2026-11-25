#!/usr/bin/env python3
"""Score VIO trajectories against ground truth with evo: ATE, RPE, and error vs distance travelled.

For each sequence: read the estimate (TUM: t x y z qx qy qz qw) and ground truth (EuRoC CSV or TUM),
match timestamps, then
  - ATE: translation RMSE after SE(3) alignment over the whole trajectory (no scale: VIO is metric),
  - RPE: translation error over fixed travelled distances (--rpe-deltas, metres, columns of vio_scores.csv),
    using consecutive non-overlapping segments after the SE(3) alignment above, each segment ending at the
    first pose at least that far along the ESTIMATE's path (evo's default, pairs_from_reference=False);
    the same for every length in --rpe-curve-deltas goes to <name>_rpe_vs_delta.csv (rmse/mean/median/max
    and number of segments, plus the start/end time of the segment with the largest error; a length longer
    than the path gives 0 segments and empty values),
  - error vs distance: per-pose position error against distance travelled along the ground truth,
    with the estimate aligned on its first --start-align-m metres of travel only, so error growth (drift)
    shows. That alignment is 4-DoF (yaw about z + translation): VIO observes gravity, so roll and pitch
    are not free; both frames are assumed to have z along gravity. The error is split into horizontal
    (x,y) and vertical (z, signed est - gt). As a cross-check the horizontal curve is also computed with
    SE(3) alignment over the whole trajectory (and with 4-DoF over the whole trajectory); the difference
    to the SE(3) curve and the roll/pitch of the SE(3) alignment rotation (tilt between the estimate's
    and the ground truth's z axes, which 4-DoF alignment cannot remove) are reported per sequence.
Start-up skip (--skip-start-s, default 2.0 s): poses earlier than the estimate's first pose (first line of its TUM file,
before timestamp matching) plus this time are left out of RPE (vio_scores.csv RPE columns and <name>_rpe_vs_delta.csv)
and of the start-aligned 4-DoF alignment window, which then covers the first --start-align-m metres travelled after the
skip. OpenVINS's first poses after initialisation can jump (room2: 0.23-0.31 m in one 0.05 s step). ATE, the SE(3)
cross-check and the per-pose error-vs-distance rows still cover all matched poses (distance still counted from the
first matched pose). --skip-start-s 0 reproduces the earlier scoring exactly.
Writes one CSV row per sequence, one per-pose CSV per sequence (input for fit_drift_model.py) and plots.

Usage (in ~/venvs/trn):
    python eval/score_vio.py --out eval/results/vio \
        --seq MH_01_easy <est.tum> <gt.csv> --seq V1_01_easy <est.tum> <gt.csv>
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from evo.core import filters, metrics, sync  # noqa: E402
from evo.core.trajectory import PoseTrajectory3D  # noqa: E402
from evo.tools import file_interface  # noqa: E402


@dataclass
class SeqResult:
    name: str
    n_matched: int
    skip_start_s: float
    n_skipped: int                  # matched poses left out of RPE and of the start-alignment window
    duration_s: float
    gt_length_m: float              # path length of the matched ground-truth poses
    est_length_m: float             # path length of the matched estimate poses (RPE segments are measured on this)
    ate_rmse_m: float
    ate_max_m: float
    rpe_rmse_m: dict[float, float]  # NaN when the path is shorter than the segment length
    rpe_median_m: dict[float, float]
    rpe_pairs: dict[float, int]
    horiz_rmse_start_m: float       # horizontal error, 4-DoF aligned on the start window
    horiz_rmse_whole_se3_m: float   # horizontal error, SE(3) aligned on the whole trajectory (cross-check)
    horiz_rmse_whole_yaw_m: float   # horizontal error, 4-DoF aligned on the whole trajectory
    horiz_mean_abs_diff_m: float    # mean |start-aligned - whole SE(3)-aligned| over all poses
    horiz_max_abs_diff_m: float
    se3_roll_deg: float             # roll/pitch of the SE(3) rotation applied to the estimate (ZYX Euler)
    se3_pitch_deg: float
    se3_tilt_deg: float             # angle between the z axes before/after that rotation
    vert_rmse_start_m: float
    final_horiz_start_m: float      # start-aligned errors at the last matched pose
    final_vert_start_m: float       # signed, est - gt


def read_traj(path: Path) -> PoseTrajectory3D:
    """EuRoC ground-truth CSV (first line starts with '#timestamp') or TUM text."""
    with path.open() as fh:
        first = fh.readline()
    if first.startswith("#timestamp") or path.suffix == ".csv":
        return file_interface.read_euroc_csv_trajectory(str(path))
    return file_interface.read_tum_trajectory_file(str(path))


def cumulative_distance(positions: np.ndarray) -> np.ndarray:
    """Distance travelled up to each pose, starting at 0 (metres)."""
    steps = np.linalg.norm(np.diff(positions, axis=0), axis=1)
    return np.concatenate([[0.0], np.cumsum(steps)])


def n_poses_until_distance(dist: np.ndarray, metres: float) -> int:
    """Number of poses until `metres` have been travelled (at least 3, for an alignment)."""
    return max(3, int(np.searchsorted(dist, metres, side="right")))


def align_yaw_translation(est_xyz: np.ndarray, ref_xyz: np.ndarray, n: int, start: int = 0) -> tuple[float, np.ndarray]:
    """4-DoF least-squares alignment on points start .. start+n-1: yaw about z, then translation.

    Returns (yaw_rad, est_aligned_xyz) with est_aligned = Rz(yaw) @ est + t for all points.
    """
    q, p = est_xyz[start:start + n], ref_xyz[start:start + n]
    qc, pc = q - q.mean(axis=0), p - p.mean(axis=0)
    yaw = float(np.arctan2(np.sum(qc[:, 0] * pc[:, 1] - qc[:, 1] * pc[:, 0]),
                           np.sum(qc[:, 0] * pc[:, 0] + qc[:, 1] * pc[:, 1])))
    c, s = np.cos(yaw), np.sin(yaw)
    rot = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])
    t = p.mean(axis=0) - rot @ q.mean(axis=0)
    return yaw, est_xyz @ rot.T + t


def copy_traj(t: PoseTrajectory3D) -> PoseTrajectory3D:
    return PoseTrajectory3D(poses_se3=[p.copy() for p in t.poses_se3], timestamps=t.timestamps.copy())


def from_index(t: PoseTrajectory3D, k0: int) -> PoseTrajectory3D:
    """Copy of poses k0 .. end (the trajectory itself when k0 == 0)."""
    if k0 == 0:
        return t
    out = copy_traj(t)
    out.reduce_to_ids(np.arange(k0, out.num_poses))
    return out


def first_kept_index(matched_t: np.ndarray, est_first_t: float, skip_s: float) -> int:
    """Index of the first matched pose at or after est_first_t + skip_s (0 when skip_s is 0)."""
    if skip_s <= 0:
        return 0
    k0 = int(np.searchsorted(matched_t, est_first_t + skip_s, side="left"))
    if k0 >= len(matched_t) - 2:
        raise ValueError(f"--skip-start-s {skip_s} leaves fewer than 3 matched poses")
    return k0


def score(name: str, est_path: Path, gt_path: Path, args: argparse.Namespace, out: Path) -> SeqResult:
    gt, est = read_traj(gt_path), read_traj(est_path)
    est_first_t = float(est.timestamps[0])  # first estimated pose, before matching to ground truth
    gt, est = sync.associate_trajectories(gt, est, max_diff=args.max_time_diff)
    k0 = first_kept_index(gt.timestamps, est_first_t, args.skip_start_s)

    est_full = copy_traj(est)
    rot_se3, _, _ = est_full.align(gt, correct_scale=False)
    roll_deg, pitch_deg, tilt_deg = roll_pitch_tilt_deg(rot_se3)
    ape = metrics.APE(metrics.PoseRelation.translation_part)
    ape.process_data((gt, est_full))

    gt_kept, est_kept = from_index(gt, k0), from_index(est_full, k0)
    rpe_stats = {d: rpe_translation(gt_kept, est_kept, d, t_first=float(gt.timestamps[0]))
                 for d in sorted(set(args.rpe_deltas) | set(args.rpe_curve_deltas))}
    write_rpe_vs_delta(out / f"{name}_rpe_vs_delta.csv", {d: rpe_stats[d] for d in sorted(args.rpe_curve_deltas)})
    rpe_rmse = {d: rpe_stats[d]["rmse_m"] for d in args.rpe_deltas}
    rpe_median = {d: rpe_stats[d]["median_m"] for d in args.rpe_deltas}
    rpe_pairs = {d: int(rpe_stats[d]["n_segments"]) for d in args.rpe_deltas}

    dist = cumulative_distance(gt.positions_xyz)
    _, est_start_xyz = align_yaw_translation(est.positions_xyz, gt.positions_xyz,
                                             n_poses_until_distance(dist[k0:] - dist[k0], args.start_align_m), start=k0)
    _, est_whole_xyz = align_yaw_translation(est.positions_xyz, gt.positions_xyz, len(dist))
    d_start = est_start_xyz - gt.positions_xyz
    horiz_start, vert_start = np.linalg.norm(d_start[:, :2], axis=1), d_start[:, 2]
    horiz_whole_yaw = np.linalg.norm((est_whole_xyz - gt.positions_xyz)[:, :2], axis=1)
    horiz_whole_se3 = np.linalg.norm((est_full.positions_xyz - gt.positions_xyz)[:, :2], axis=1)
    write_error_vs_distance(out / f"{name}_error_vs_distance.csv", gt.timestamps - gt.timestamps[0], dist,
                            horiz_start, vert_start, horiz_whole_se3, horiz_whole_yaw)
    plot_trajectory(out / f"{name}_trajectory.png", name, gt, est_full)

    return SeqResult(name, len(gt.timestamps), args.skip_start_s, k0,
                     float(gt.timestamps[-1] - gt.timestamps[0]), float(dist[-1]),
                     float(cumulative_distance(est.positions_xyz)[-1]),
                     float(ape.get_statistic(metrics.StatisticsType.rmse)),
                     float(ape.get_statistic(metrics.StatisticsType.max)), rpe_rmse, rpe_median, rpe_pairs,
                     rmse(horiz_start), rmse(horiz_whole_se3), rmse(horiz_whole_yaw),
                     float(np.mean(np.abs(horiz_start - horiz_whole_se3))),
                     float(np.max(np.abs(horiz_start - horiz_whole_se3))), roll_deg, pitch_deg, tilt_deg,
                     rmse(vert_start), float(horiz_start[-1]), float(vert_start[-1]))


def rpe_translation(gt: PoseTrajectory3D, est: PoseTrajectory3D, delta_m: float, t_first: float) -> dict[str, float]:
    """Translation RPE [m] over consecutive, non-overlapping segments of >= delta_m metres of the estimate's path
    (evo default pairs_from_reference=False, kept so the 1 m / 10 m values match earlier scoring).
    Also returns the start/end timestamps of the segment with the largest error (absolute, and relative to t_first)."""
    rpe = metrics.RPE(metrics.PoseRelation.translation_part, delta=delta_m, delta_unit=metrics.Unit.meters,
                      all_pairs=False)
    try:
        rpe.process_data((gt, est))
    except (filters.FilterException, metrics.MetricsException):  # path shorter than one segment
        return {"n_segments": 0, **{k: float("nan") for k in RPE_STAT_KEYS}}
    st = metrics.StatisticsType
    # consecutive pairs: segment k runs from the end of segment k-1 (or pose 0) to delta_ids[k]
    k = int(np.argmax(rpe.error))
    i, j = (rpe.delta_ids[k - 1] if k > 0 else 0), rpe.delta_ids[k]
    t0, t1 = float(est.timestamps[i]), float(est.timestamps[j])
    return {"n_segments": len(rpe.error), "rmse_m": float(rpe.get_statistic(st.rmse)),
            "mean_m": float(rpe.get_statistic(st.mean)), "median_m": float(rpe.get_statistic(st.median)),
            "max_m": float(rpe.get_statistic(st.max)), "max_seg_start_t_rel_s": t0 - t_first,
            "max_seg_end_t_rel_s": t1 - t_first, "max_seg_start_stamp": t0, "max_seg_end_stamp": t1}


RPE_STAT_KEYS = ("rmse_m", "mean_m", "median_m", "max_m", "max_seg_start_t_rel_s", "max_seg_end_t_rel_s",
                 "max_seg_start_stamp", "max_seg_end_stamp")


def write_rpe_vs_delta(path: Path, stats: dict[float, dict[str, float]]) -> None:
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["delta_m", "n_segments", "rpe_trans_rmse_m", "rpe_trans_mean_m", "rpe_trans_median_m",
                    "rpe_trans_max_m", "max_seg_start_t_rel_s", "max_seg_end_t_rel_s", "max_seg_start_stamp",
                    "max_seg_end_stamp"])
        for d, s in stats.items():
            w.writerow([f"{d:g}", s["n_segments"]] + [fmt4(s[k]) for k in ("rmse_m", "mean_m", "median_m", "max_m")]
                       + [fmt_n(s[k], 3) for k in ("max_seg_start_t_rel_s", "max_seg_end_t_rel_s")]
                       + [fmt_n(s[k], 6) for k in ("max_seg_start_stamp", "max_seg_end_stamp")])


def fmt4(v: float) -> str:
    return fmt_n(v, 4)


def fmt_n(v: float, decimals: int) -> str:
    return "" if np.isnan(v) else f"{v:.{decimals}f}"


def roll_pitch_tilt_deg(rot: np.ndarray) -> tuple[float, float, float]:
    """Roll and pitch (ZYX Euler) of a rotation matrix, and the total tilt of its z axis, in degrees."""
    roll = np.arctan2(rot[2, 1], rot[2, 2])
    pitch = -np.arcsin(np.clip(rot[2, 0], -1.0, 1.0))
    tilt = np.arccos(np.clip(rot[2, 2], -1.0, 1.0))
    return float(np.degrees(roll)), float(np.degrees(pitch)), float(np.degrees(tilt))


def rmse(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x))))


def write_error_vs_distance(path: Path, t_rel: np.ndarray, dist: np.ndarray, horiz_start: np.ndarray,
                            vert_start: np.ndarray, horiz_whole_se3: np.ndarray,
                            horiz_whole_yaw: np.ndarray) -> None:
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["t_rel_s", "distance_m", "horiz_err_start_aligned_m", "vert_err_start_aligned_m",
                    "horiz_err_whole_se3_aligned_m", "horiz_err_whole_yaw_aligned_m"])
        for row in zip(t_rel, dist, horiz_start, vert_start, horiz_whole_se3, horiz_whole_yaw):
            w.writerow([f"{v:.6f}" for v in row])


def plot_trajectory(path: Path, name: str, gt: PoseTrajectory3D, est: PoseTrajectory3D) -> None:
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot(gt.positions_xyz[:, 0], gt.positions_xyz[:, 1], label="ground truth", lw=1.5)
    ax.plot(est.positions_xyz[:, 0], est.positions_xyz[:, 1], label="OpenVINS (SE(3)-aligned)", lw=1)
    ax.set(xlabel="x [m]", ylabel="y [m]", title=f"{name}: top view", aspect="equal")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def plot_error_vs_distance(path: Path, out: Path, names: list[str], start_align_m: float) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    for name in names:
        data = np.loadtxt(out / f"{name}_error_vs_distance.csv", delimiter=",", skiprows=1)
        line, = ax.plot(data[:, 1], data[:, 2], label=f"{name} horizontal", lw=1)
        ax.plot(data[:, 1], np.abs(data[:, 3]), label=f"{name} |vertical|", lw=1, ls="--", color=line.get_color())
    ax.set(xlabel="distance travelled along ground truth [m]", ylabel="position error [m]",
           title=f"OpenVINS error vs distance (yaw+translation aligned on first {start_align_m:g} m)")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def write_summary(path: Path, results: list[SeqResult], deltas: list[float]) -> None:
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["sequence", "matched_poses", "skip_start_s", "skipped_poses", "duration_s", "gt_length_m", "est_length_m", "ate_rmse_m", "ate_max_m"]
                   + [f"rpe_trans_rmse_{d:g}m" for d in deltas] + [f"rpe_trans_median_{d:g}m" for d in deltas]
                   + [f"rpe_pairs_{d:g}m" for d in deltas]
                   + ["horiz_rmse_start_aligned_m", "horiz_rmse_whole_se3_aligned_m", "horiz_rmse_whole_yaw_aligned_m",
                      "horiz_mean_abs_diff_m", "horiz_max_abs_diff_m", "se3_align_roll_deg", "se3_align_pitch_deg",
                      "se3_align_tilt_deg", "vert_rmse_start_aligned_m", "final_horiz_err_start_aligned_m",
                      "final_vert_err_start_aligned_m"])
        for r in results:
            w.writerow([r.name, r.n_matched, f"{r.skip_start_s:g}", r.n_skipped, f"{r.duration_s:.2f}", f"{r.gt_length_m:.2f}", f"{r.est_length_m:.2f}",
                        f"{r.ate_rmse_m:.4f}", f"{r.ate_max_m:.4f}"] + [fmt4(r.rpe_rmse_m[d]) for d in deltas]
                       + [fmt4(r.rpe_median_m[d]) for d in deltas]
                       + [r.rpe_pairs[d] for d in deltas]
                       + [f"{v:.4f}" for v in (r.horiz_rmse_start_m, r.horiz_rmse_whole_se3_m, r.horiz_rmse_whole_yaw_m,
                                                 r.horiz_mean_abs_diff_m, r.horiz_max_abs_diff_m, r.se3_roll_deg,
                                                 r.se3_pitch_deg, r.se3_tilt_deg, r.vert_rmse_start_m,
                                                 r.final_horiz_start_m, r.final_vert_start_m)])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seq", nargs=3, action="append", required=True, metavar=("NAME", "EST_TUM", "GT"),
                    help="sequence name, estimate (TUM), ground truth (EuRoC CSV or TUM); repeatable")
    ap.add_argument("--out", type=Path, required=True, help="output directory")
    ap.add_argument("--rpe-deltas", type=float, nargs="+", default=[1.0, 10.0, 50.0],
                    help="RPE segment lengths [m] reported in vio_scores.csv")
    ap.add_argument("--rpe-curve-deltas", type=float, nargs="+", default=[1.0, 2.0, 5.0, 10.0, 20.0, 50.0],
                    help="RPE segment lengths [m] written per sequence to <name>_rpe_vs_delta.csv")
    ap.add_argument("--start-align-m", type=float, default=5.0, help="alignment window for error vs distance [m travelled]")
    ap.add_argument("--skip-start-s", type=float, default=2.0,
                    help="leave out poses earlier than the first estimated pose + this [s] from RPE and from the "
                         "start-alignment window (0 = earlier behaviour)")
    ap.add_argument("--max-time-diff", type=float, default=0.01, help="max timestamp gap when matching poses [s]")
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    results = [score(name, Path(est), Path(gt), args, args.out) for name, est, gt in args.seq]
    write_summary(args.out / "vio_scores.csv", results, args.rpe_deltas)
    plot_error_vs_distance(args.out / "error_vs_distance.png", args.out, [r.name for r in results], args.start_align_m)
    settings = {"alignment_ate_rpe": "SE(3) Umeyama, all matched poses, no scale",
                # fit_drift_model.py must copy this block into drift_params.json
                "drift_curve_alignment": {"method": "4dof_yaw_translation", "window_m": args.start_align_m,
                                          "skip_start_s": args.skip_start_s,
                                          "skip_start_meaning": "alignment window starts at the first matched pose at or after the first estimated pose + skip_start_s; error rows still cover all poses, distance from the first matched pose",
                                          "window_unit": "metres travelled along ground truth",
                                          "error_split": "horizontal = norm of (x,y) error; vertical = signed z error (est - gt)",
                                          "comparison_curves": "horizontal error with SE(3) alignment over all poses (cross-check), and with 4-DoF over all poses",
                                          "tilt_check": "roll/pitch (ZYX Euler, degrees) of the SE(3) rotation applied to the estimate",
                                          "assumption": "z axis along gravity in estimate and ground truth"},
                "rpe_skip_start_s": args.skip_start_s, "rpe_deltas_m": args.rpe_deltas, "rpe_curve_deltas_m": args.rpe_curve_deltas,
                "rpe_segments": "evo RPE translation_part, consecutive non-overlapping segments, length measured along the estimate's path (pairs_from_reference=False), after SE(3) alignment",
                "max_time_diff_s": args.max_time_diff,
                "inputs": {n: {"estimate": e, "ground_truth": g} for n, e, g in args.seq}}
    (args.out / "vio_scores_settings.json").write_text(json.dumps(settings, indent=2) + "\n")
    for r in results:
        print(f"{r.name}: {r.n_matched} poses, ATE RMSE {r.ate_rmse_m:.3f} m")
        print(f"{r.name}: path length estimate {r.est_length_m:.2f} m, ground truth {r.gt_length_m:.2f} m "
              f"(estimate / ground truth {r.est_length_m / r.gt_length_m:.3f})")
        print(f"{r.name}: horizontal error RMSE {r.horiz_rmse_start_m:.3f} m (aligned on first {args.start_align_m:g} m) vs "
              f"{r.horiz_rmse_whole_se3_m:.3f} m (whole-trajectory SE(3)) / {r.horiz_rmse_whole_yaw_m:.3f} m "
              f"(whole-trajectory yaw+translation); start vs SE(3) curves differ by mean "
              f"{r.horiz_mean_abs_diff_m:.3f} m, max {r.horiz_max_abs_diff_m:.3f} m")
        print(f"{r.name}: SE(3) alignment rotation roll {r.se3_roll_deg:+.3f} deg, pitch {r.se3_pitch_deg:+.3f} deg "
              f"(tilt {r.se3_tilt_deg:.3f} deg)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
