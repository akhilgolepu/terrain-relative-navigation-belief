#!/usr/bin/env python3
"""Breakdown of matcher runs on the tune split, for comparing settings and reading failures.

For each frames_<method>.csv given: fixes, share of fixes within 15 / 30 / 50 m of the label,
median error; error by ratio quantile; rotation and scale distribution (share at the search edge,
share with |rotation| > 5 deg, p5-p95 of rotation for fixes within 50 m); blank-patch split
(map_valid_frac < 0.9); and, for rejected frames, how many had a best candidate within 50 m and
the median ratio of each group. Refuses the test split. Prints a text report.

Usage: python3 eval/tune_breakdown.py RUN_DIR/frames_ncc.csv [...] > breakdown.txt
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np


def report(path: Path) -> list[str]:
    rows = list(csv.DictReader(path.open()))
    if any(r["split"] == "test" for r in rows):
        return [f"{path}: refusing the test split"]
    fx = [(r, json.loads(r["diag"]) if r["diag"] else {}) for r in rows if r["status"] == "fix"]
    out = [f"== {path.parent.name}/{path.name}: {len(fx)}/{len(rows)} fixes"]
    if not fx:
        return out
    err = np.array([float(r["err_m"]) for r, _ in fx])
    out.append(f"  of fixes: within 15 m {np.mean(err <= 15):.3f}, 30 m {np.mean(err <= 30):.3f}, "
               f"50 m {np.mean(err <= 50):.3f}; median {np.median(err):.1f} m")
    ratio = np.array([d.get("ratio", np.nan) for _, d in fx])
    for q in (50, 75, 90):
        t = np.nanpercentile(ratio, q)
        m = ratio >= t
        out.append(f"  ratio >= p{q} ({t:.3f}): n={m.sum()} median {np.median(err[m]):.1f} m, "
                   f"within 50 m {np.mean(err[m] <= 50):.2f}")
    rot = np.array([d.get("rot_deg", np.nan) for _, d in fx])
    scale = np.array([d.get("scale", np.nan) for _, d in fx])
    good = err <= 50
    out.append(f"  rotation: |rot| > 5 deg {np.mean(np.abs(rot) > 5):.2f}; at rotation edge "
               f"{np.mean([d.get('at_rot_edge', False) for _, d in fx]):.2f}; at scale edge "
               f"{np.mean([d.get('at_scale_edge', False) for _, d in fx]):.2f}")
    if good.any():
        out.append(f"  fixes within 50 m (n={good.sum()}): rotation p5/p50/p95 "
                   f"{np.round(np.percentile(rot[good], [5, 50, 95]), 1).tolist()}, scale p10/p50/p90 "
                   f"{np.round(np.percentile(scale[good], [10, 50, 90]), 3).tolist()}")
    cov = {r["image"]: float(r["map_valid_frac"]) for r in rows}
    blank = np.array([cov[r["image"]] < 0.9 for r, _ in fx])
    nb = sum(v < 0.9 for v in cov.values())
    out.append(f"  blank-patch frames (< 90 % imagery): {nb}; fixes {blank.sum()}"
               + (f", median {np.median(err[blank]):.1f} m" if blank.any() else ""))
    rej = [(r, json.loads(r["diag"]) if r["diag"] else {}) for r in rows if r["status"] != "fix"]
    near, far = [], []
    for r, d in rej:
        if "cand_east" not in d:
            continue
        e = np.hypot(d["cand_east"] - float(r["true_e"]), d["cand_north"] - float(r["true_n"]))
        (near if e <= 50 else far).append(d.get("ratio", np.nan))
    if near or far:
        out.append(f"  rejected: {len(rej)}; candidate within 50 m: {len(near)} (median ratio "
                   f"{np.nanmedian(near) if near else float('nan'):.3f}), beyond: {len(far)} (median ratio "
                   f"{np.nanmedian(far) if far else float('nan'):.3f})")
    return out


def main() -> int:
    for p in sys.argv[1:]:
        print("\n".join(report(Path(p))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
