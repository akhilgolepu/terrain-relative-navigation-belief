#!/usr/bin/env python3
"""Diagnostic: matcher label offset and rotation residual split by flight direction.

DIAGNOSTIC ONLY (never applied to scores, labels or matcher output). For the matcher's fixes
within --max-err-m of the label, grouped by the dataset heading (Phi2, degrees clockwise from
north) into 90-degree bins, it reports the median label offset east/north (estimate - label)
with its median absolute deviation, the median rotation the matcher found, and the median of
the dataset's Phi1 - Phi2 (the two angle columns disagree; documented as undocumented).
Heading is read from the flight's UAV-coordinates.csv; height is not used.
Refuses the test split.

Usage: python3 eval/diag_by_heading.py RESULTS/frames_ncc.csv [--max-err-m 50]
  Writes heading_diag_<method>.csv next to the input.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np


def mad(x: np.ndarray) -> float:
    return float(np.median(np.abs(x - np.median(x))))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("frames", type=Path)
    ap.add_argument("--max-err-m", type=float, default=50.0)
    ap.add_argument("--root", type=Path, default=Path.home() / "data/visloc/flights")
    args = ap.parse_args()
    rows = list(csv.DictReader(args.frames.open()))
    if any(r["split"] == "test" for r in rows):
        print("refusing: no diagnostics on the test split")
        return 2
    angles = {}
    for flight in sorted({r["flight"] for r in rows}):
        with (args.root / flight / f"{flight}-UAV-coordinates.csv").open(encoding="utf-8-sig") as fh:
            for a in csv.DictReader(fh):
                angles[(flight, a["filename"])] = (float(a["Phi2"]) % 360, float(a["Phi1"]) % 360)
    groups: dict[tuple, list] = defaultdict(list)
    for r in rows:
        if r["status"] != "fix" or float(r["err_m"]) > args.max_err_m:
            continue
        phi2, phi1 = angles[(r["flight"], r["image"])]
        d = json.loads(r["diag"]) if r["diag"] else {}
        diff = (phi1 - phi2 + 180) % 360 - 180
        groups[(r["flight"], int(phi2 // 90) * 90)].append(
            (float(r["err_e"]), float(r["err_n"]), d.get("rot_deg", np.nan), diff, phi2))
    out = []
    for (flight, lo), v in sorted(groups.items()):
        a = np.array(v, float)
        out.append({"flight": flight, "heading_bin_deg": f"{lo}-{lo + 90}", "n": len(v),
                    "median_heading_deg": round(float(np.median(a[:, 4])), 1),
                    "offset_e_m": round(float(np.median(a[:, 0])), 1), "mad_e_m": round(mad(a[:, 0]), 1),
                    "offset_n_m": round(float(np.median(a[:, 1])), 1), "mad_n_m": round(mad(a[:, 1]), 1),
                    "matcher_rot_deg": round(float(np.nanmedian(a[:, 2])), 1),
                    "phi1_minus_phi2_deg": round(float(np.median(a[:, 3])), 1),
                    "note": "diagnostic only; never applied"})
    method = args.frames.stem.removeprefix("frames_")
    path = args.frames.parent / f"heading_diag_{method}.csv"
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    for o in out:
        print(f"flight {o['flight']} heading {o['heading_bin_deg']} (median {o['median_heading_deg']}), n={o['n']}: "
              f"offset east {o['offset_e_m']:+.1f} (MAD {o['mad_e_m']}) north {o['offset_n_m']:+.1f} "
              f"(MAD {o['mad_n_m']}) m; matcher rotation {o['matcher_rot_deg']:+.1f} deg; "
              f"Phi1 - Phi2 {o['phi1_minus_phi2_deg']:+.1f} deg")
    print(f"diagnostic only; wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
