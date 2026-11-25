"""Input/output helpers for the VIO drift model (scaffolding only; the model and the fit live in fit_drift_model.py).

- distinct_runs():        one run per distinct outcome (vio_run_identity.csv), so byte-identical repeats count once
- load_rpe_points():      RPE RMSE / median vs segment length from <run>_rpe_vs_delta.csv, up to a maximum length
- scoring_settings():     the alignment and RPE settings the RPE values were produced with (vio_scores_settings.json),
                          to be copied into drift_params.json
- plot_rpe_vs_delta():    log-log plot of RMSE vs segment length per run, with optional fitted curves
"""
from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np


@dataclass
class RpePoints:
    run: str
    sequence: str
    delta_m: np.ndarray       # segment length [m]
    rmse_m: np.ndarray        # translation RPE RMSE over all segments of that length [m]
    median_m: np.ndarray      # translation RPE median [m]
    n_segments: np.ndarray    # number of segments behind each value
    source: Path


def distinct_runs(results: Path) -> list[str]:
    """First run (by name) of each distinct outcome in vio_run_identity.csv."""
    seen: set[str] = set()
    runs = []
    for row in sorted(csv.DictReader((results / "vio_run_identity.csv").open()), key=lambda r: r["run"]):
        if row["outcome"] not in seen:
            seen.add(row["outcome"])
            runs.append(row["run"])
    return runs


def load_rpe_points(results: Path, run: str, max_delta_m: float = float("inf")) -> RpePoints:
    """Segment lengths <= max_delta_m with at least one segment, from <run>_rpe_vs_delta.csv."""
    path = results / f"{run}_rpe_vs_delta.csv"
    rows = [r for r in csv.DictReader(path.open())
            if int(r["n_segments"]) > 0 and float(r["delta_m"]) <= max_delta_m]
    col = lambda k, f=float: np.array([f(r[k]) for r in rows])  # noqa: E731
    return RpePoints(run, run.rsplit("_run", 1)[0], col("delta_m"), col("rpe_trans_rmse_m"),
                     col("rpe_trans_median_m"), col("n_segments", int), path)


def scoring_settings(results: Path) -> dict:
    """Settings the RPE values were computed with, for drift_params.json."""
    s = json.loads((results / "vio_scores_settings.json").read_text())
    return {"drift_curve_alignment": s["drift_curve_alignment"],
            "rpe_skip_start_s": s["rpe_skip_start_s"], "rpe_segments": s["rpe_segments"],
            "alignment_ate_rpe": s["alignment_ate_rpe"], "max_time_diff_s": s["max_time_diff_s"]}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_loglog_slopes(delta_m: np.ndarray, e_m: np.ndarray) -> np.ndarray:
    """Slope of log(e) vs log(delta) between neighbouring segment lengths (a power law gives a constant slope)."""
    return np.diff(np.log(e_m)) / np.diff(np.log(delta_m))


def plot_rpe_vs_delta(path: Path, points: list[RpePoints], title: str,
                      fits: dict[str, Callable[[np.ndarray], np.ndarray]] | None = None,
                      reference_slopes: tuple[float, ...] = (0.5, 1.0), fit_max_delta_m: float | None = None) -> None:
    """Log-log RMSE vs segment length, one line per run (point labels = number of segments).
    `fits` maps a label to e(delta) [m], drawn over the plotted range; fit_max_delta_m draws a vertical line at the
    end of the fitted range (curves beyond it are extrapolation). Reference slopes are drawn through the mean
    1 m value, as visual guides only."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 5))
    for p in points:
        line, = ax.plot(p.delta_m, p.rmse_m, "o-", label=f"{p.run} RMSE")
        for d, e, n in zip(p.delta_m, p.rmse_m, p.n_segments):
            ax.annotate(str(n), (d, e), textcoords="offset points", xytext=(4, -10), fontsize=7, color=line.get_color())
    d_all = np.concatenate([p.delta_m for p in points])
    grid = np.geomspace(d_all.min(), d_all.max(), 100)
    anchor = np.mean([p.rmse_m[np.argmin(p.delta_m)] for p in points])
    for slope in reference_slopes:
        ax.plot(grid, anchor * (grid / grid[0]) ** slope, ":", color="grey", lw=1)
        ax.annotate(f"slope {slope:g}", (grid[-1], anchor * (grid[-1] / grid[0]) ** slope), fontsize=7, color="grey")
    for label, f in (fits or {}).items():
        ax.plot(grid, f(grid), "--", lw=2, label=label)
    if fit_max_delta_m is not None:
        ax.axvline(fit_max_delta_m, color="black", lw=1, alpha=0.6)
        ax.annotate("end of fitted range\n(extrapolation beyond)", (fit_max_delta_m,
                    min(p.rmse_m.min() for p in points)), xytext=(4, 0), textcoords="offset points", fontsize=7)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("segment length δ [m] (measured along the estimate's path)")
    ax.set_ylabel("translation RPE RMSE [m]")
    ax.set_title(title, fontsize=10)
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
