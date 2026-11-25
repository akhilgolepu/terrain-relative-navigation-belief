#!/usr/bin/env python3
"""Week 5: per-frame calibration features from a frozen-matcher run, and their shift between flights.

Input: frames_ncc.csv of the FROZEN matcher (diag must contain topk: runs from commit 1c60560 on;
for flight 10 use eval/results/week4/tune_regression, identical to the frozen tune run).
Every frame whose fine search produced a candidate is kept, accepted or rejected by the frozen
gate. fix = the accepted fix, or the best rejected candidate (cand_east/north); error e = fix - label
(metres, region ENU). wrong = |e| > 50 m.

Features (all available at run time; no label, height or heading used):
  log_ratio    log of the z ratio (best / second best >= 1/4 footprint away)
  peak         NCC of the best candidate
  peak_z_norm  Fisher z / sqrt(template pixels at the coarse level), ~ atanh(peak) x overlap^0.5
  rel_gap      (z1 - z2) / z1 for the top-2 distinct (> 20 m) candidates
  overlap      fraction of the image footprint on map imagery at the answer
  edge_fp      signed distance from the PRIOR to the edge of the map, in footprints (> 0 inside)
  at_bound     1 if the coarse answer is at the edge of the scale or rotation range
  alt_dist_fp  distance between the top-2 candidates, in footprints
  map_valid    fraction of the map patch with imagery
Writes RESULTS/features_<flight>.csv; with two inputs also RESULTS/feature_shift.md.
Refuses the test split.

Usage: /usr/bin/python3 eval/calib_features.py RUN/frames_ncc.csv [RUN2/frames_ncc.csv] [--out eval/results/week5]
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src/trn_matcher"))
import envcheck  # noqa: E402
from trn_matcher.loader import LoaderConfig, VisLocDataset  # noqa: E402

FEATURES = ["log_ratio", "peak", "peak_z_norm", "rel_gap", "overlap", "edge_fp", "at_bound", "alt_dist_fp",
            "map_valid"]
WRONG_M = 50.0


def edge_distance_m(store, frame, east: float, north: float) -> float:
    """Signed distance [m] from a point to the edge of the store's chip-covered map (> 0 inside)."""
    lat, lon, _ = frame.to_geodetic(east, north)
    row, col = store.georef.latlon_to_pixel(lat, lon)
    g = store.georef
    lat_mid = g.lat0 + g.dlat_drow * store.height_px / 2
    m_row = abs(g.dlat_drow) * 111_320.0
    m_col = abs(g.dlon_dcol) * 111_320.0 * math.cos(math.radians(lat_mid))
    inside = min(float(row) * m_row, (store.height_px - float(row)) * m_row,
                 float(col) * m_col, (store.width_px - float(col)) * m_col)
    return inside


def build(path: Path, root: Path, splits: dict) -> list[dict]:
    rows = list(csv.DictReader(path.open()))
    split = rows[0]["split"]
    if split == "test":
        raise SystemExit("refusing the test split")
    ds = VisLocDataset(root, splits, split, LoaderConfig())
    out = []
    for r in rows:
        d = json.loads(r["diag"]) if r["diag"] else {}
        if "cand_east" not in d or "topk" not in d:
            continue
        region = r["region"]
        reg = ds.regions[region]
        store = next(s for s in reg.stores if s.name == r["flight"])
        fix = (np.array([float(r["est_e"]), float(r["est_n"])]) if r["status"] == "fix"
               else np.array([d["cand_east"], d["cand_north"]]))
        true = np.array([float(r["true_e"]), float(r["true_n"])])
        e = fix - true
        foot = float(r["footprint_m"])
        top = d["topk"]
        z1 = top[0]["z"]
        z2 = top[1]["z"] if len(top) > 1 else 0.0
        alt = (math.hypot(top[1]["east"] - top[0]["east"], top[1]["north"] - top[0]["north"]) / foot
               if len(top) > 1 else 0.0)
        n_pix = (foot / d["coarse_m_per_px"]) ** 2
        out.append({
            "split": split, "flight": r["flight"], "image": r["image"], "frame": int(r["image"].split("_")[1][:4]),
            "accepted": int(r["status"] == "fix"), "e_e": round(float(e[0]), 3), "e_n": round(float(e[1]), 3),
            "err_m": round(float(np.hypot(*e)), 3), "wrong": int(np.hypot(*e) > WRONG_M),
            "log_ratio": round(math.log(max(d["ratio"], 1e-3)), 5), "peak": d["peak"],
            "peak_z_norm": round(d["peak_z"] / math.sqrt(n_pix), 5),
            "rel_gap": round((z1 - z2) / z1 if z1 > 0 else 0.0, 5), "overlap": d["overlap_valid_frac"],
            "edge_fp": round(edge_distance_m(store, reg.frame, float(r["prior_e"]), float(r["prior_n"])) / foot, 4),
            "at_bound": int(bool(d.get("at_scale_edge")) or bool(d.get("at_rot_edge"))),
            "alt_dist_fp": round(alt, 4), "map_valid": float(r["map_valid_frac"]),
            "footprint_m": foot, "ratio": d["ratio"]})
    return out


def shift_table(a: list[dict], b: list[dict]) -> str:
    fa, fb = a[0]["flight"], b[0]["flight"]
    lines = [f"Feature shift between flight {fa} (fit) and flight {fb} (check). Medians [p25, p75]; "
             f"KS = two-sample Kolmogorov-Smirnov statistic (0 = same distribution, 1 = disjoint); "
             f"shift = (median {fb} - median {fa}) / IQR {fa}. 'right' = frames with |e| <= {WRONG_M:g} m.",
             "", f"| Feature | {fa} all | {fb} all | KS all | shift all | {fa} right | {fb} right | KS right | "
             f"shift right |", "|---|---|---|---|---|---|---|---|---|"]

    def q(v):
        return f"{np.median(v):.3g} [{np.percentile(v, 25):.3g}, {np.percentile(v, 75):.3g}]"

    for f in FEATURES:
        cells = []
        for subset in ("all", "right"):
            va = np.array([x[f] for x in a if subset == "all" or not x["wrong"]], float)
            vb = np.array([x[f] for x in b if subset == "all" or not x["wrong"]], float)
            iqr = np.percentile(va, 75) - np.percentile(va, 25)
            sh = (np.median(vb) - np.median(va)) / iqr if iqr > 0 else float("nan")
            ks = stats.ks_2samp(va, vb).statistic
            cells += [q(va), q(vb), f"{ks:.2f}", f"{sh:+.2f}"]
        lines.append(f"| {f} | " + " | ".join(cells) + " |")
    na, nb = len(a), len(b)
    wa, wb = sum(x["wrong"] for x in a), sum(x["wrong"] for x in b)
    lines += ["", f"Frames with a candidate: {fa} {na} ({wa} wrong, {wa / na:.1%}); {fb} {nb} ({wb} wrong, "
              f"{wb / nb:.1%}). Errors are against dataset labels, so reported uncertainty includes label "
              "registration error and is not uncertainty about the true position."]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("frames", type=Path, nargs="+")
    ap.add_argument("--root", type=Path, default=Path.home() / "data/visloc/flights")
    ap.add_argument("--splits", type=Path, default=Path(__file__).parent / "splits.json")
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "results/week5")
    args = ap.parse_args()
    envcheck.require_reference_env()
    args.out.mkdir(parents=True, exist_ok=True)
    splits = json.loads(args.splits.read_text())
    sets = []
    for path in args.frames:
        feats = build(path, args.root, splits)
        flight = feats[0]["flight"]
        with (args.out / f"features_{flight}.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(feats[0]))
            w.writeheader()
            w.writerows(feats)
        print(f"flight {flight}: {len(feats)} frames with a candidate -> {args.out / f'features_{flight}.csv'}")
        sets.append(feats)
    if len(sets) == 2:
        md = shift_table(*sets)
        (args.out / "feature_shift.md").write_text(md)
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
