#!/usr/bin/env python3
"""Per-flight error tables and CDF plots from eval_matcher.py's per-frame CSVs.

Reporting rules (week 4, set by Akhil 2026-11-19):
  - one table per flight; never pooled across flights or splits;
  - every table shows the floor baselines (prior, random) next to the matcher rows; a table
    without both is refused;
  - every table states that errors below about 15 m are not distinguishable from label
    registration error.
Errors are against the dataset labels (UAV-coordinates.csv positions), in metres.

Each flight's table is also repeated for two subsets of its frames, split by how much of the map
patch has imagery (map_valid_frac < --coverage, default 0.9, "blank-patch frames", and the rest),
with the baselines computed on the same frames.

Usage: python3 eval/matcher_report.py RESULTS_DIR [--wrong-m 50] [--coverage 0.9] [--no-plot]
  RESULTS_DIR holds frames_<method>.csv (from eval_matcher.py). Writes summary.csv,
  summary.md and cdf_<flight>.png into RESULTS_DIR.
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

BASELINES = ("prior", "random")
LABEL_FLOOR_M = 15.0
LABEL_NOTE = ("Errors below about 15 m are not distinguishable from label registration error: "
              "week 3 found 10-40 m offsets between the dataset positions and the map "
              "(eval/results/week3/overlay_offsets.csv). Errors are against the dataset labels.")
# categorical slots 1-4 of the dataviz reference palette, fixed order: prior, random, then matchers
COLOURS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]


def read_frames(results: Path) -> list[dict]:
    rows = []
    for path in sorted(results.glob("frames_*.csv")):
        rows += list(csv.DictReader(path.open()))
    return rows


def method_order(methods) -> list[str]:
    """Baselines first in fixed order, then the other methods alphabetically."""
    return [m for m in BASELINES if m in methods] + sorted(m for m in methods if m not in BASELINES)


def stats(rows: list[dict], wrong_m: float) -> dict:
    """Error statistics of one method on one flight. Errors over fixes only; rates over all frames."""
    n = len(rows)
    errs = np.array([float(r["err_m"]) for r in rows if r["status"] == "fix"])
    no_fix = sum(r["status"] != "fix" for r in rows)
    pct = (lambda q: round(float(np.percentile(errs, q)), 1)) if errs.size else (lambda q: math.nan)
    of_fix = (lambda c: round(float(c.sum()) / errs.size, 3)) if errs.size else (lambda c: math.nan)
    return {"n_frames": n, "n_fix": int(errs.size), "no_fix_rate": round(no_fix / n, 3) if n else math.nan,
            "acceptance": round(errs.size / n, 3) if n else math.nan,
            "median_m": pct(50), "p95_m": pct(95),
            "within_15m_rate": round(float((errs <= LABEL_FLOOR_M).sum()) / n, 3) if n else math.nan,
            "within_15m_of_fixes": of_fix(errs <= LABEL_FLOOR_M),
            f"wrong_over_{wrong_m:g}m_rate": round(float((errs > wrong_m).sum()) / n, 3) if n else math.nan,
            f"wrong_over_{wrong_m:g}m_of_fixes": of_fix(errs > wrong_m)}


def flight_tables(rows: list[dict], wrong_m: float = 50.0, coverage: float | None = None) -> dict[tuple, list[dict]]:
    """Return {(split, flight, subset): [row per method]}; raise if a flight lacks a baseline.

    subset is "all frames", or with coverage set also "map imagery < X %" / ">= X %"."""
    groups: dict[tuple, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        groups[(r["split"], r["flight"], "all frames")][r["method"]].append(r)
        if coverage is not None:
            sub = (f"map imagery < {coverage:.0%} of patch" if float(r["map_valid_frac"]) < coverage
                   else f"map imagery >= {coverage:.0%} of patch")
            groups[(r["split"], r["flight"], sub)][r["method"]].append(r)
    tables = {}
    for key, by_method in sorted(groups.items()):
        missing = [b for b in BASELINES if b not in by_method]
        if missing:
            raise ValueError(f"flight {key[1]} ({key[0]}): no {', '.join(missing)} baseline rows; "
                             "every error table must show the baseline floor")
        frames = {m: {r["image"] for r in v} for m, v in by_method.items()}
        ref = frames[BASELINES[0]]
        for m, f in frames.items():
            if f != ref:
                raise ValueError(f"flight {key[1]}: method {m} was run on different frames than the baselines")
        floor = {b: stats(by_method[b], wrong_m) for b in BASELINES}
        tables[key] = []
        for m in method_order(by_method):
            s = stats(by_method[m], wrong_m)
            tables[key].append({"split": key[0], "flight": key[1], "subset": key[2], "method": m,
                                "role": "floor" if m in BASELINES else "matcher", **s,
                                "floor_prior_median_m": floor["prior"]["median_m"],
                                "floor_random_median_m": floor["random"]["median_m"]})
    return tables


def markdown(tables: dict, wrong_m: float) -> str:
    out = []
    for (split, flight, subset), rows in tables.items():
        out.append(f"### Flight {flight} ({split} split), {subset}, n = {rows[0]['n_frames']} frames\n")
        out.append(f"| Method | Role | Fixes | Acceptance | Median [m] | p95 [m] | Within 15 m (of fixes) | "
                   f"Within 15 m (of all) | Wrong > {wrong_m:g} m (of fixes) | Floor: prior median [m] | "
                   f"Floor: random median [m] |")
        out.append("|---|---|---|---|---|---|---|---|---|---|---|")
        for r in rows:
            out.append(f"| {r['method']} | {r['role']} | {r['n_fix']} | {r['acceptance']:.3f} | {r['median_m']} | "
                       f"{r['p95_m']} | {r['within_15m_of_fixes']:.3f} | {r['within_15m_rate']:.3f} | "
                       f"{r[f'wrong_over_{wrong_m:g}m_of_fixes']:.3f} | {r['floor_prior_median_m']} | "
                       f"{r['floor_random_median_m']} |")
        out.append("\nMedian and p95 are over accepted frames (fixes) only.")
        out.append(f"\n{LABEL_NOTE}\n")
    return "\n".join(out)


def plot_cdf(rows: list[dict], split: str, flight: str, out: Path) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    by_method: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r["split"] == split and r["flight"] == flight:
            by_method[r["method"]].append(r)
    fig, ax = plt.subplots(figsize=(7, 4.2), dpi=130)
    ax.axvspan(0, LABEL_FLOOR_M, color="#000000", alpha=0.06, lw=0)
    ax.text(LABEL_FLOOR_M * 0.5, 0.97, "< 15 m: within\nlabel registration\nerror", ha="center", va="top",
            fontsize=7, color="#555555")
    xmax = 1.0
    for k, m in enumerate(method_order(by_method)):
        v = by_method[m]
        errs = np.sort([float(r["err_m"]) for r in v if r["status"] == "fix"])
        n = len(v)  # no-fix frames count as never reaching any error level
        if errs.size:
            y = np.arange(1, errs.size + 1) / n
            ax.step(np.r_[0, errs], np.r_[0, y], where="post", lw=2, color=COLOURS[k % len(COLOURS)],
                    ls="--" if m in BASELINES else "-",
                    label=f"{m}{' (floor)' if m in BASELINES else ''}, fixes {errs.size}/{n}")
            xmax = max(xmax, float(errs[-1]))
    ax.set_xlim(0, xmax * 1.02)
    ax.set_ylim(0, 1)
    ax.set_xlabel("position error against dataset label [m]")
    ax.set_ylabel("fraction of frames")
    ax.set_title(f"Flight {flight} ({split}): error CDF, no-fix frames never reach 1", fontsize=10)
    ax.grid(color="#e6e6e6", lw=0.8)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    fig.tight_layout()
    path = out / f"cdf_{flight}.png"
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    return path


def write_report(results: Path, wrong_m: float = 50.0, plot: bool = True, coverage: float | None = 0.9) -> dict:
    rows = read_frames(results)
    if not rows:
        raise FileNotFoundError(f"no frames_*.csv in {results}")
    tables = flight_tables(rows, wrong_m, coverage)
    flat = [r for t in tables.values() for r in t]
    with (results / "summary.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(flat[0]))
        w.writeheader()
        w.writerows(flat)
    md = markdown(tables, wrong_m)
    (results / "summary.md").write_text(md + "\n")
    print(md)
    if plot:
        for split, flight in sorted({(k[0], k[1]) for k in tables}):
            print(f"wrote {plot_cdf(rows, split, flight, results)}")
    print(f"wrote {results / 'summary.csv'} and {results / 'summary.md'}")
    return tables


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("results", type=Path)
    ap.add_argument("--wrong-m", type=float, default=50.0, help="error above which a fix counts as wrong")
    ap.add_argument("--coverage", type=float, default=0.9, help="map imagery fraction splitting the subsets")
    ap.add_argument("--no-plot", action="store_true")
    args = ap.parse_args()
    write_report(args.results, args.wrong_m, not args.no_plot, args.coverage)
    return 0


if __name__ == "__main__":
    sys.exit(main())
