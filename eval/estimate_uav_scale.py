#!/usr/bin/env python3
"""Estimate each flight's UAV image scale (metres per pixel) and orientation from consecutive images.

UAV-VisLoc gives no camera model and the images carry no EXIF, so the ground footprint of an image
is unknown. Consecutive images overlap; the shift between them in pixels (phase correlation of the
two grayscale images, no map involved) and the GPS displacement between them in metres give:
  - scale: metres per pixel = |GPS displacement| / |pixel shift|
  - orientation: the angle between the expected image motion of a north-up image (scene moves
    opposite to the camera: east motion -> content moves left, north motion -> content moves down)
    and the measured motion. About 0 deg means the stored images are north-up.
Pairs with a weak correlation peak (peak-to-mean ratio below --min-peak) or a GPS displacement
under --min-move-m are skipped. Reports median and spread over the pairs used.

Writes RESULTS/uav_scale.csv (one row per flight) and RESULTS/uav_scale_pairs.csv (one row per pair).
Usage (system python3 or venv): python3 eval/estimate_uav_scale.py ~/data/visloc/flights 05 18 19 20 11
       [--out eval/results/week3] [--pairs 60] [--work-px 512]
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src/trn_matcher"))
from trn_matcher.geo import LocalENU  # noqa: E402
from trn_matcher.loader import read_uav_records  # noqa: E402


def gray(path: Path, work_px: int) -> tuple[np.ndarray, float]:
    """Grayscale image resized to work_px on its long side; returns it and the resize factor."""
    with Image.open(path) as im:
        s = work_px / max(im.size)
        g = im.convert("L").resize((round(im.width * s), round(im.height * s)), Image.BILINEAR)
    return np.asarray(g, np.float32), s


def phase_correlation(a: np.ndarray, b: np.ndarray) -> tuple[float, float, float]:
    """Shift (dx, dy) in pixels that moves image a onto image b, and the peak-to-mean ratio."""
    h, w = a.shape
    win = np.outer(np.hanning(h), np.hanning(w)).astype(np.float32)
    fa, fb = np.fft.fft2((a - a.mean()) * win), np.fft.fft2((b - b.mean()) * win)
    r = fb * np.conj(fa)
    r /= np.abs(r) + 1e-9
    c = np.real(np.fft.ifft2(r))
    iy, ix = np.unravel_index(np.argmax(c), c.shape)
    peak = float(c[iy, ix] / (np.abs(c).mean() + 1e-12))

    def sub(v_minus, v0, v_plus):  # parabolic sub-pixel refinement
        den = v_minus - 2 * v0 + v_plus
        return 0.0 if den == 0 else 0.5 * (v_minus - v_plus) / den
    dy = iy + sub(c[iy - 1, ix], c[iy, ix], c[(iy + 1) % h, ix])
    dx = ix + sub(c[iy, ix - 1], c[iy, ix], c[iy, (ix + 1) % w])
    dy = dy - h if dy > h / 2 else dy
    dx = dx - w if dx > w / 2 else dx
    return float(dx), float(dy), peak


def flight_pairs(flight_dir: Path, n_pairs: int, work_px: int, min_move_m: float,
                 min_peak: float) -> list[dict]:
    recs = read_uav_records(flight_dir)
    frame = LocalENU(recs[0].lat, recs[0].lon)
    idx = np.unique(np.linspace(0, len(recs) - 2, n_pairs).astype(int))
    out = []
    for i in idx:
        r1, r2 = recs[i], recs[i + 1]
        e, n, _ = frame.to_enu(np.array([r1.lat, r2.lat]), np.array([r1.lon, r2.lon]))
        de, dn = float(e[1] - e[0]), float(n[1] - n[0])
        move = math.hypot(de, dn)
        row = {"flight": flight_dir.name, "image1": r1.filename, "image2": r2.filename,
               "gps_move_m": round(move, 3)}
        if move < min_move_m:
            out.append({**row, "used": 0, "why": "GPS move too small"})
            continue
        a, s = gray(r1.path, work_px)
        b, _ = gray(r2.path, work_px)
        if a.shape != b.shape:
            out.append({**row, "used": 0, "why": "image sizes differ"})
            continue
        dx, dy, peak = phase_correlation(a, b)
        shift_px = math.hypot(dx, dy) / s  # in full-resolution pixels
        # expected content motion for a north-up image: (-east, +north) in (x right, y down)
        ang_exp = math.atan2(dn, -de)
        ang_meas = math.atan2(dy, dx)
        rot = (math.degrees(ang_meas - ang_exp) + 180) % 360 - 180
        ok = peak >= min_peak and shift_px > 1
        out.append({**row, "used": int(ok), "why": "" if ok else "weak correlation peak",
                    "shift_px": round(shift_px, 2), "peak_to_mean": round(peak, 1),
                    "m_per_px": round(move / shift_px, 5) if shift_px > 0 else "",
                    "rotation_deg": round(rot, 2), "heading_deg": round(r1.heading_deg, 2)})
    return out


def summarise(flight: str, pairs: list[dict], image_px: int) -> dict:
    used = [p for p in pairs if p.get("used")]
    if not used:
        return {"flight": flight, "pairs_used": 0, "pairs_tried": len(pairs)}
    mpp = np.array([p["m_per_px"] for p in used], float)
    rot = np.array([p["rotation_deg"] for p in used], float)
    med = float(np.median(mpp))
    return {"flight": flight, "pairs_used": len(used), "pairs_tried": len(pairs), "image_px": image_px,
            "m_per_px_median": round(med, 5), "m_per_px_p10": round(float(np.percentile(mpp, 10)), 5),
            "m_per_px_p90": round(float(np.percentile(mpp, 90)), 5),
            "footprint_m_median": round(med * image_px, 1),
            "rotation_deg_median": round(float(np.median(rot)), 2),
            "rotation_deg_p10": round(float(np.percentile(rot, 10)), 2),
            "rotation_deg_p90": round(float(np.percentile(rot, 90)), 2)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("root", type=Path)
    ap.add_argument("flights", nargs="+")
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "results/week3")
    ap.add_argument("--pairs", type=int, default=60)
    ap.add_argument("--work-px", type=int, default=512)
    ap.add_argument("--min-move-m", type=float, default=5.0)
    ap.add_argument("--min-peak", type=float, default=20.0)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    all_pairs, summary = [], []
    for f in args.flights:
        pairs = flight_pairs(args.root / f, args.pairs, args.work_px, args.min_move_m, args.min_peak)
        with Image.open(read_uav_records(args.root / f)[0].path) as im:
            image_px = max(im.size)
        summary.append(summarise(f, pairs, image_px))
        all_pairs += pairs
        print(summary[-1], flush=True)
    for name, rows in (("uav_scale.csv", summary), ("uav_scale_pairs.csv", all_pairs)):
        keys = list(dict.fromkeys(k for r in rows for k in r))
        with (args.out / name).open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)
    print(f"wrote {args.out / 'uav_scale.csv'} and {args.out / 'uav_scale_pairs.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
