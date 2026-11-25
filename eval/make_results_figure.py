#!/usr/bin/env python3
"""One-page results figure for the README: docs/figures/results_flight11.png.

Flight 11 (test, run once): fused closed loop (seeds 0-4, eval/results/test_flight11/closed_loop_summary.csv),
odometry from the perfect start (seeds 0-19, open_loop.csv) and raw fixes (T1 row of results.md), across
the SYNTHETIC drift levels. Development flights 10 (tune) and 05 (calibrate) are drawn faded
(frozen design, open loop, eval/results/week7/frozen_design/fusion_<f>.csv). Errors are against dataset
labels and include label registration error. Usage: python3 eval/make_results_figure.py
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
OUT = HERE.parent / "docs/figures/results_flight11.png"
C = {"fused": "#2a78d6", "odo": "#eb6834", "fixes": "#b58300"}


def stats(rows, key, levels):
    m, lo, hi = [], [], []
    for lv in levels:
        v = np.array([float(r[key]) for r in rows if float(r["drift_pct"]) == lv])
        m.append(v.mean())
        lo.append(v.mean() - np.percentile(v, 5))
        hi.append(np.percentile(v, 95) - v.mean())
    return np.array(m), np.array([lo, hi])


def raw_fixes_rmse_11() -> float:
    text = (HERE / "results/test_flight11/results.md").read_text()
    row = next(line for line in text.splitlines() if line.startswith("| 0.1 %"))
    return float(re.split(r"\s*\|\s*", row)[6].split()[0])   # column "Raw fixes RMSE (median)"


def main() -> int:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    closed = list(csv.DictReader((HERE / "results/test_flight11/closed_loop_summary.csv").open()))
    openl = list(csv.DictReader((HERE / "results/test_flight11/open_loop.csv").open()))
    levels = sorted({float(r["drift_pct"]) for r in closed})
    fig, ax = plt.subplots(figsize=(8, 4.6), dpi=150)
    for f, name in (("10", "tune"), ("05", "calibrate")):
        dev = list(csv.DictReader((HERE / f"results/week7/frozen_design/fusion_{f}.csv").open()))
        for key, col, ls in (("fused_rmse", C["fused"], "-"), ("odotrue_rmse", C["odo"], "--")):
            m, _ = stats(dev, key, levels)
            ax.plot(levels, m, color=col, lw=1.2, ls=ls, alpha=0.25)
        ax.axhline(float(dev[0]["fixes_rmse"]), color=C["fixes"], lw=1.0, ls=":", alpha=0.25)
        m, _ = stats(dev, "fused_rmse", levels)
        ax.text(levels[-1] * 1.04, m[-1], f"fused, flight {f} ({name})", fontsize=6.5, color=C["fused"], alpha=0.6,
                va="center")
    m, e = stats(closed, "rmse", levels)
    ax.errorbar(levels, m, yerr=e, color=C["fused"], lw=2.5, marker="o", ms=7, capsize=3,
                label="fused, closed loop (test flight 11)")
    m_o, e_o = stats(openl, "odo_true_rmse", levels)
    ax.errorbar(levels, m_o, yerr=e_o, color=C["odo"], lw=2.5, ls="--", marker="s", ms=6, capsize=3,
                label="odometry only, perfect start (flight 11)")
    ax.axhline(raw_fixes_rmse_11(), color=C["fixes"], lw=2.5, ls=":", label="raw terrain fixes, no fusion (flight 11)")
    ax.plot([], [], color="#888888", alpha=0.35, lw=1.2, label="development flights 10 and 05 (faded)")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xticks(levels)
    ax.set_xticklabels([f"{lv:g} %" for lv in levels])
    ax.set_xlim(levels[0] * 0.8, levels[-1] * 2.2)
    ax.set_xlabel("SYNTHETIC odometry drift (RMS after 10 km, % of 10 km)")
    ax.set_ylabel("position RMSE against dataset labels [m]")
    ax.set_title("Held-out test flight 11, run once after pre-registration: fusion vs odometry vs raw fixes\n"
                 "Errors are against dataset labels and include label registration error; odometry is SYNTHETIC; "
                 "bars = seed p5-p95", fontsize=8.5)
    ax.grid(color="#e6e6e6", lw=0.8, which="both")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.legend(frameon=False, fontsize=7.5, loc="upper left")
    fig.tight_layout()
    fig.savefig(OUT, facecolor="white")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
