#!/usr/bin/env python3
"""Look for gaps and jumps in the raw estimate and raw ground truth around each run's worst RPE segment.

For every run and segment length in <run>_rpe_vs_delta.csv (written by score_vio.py), take the time window of the
segment with the largest RPE (padded by --margin-s on each side) and report, separately for the estimate (TUM file)
and the ground truth (file given to score_vio.py; inputs read from vio_scores_settings.json):
  - largest time gap between consecutive poses,
  - largest position step and the speed it implies,
  - largest orientation step and the angular rate it implies,
each next to the same quantity's whole-trajectory median and 99.9th percentile, so a jump stands out as a value far
above the trajectory's own 99.9th percentile; plus, for the whole trajectory, the number and total length of time
gaps longer than 5 x its median pose interval (poses missing, e.g. motion-capture dropouts in the ground truth),
and its first step (pose 1 -> pose 2: for the estimate, the first step after OpenVINS initialised).
Raw files are used: no alignment and no timestamp matching.

Writes RESULTS/rpe_max_segment_check.csv (one row per run x segment length x trajectory).

Usage (in ~/venvs/trn): python eval/check_rpe_segments.py eval/results/vio [--runs room2_run1 ...] [--margin-s 0.5]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation


def load_tum(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Timestamps, xyz and quaternions (x, y, z, w) of a TUM file; '#' lines are comments."""
    a = np.loadtxt(path, comments="#")
    return a[:, 0], a[:, 1:4], a[:, 4:8]


def step_series(t: np.ndarray, xyz: np.ndarray, quat: np.ndarray) -> dict[str, np.ndarray]:
    """Per consecutive pair: time gap [s], position step [m], speed [m/s], rotation step [deg], rate [deg/s].
    Entry k describes the step from pose k to pose k+1."""
    dt = np.diff(t)
    step = np.linalg.norm(np.diff(xyz, axis=0), axis=1)
    rot = Rotation.from_quat(quat)
    ang = np.degrees((rot[:-1].inv() * rot[1:]).magnitude())
    safe_dt = np.where(dt > 0, dt, np.nan)
    return {"dt_s": dt, "step_m": step, "speed_mps": step / safe_dt, "rot_deg": ang, "rate_dps": ang / safe_dt}


GAP_FACTOR = 5.0  # a time gap is a pose interval longer than this many median intervals


def window_report(t: np.ndarray, series: dict[str, np.ndarray], t0: float, t1: float) -> dict[str, float]:
    """Max of each step quantity inside [t0, t1] (steps that start or end inside), its time, and whole-run
    median and 99.9th percentile of the same quantity."""
    inside = (t[1:] >= t0) & (t[:-1] <= t1)
    out: dict[str, float] = {"n_poses_in_window": int(np.sum((t >= t0) & (t <= t1)))}
    dt = series["dt_s"]
    gaps = dt[dt > GAP_FACTOR * np.median(dt)]
    out["whole_n_gaps"], out["whole_gap_total_s"] = int(gaps.size), float(gaps.sum())
    out["first_step_at"] = float(t[0])
    for key in ("dt_s", "step_m", "speed_mps", "rot_deg"):
        out[f"first_step_{key}"] = float(series[key][0])
    for key, v in series.items():
        out[f"whole_median_{key}"] = float(np.nanmedian(v))
        out[f"whole_p999_{key}"] = float(np.nanpercentile(v, 99.9))
        if not inside.any():
            out[f"win_max_{key}"], out[f"win_max_{key}_at"] = float("nan"), float("nan")
            continue
        idx = np.flatnonzero(inside)
        k = idx[int(np.nanargmax(v[idx]))]
        out[f"win_max_{key}"], out[f"win_max_{key}_at"] = float(v[k]), float(t[k])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("results", type=Path)
    ap.add_argument("--runs", nargs="+", help="default: every run in vio_scores_settings.json")
    ap.add_argument("--margin-s", type=float, default=0.5, help="padding on each side of the segment window [s]")
    args = ap.parse_args()

    inputs = json.loads((args.results / "vio_scores_settings.json").read_text())["inputs"]
    rows = []
    for run in args.runs or sorted(inputs):
        trajs = {"estimate": Path(inputs[run]["estimate"]).expanduser(),
                 "ground_truth": Path(inputs[run]["ground_truth"]).expanduser()}
        loaded = {name: load_tum(p) for name, p in trajs.items()}
        series = {name: step_series(*loaded[name]) for name in trajs}
        for seg in csv.DictReader((args.results / f"{run}_rpe_vs_delta.csv").open()):
            if not seg["max_seg_start_stamp"]:
                continue
            t0 = float(seg["max_seg_start_stamp"]) - args.margin_s
            t1 = float(seg["max_seg_end_stamp"]) + args.margin_s
            for name in trajs:
                rep = window_report(loaded[name][0], series[name], t0, t1)
                rows.append({"run": run, "delta_m": seg["delta_m"], "rpe_trans_max_m": seg["rpe_trans_max_m"],
                             "seg_start_t_rel_s": seg["max_seg_start_t_rel_s"],
                             "seg_end_t_rel_s": seg["max_seg_end_t_rel_s"],
                             "seg_start_stamp": seg["max_seg_start_stamp"], "seg_end_stamp": seg["max_seg_end_stamp"],
                             "trajectory": name,
                             **{k: (f"{v:.6f}" if k.endswith("_at") else f"{v:.4f}") if isinstance(v, float) else v
                                for k, v in rep.items()}})
    out = args.results / "rpe_max_segment_check.csv"
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {out} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
