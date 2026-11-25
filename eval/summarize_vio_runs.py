#!/usr/bin/env python3
"""Summarise repeated OpenVINS runs: mean and spread of the scores per sequence, and a health check per run.

Reads, from one results directory:
  vio_scores.csv                 written by score_vio.py; run names must look like <sequence>_run<N>
  <run>_run_status.txt           written by run_openvins.sh (how `ros2 bag play` ended, input bag)
  <run>_openvins.log, <run>_play.log, <run>_record.log, <run>_openvins.tum
Only runs in vio_scores.csv are summarised; eval/score_week2_vio.sh leaves invalid runs out of it and lists them
in vio_invalid_runs.csv.
Writes
  vio_runs_summary.csv           mean, sample std, min, max per metric over all runs
  vio_run_identity.csv           which runs of a sequence have byte-identical pose files (<run>_openvins.tum, SHA-256)
  vio_runs_summary_distinct.csv  the same statistics over distinct outcomes only (one run per identical group), so
                                 repeated identical runs do not shrink the spread
  vio_run_health.csv             one row per run.
Health column max_imu_cam_gap_data_time_s: OpenVINS prints "[TIME]: ... (H hz, X ms behind)" with
X = 100 * (newest IMU time - time of the camera frame being processed) (ov_msckf ROS2Visualizer.cpp), i.e. how long,
in recorded data time, a camera frame waited for a later IMU sample. It is not wall-clock processing delay, and the
factor is 100, not 1000; the column is X / 100 in seconds. updates_slower_than_20hz counts updates whose wall-clock
processing time (1 / H) exceeded 50 ms.

Usage: python3 eval/summarize_vio_runs.py eval/results/vio
"""
from __future__ import annotations

import csv
import hashlib
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import yaml

METRICS = ["ate_rmse_m", "rpe_trans_rmse_1m", "rpe_trans_median_1m", "rpe_trans_rmse_10m", "rpe_trans_median_10m",
           "se3_align_roll_deg", "se3_align_pitch_deg",
           "se3_align_tilt_deg", "final_horiz_err_start_aligned_m", "final_vert_err_start_aligned_m",
           "horiz_rmse_start_aligned_m", "vert_rmse_start_aligned_m"]
PROBLEM_WORDS = re.compile(r"drop|overflow|queue|lost|skip", re.IGNORECASE)
ANSI = re.compile(r"\x1b\[[0-9;]*m")
TIME_LINE = re.compile(r"\(([\d.]+) hz, ([\d.]+) ms behind")


def sequence_of(run: str) -> str:
    return re.sub(r"_run\d+$", "", run)


def spread(values: list[float]) -> dict[str, float]:
    return {"mean": statistics.fmean(values), "std": statistics.stdev(values) if len(values) > 1 else 0.0,
            "min": min(values), "max": max(values)}


def summarise_scores(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    by_seq: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_seq[sequence_of(row["sequence"])].append(row)
    out = []
    for seq, runs in sorted(by_seq.items()):
        for metric in METRICS:
            s = spread([float(r[metric]) for r in runs])
            out.append({"sequence": seq, "metric": metric, "n_runs": len(runs),
                        **{k: f"{v:.4f}" for k, v in s.items()}})
    return out


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity_groups(hashes: dict[str, str]) -> list[dict[str, object]]:
    """One row per run: its sequence, pose-file hash, outcome label (A, B, ... per sequence in order of first run)
    and the other runs of the same sequence with a byte-identical pose file."""
    rows = []
    by_seq: dict[str, list[str]] = defaultdict(list)
    for run in sorted(hashes):
        by_seq[sequence_of(run)].append(run)
    for seq, runs in sorted(by_seq.items()):
        labels: dict[str, str] = {}
        for run in runs:
            labels.setdefault(hashes[run], chr(ord("A") + len(labels)))
        for run in runs:
            same = [r for r in runs if r != run and hashes[r] == hashes[run]]
            rows.append({"run": run, "sequence": seq, "pose_file_sha256": hashes[run],
                         "outcome": f"{seq}_{labels[hashes[run]]}", "n_distinct_in_sequence": len(labels),
                         "identical_to": " ".join(same)})
    return rows


def distinct_rows(rows: list[dict[str, str]], identity: list[dict[str, object]]) -> list[dict[str, str]]:
    """Keep the first run of each outcome."""
    outcome = {i["run"]: i["outcome"] for i in identity}
    seen, out = set(), []
    for row in sorted(rows, key=lambda r: r["sequence"]):
        if outcome[row["sequence"]] not in seen:
            seen.add(outcome[row["sequence"]])
            out.append(row)
    return out


def camera_frames(bag_dir: Path) -> int:
    """Message count of /cam0/image_raw from the input bag's metadata.yaml."""
    info = yaml.safe_load((bag_dir / "metadata.yaml").read_text())["rosbag2_bagfile_information"]
    counts = {t["topic_metadata"]["name"]: t["message_count"] for t in info["topics_with_message_count"]}
    return counts["/cam0/image_raw"]


def count_problem_lines(path: Path) -> int:
    return sum(bool(PROBLEM_WORDS.search(line)) for line in ANSI.sub("", path.read_text(errors="replace")).splitlines())


def health(results: Path, run: str) -> dict[str, object]:
    status = dict(line.split("=", 1) for line in (results / f"{run}_run_status.txt").read_text().splitlines())
    log = ANSI.sub("", (results / f"{run}_openvins.log").read_text(errors="replace"))
    timing = [(float(hz), float(ms)) for hz, ms in TIME_LINE.findall(log)]
    poses = sum(1 for line in (results / f"{run}_openvins.tum").read_text().splitlines() if not line.startswith("#"))
    return {"run": run, "camera_frames_in_bag": camera_frames(Path(status["bag"]).expanduser()),
            "openvins_updates": len(timing), "poses_output": poses,
            "max_imu_cam_gap_data_time_s": f"{max(x for _, x in timing) / 100.0:.4f}",
            "updates_slower_than_20hz": sum(hz < 20.0 for hz, _ in timing),
            "problem_lines_openvins": count_problem_lines(results / f"{run}_openvins.log"),
            "problem_lines_play": count_problem_lines(results / f"{run}_play.log"),
            "problem_lines_record": count_problem_lines(results / f"{run}_record.log"),
            "play_wall_s": status["play_wall_s"], "play_end": status["play_end"],
            "recorder_end": status["recorder_end"], "openvins_end": status["openvins_end"],
            "leftover_openvins_processes": status["leftover_openvins_processes"]}


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    results = Path(sys.argv[1])
    rows = list(csv.DictReader((results / "vio_scores.csv").open()))
    summary = summarise_scores(rows)
    identity = identity_groups({r["sequence"]: file_sha256(results / f"{r['sequence']}_openvins.tum") for r in rows})
    distinct = summarise_scores(distinct_rows(rows, identity))
    for d in distinct:
        d["n_distinct_outcomes"] = d.pop("n_runs")
        d["outcomes"] = " ".join(sorted({i["outcome"] for i in identity if i["sequence"] == d["sequence"]}))
    healths = [health(results, r["sequence"]) for r in rows]
    write_csv(results / "vio_runs_summary.csv", summary)
    write_csv(results / "vio_run_identity.csv", identity)
    write_csv(results / "vio_runs_summary_distinct.csv", distinct)
    write_csv(results / "vio_run_health.csv", healths)
    for i in identity:
        print(f"{i['run']:12s} outcome {i['outcome']}  sha256 {i['pose_file_sha256'][:16]}  identical to: "
              f"{i['identical_to'] or '-'}")
    for row in summary:
        print(f"{row['sequence']:8s} {row['metric']:34s} n={row['n_runs']} mean {row['mean']} std {row['std']} "
              f"min {row['min']} max {row['max']}")
    for h in healths:
        print(" | ".join(f"{k}={v}" for k, v in h.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
