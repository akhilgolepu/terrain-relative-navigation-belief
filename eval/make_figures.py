#!/usr/bin/env python3
"""Figures for the write-up (docs/figures/): drift sweep, validity timeline (from the rosbag), reliability.

  drift_sweep.png          RMSE vs SYNTHETIC drift level, flights 10 and 05, frozen fusion design
                           (eval/results/week7/frozen_design/fusion_<f>.csv): fused, odometry-only from
                           the prior and from the true start, all raw fixes; bars = seed p5-p95
  validity_timeline.png    the recorded replay (rosbag ~/data/rosbags/replay_10_1pct_seed0, flight 10,
                           1 % drift): fused error vs label with the 2-sigma band, validity and consumer action
  calibration_reliability.png  week 5 P(wrong) reliability, selected (ratio) and constant models,
                           flight 05 out-of-fold and flight 10 (eval/results/week5/eval_<f>.json)
Every figure says: errors against dataset labels (incl. label registration error); odometry SYNTHETIC.
Needs ROS sourced for the bag (rosbag2_py). Usage: python3 eval/make_figures.py
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
FIG = HERE.parent / "docs/figures"
BAG = Path.home() / "data/rosbags/replay_10_1pct_seed0"
NOTE = "Errors vs dataset labels (include label registration error); odometry is SYNTHETIC."
C = {"fused": "#2a78d6", "odo_prior": "#eb6834", "odo_true": "#1baf7a", "fixes": "#eda100"}
STATES = ["STRONG", "UNCERTAIN", "AGING", "DO_NOT_PUBLISH"]
SCOL = {"STRONG": "#1baf7a", "UNCERTAIN": "#eda100", "AGING": "#e87ba4", "DO_NOT_PUBLISH": "#e34948"}


def style(ax):
    ax.grid(color="#e6e6e6", lw=0.8)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def drift_sweep(plt):
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.8), dpi=140, sharey=False)
    for ax, f in zip(axes, ("10", "05")):
        rows = list(csv.DictReader((HERE / f"results/week7/frozen_design/fusion_{f}.csv").open()))
        levels = sorted({float(r["drift_pct"]) for r in rows})
        for key, name, col in (("fused_rmse", "fused", C["fused"]), ("odotrue_rmse", "odometry from true start",
                                                                     C["odo_true"]),
                               ("odo_rmse", "odometry from prior", C["odo_prior"])):
            m, lo, hi = [], [], []
            for lv in levels:
                v = np.array([float(r[key]) for r in rows if float(r["drift_pct"]) == lv])
                m.append(v.mean())
                lo.append(v.mean() - np.percentile(v, 5))
                hi.append(np.percentile(v, 95) - v.mean())
            ax.errorbar(levels, m, yerr=[lo, hi], marker="o", ms=6, lw=2, capsize=3, color=col, label=name,
                        ls="-" if name == "fused" else "--")
        ax.axhline(float(rows[0]["fixes_rmse"]), color=C["fixes"], lw=2, ls=":", label="all raw fixes")
        ax.set_xscale("log")
        ax.set_xticks(levels)
        ax.set_xticklabels([f"{lv:g} %" for lv in levels])
        ax.set_xlabel("SYNTHETIC drift (RMS after 10 km, % of 10 km)")
        ax.set_ylabel("position RMSE vs label [m]")
        ax.set_title(f"Flight {f} ({'tune' if f == '10' else 'calibrate, in-sample for the fix model'})", fontsize=9)
        style(ax)
    axes[0].legend(frameon=False, fontsize=7, loc="upper left")
    fig.suptitle("Drift sweep, frozen fusion design (20 seeds, bars p5-p95). " + NOTE, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "drift_sweep.png", facecolor="white")
    plt.close(fig)


def read_bag():
    import rosbag2_py
    from rclpy.serialization import deserialize_message
    from rosidl_runtime_py.utilities import get_message
    reader = rosbag2_py.SequentialReader()
    reader.open(rosbag2_py.StorageOptions(uri=str(BAG), storage_id="mcap"),
                rosbag2_py.ConverterOptions("cdr", "cdr"))
    types = {t.name: t.type for t in reader.get_all_topics_and_types()}
    out = {"/nav_belief": [], "/consumer/action": []}
    while reader.has_next():
        topic, data, _ = reader.read_next()
        if topic in out:
            out[topic].append(deserialize_message(data, get_message(types[topic])))
    return out


def validity_timeline(plt):
    msgs = read_bag()
    inp = list(csv.DictReader((HERE / "results/week6/inputs_10.csv").open()))
    lab = {round(float(r["t_s"]), 3): (float(r["true_e"]), float(r["true_n"])) for r in inp}
    names = {0: "STRONG", 1: "AGING", 2: "UNCERTAIN", 3: "DO_NOT_PUBLISH"}
    last = {}
    for m in msgs["/nav_belief"]:
        t = round(m.header.stamp.sec - 1_700_000_000 + m.header.stamp.nanosec * 1e-9, 3)
        last[t] = m
    ts = np.array(sorted(t for t in last if t in lab))
    err = np.array([math.hypot(last[t].pose.pose.position.x - lab[t][0], last[t].pose.pose.position.y - lab[t][1])
                    for t in ts])
    sig = np.array([math.sqrt(max(np.linalg.eigvalsh([[last[t].pose.covariance[0], last[t].pose.covariance[1]],
                                                      [last[t].pose.covariance[6], last[t].pose.covariance[7]]])))
                    for t in ts])
    state = [names[last[t].validity] for t in ts]
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(8, 4.4), dpi=140, sharex=True, gridspec_kw={"height_ratios": [4, 1]})
    ax.fill_between(ts, 0, 2 * sig, color=C["fused"], alpha=0.15, lw=0, label="2-sigma (major axis)")
    ax.plot(ts, err, color=C["fused"], lw=2, label="fused error vs label")
    ax.set_ylabel("error [m]")
    ax.set_title("Recorded ROS replay (rosbag): flight 10, 1 % SYNTHETIC drift, fixes throughout.\n" + NOTE, fontsize=8)
    ax.legend(frameon=False, fontsize=7, loc="upper right")
    for i, s in enumerate(STATES):
        msk = np.array([x == s for x in state])
        ax2.scatter(ts[msk], np.full(msk.sum(), i), s=6, color=SCOL[s])
    ax2.set_yticks(range(len(STATES)))
    ax2.set_yticklabels(STATES, fontsize=6)
    ax2.set_xlabel("flight time [s]")
    for a in (ax, ax2):
        style(a)
    fig.tight_layout()
    fig.savefig(FIG / "validity_timeline.png", facecolor="white")
    plt.close(fig)
    return len(msgs["/nav_belief"]), float(np.mean(err <= 2 * sig))


def reliability(plt):
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.8), dpi=140)
    for ax, f, title in zip(axes, ("05", "10"), ("Flight 05, out-of-fold (fit flight)", "Flight 10, frozen model")):
        res = json.loads((HERE / f"results/week5/eval_{f}.json").read_text())
        ax.plot([0, 1], [0, 1], color="#999999", lw=1, ls="--", label="perfect calibration")
        for role, col in (("selected", C["fused"]), ("baseline_const", C["odo_true"])):
            rel = res["models"][role]["reliability"]
            ax.plot([b["pred"] for b in rel], [b["obs"] for b in rel], marker="o", ms=6, lw=2, color=col,
                    label=f"{'ratio model' if role == 'selected' else 'constant'} (ECE {res['models'][role]['ece']:.3f})")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_xlabel("predicted P(|e| > 50 m)")
        ax.set_ylabel("observed wrong rate")
        ax.set_title(title, fontsize=9)
        ax.legend(frameon=False, fontsize=7, loc="upper left")
        style(ax)
    fig.suptitle("Fix-error calibration (week 5), equal-count bins. Errors vs dataset labels (include label "
                 "registration error).", fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "calibration_reliability.png", facecolor="white")
    plt.close(fig)


def main() -> int:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    FIG.mkdir(parents=True, exist_ok=True)
    drift_sweep(plt)
    n, inside = validity_timeline(plt)
    reliability(plt)
    print(f"wrote {FIG}/drift_sweep.png, validity_timeline.png ({n} beliefs from the bag; error inside 2-sigma "
          f"on {inside:.0%} of frames), calibration_reliability.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
