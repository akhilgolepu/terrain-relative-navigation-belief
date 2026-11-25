#!/usr/bin/env python3
"""Estimate how far each overlay's aerial image is shifted against the map, from landmarks picked by eye.

Two steps:
  grid     For each overlay PNG (from make_overlays.py), draw panel 1 (aerial image) and panel 2 (map cropped to
           the footprint, centred on the true position) side by side with a labelled 50 px grid, so the pixel
           position of the same landmark (road junction, building corner, field corner) can be read in both.
           Writes RESULTS/overlays/grid_<overlay>.png (git-ignored: contains imagery).
  compute  Read RESULTS/overlay_landmarks.csv (columns: overlay, landmark, uav_x, uav_y, map_x, map_y; panel pixels,
           0..400, x right, y down; picked by eye; optional quality and note columns; a row with empty coordinates
           records an overlay where no landmark could be matched) and RESULTS/overlay_index.csv (footprint per
           overlay), and write RESULTS/overlay_offsets.csv: per landmark, per overlay (mean of its landmarks) and per
           flight (mean over its measured overlays).
Offset meaning: a landmark seen at u in the image and at m on the map crop means the image centre's true ground
position is the dataset position + (m - u) x metres-per-pixel, i.e. east = (map_x - uav_x) * s,
north = -(map_y - uav_y) * s with s = footprint_m / 400. Precision about +-5 px (s x 5 m) per landmark, plus any
mismatch from relief, map date and the footprint-size assumption.

Usage: python3 eval/overlay_offsets.py grid|compute [--out eval/results/week3]
"""
from __future__ import annotations

import argparse
import csv
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw

PANEL = 400  # must match make_overlays.py
GRID = 50


def panel(img: Image.Image, k: int) -> Image.Image:
    x0 = 10 + k * (PANEL + 10)
    return img.crop((x0, 10, x0 + PANEL, 10 + PANEL))


def draw_grid(im: Image.Image) -> Image.Image:
    im = im.convert("RGB").resize((2 * PANEL, 2 * PANEL), Image.BILINEAR)  # x2 for easier reading
    d = ImageDraw.Draw(im)
    for v in range(0, PANEL + 1, GRID):
        c = (255, 255, 0) if v % 100 == 0 else (0, 255, 255)
        d.line([(2 * v, 0), (2 * v, 2 * PANEL)], fill=c, width=1)
        d.line([(0, 2 * v), (2 * PANEL, 2 * v)], fill=c, width=1)
        d.text((2 * v + 2, 2), str(v), fill=c)
        d.text((2, 2 * v + 2), str(v), fill=c)
    return im


def make_grids(out: Path) -> int:
    rows = list(csv.DictReader((out / "overlay_index.csv").open()))
    for r in rows:
        src = out / r["file"]
        with Image.open(src) as img:
            a, b = draw_grid(panel(img, 0)), draw_grid(panel(img, 1))
        canvas = Image.new("RGB", (4 * PANEL + 20, 2 * PANEL + 24), (255, 255, 255))
        canvas.paste(a, (0, 0))
        canvas.paste(b, (2 * PANEL + 20, 0))
        ImageDraw.Draw(canvas).text((4, 2 * PANEL + 6), f"{src.name}: left aerial image, right map crop "
                                    f"(footprint {r['footprint_m']} m); grid labels in panel pixels 0..400",
                                    fill=(0, 0, 0))
        canvas.save(out / "overlays" / f"grid_{src.name}")
    print(f"wrote {len(rows)} grid images to {out / 'overlays'}")
    return 0


def compute(out: Path) -> int:
    foot = {Path(r["file"]).name: (float(r["footprint_m"]), r["flight"])
            for r in csv.DictReader((out / "overlay_index.csv").open())}
    marks = list(csv.DictReader((out / "overlay_landmarks.csv").open()))
    per_overlay: dict[str, list[tuple[float, float]]] = defaultdict(list)
    rows = []
    for m in marks:
        f_m, flight = foot[m["overlay"]]
        if not m["uav_x"].strip():  # overlay with no matchable landmark
            rows.append({"level": "overlay", "flight": flight, "overlay": m["overlay"], "landmark": "none found",
                         "n": 0, "quality": m.get("quality", ""), "note": m.get("note", "")})
            continue
        s = f_m / PANEL
        east = (float(m["map_x"]) - float(m["uav_x"])) * s
        north = -(float(m["map_y"]) - float(m["uav_y"])) * s
        per_overlay[m["overlay"]].append((east, north))
        rows.append({"level": "landmark", "flight": flight, "overlay": m["overlay"], "landmark": m["landmark"],
                     "east_m": round(east, 1), "north_m": round(north, 1),
                     "offset_m": round((east ** 2 + north ** 2) ** 0.5, 1), "n": 1,
                     "quality": m.get("quality", ""), "note": m.get("note", "")})
    per_flight: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for ov, v in per_overlay.items():
        e, n = statistics.fmean(x for x, _ in v), statistics.fmean(y for _, y in v)
        per_flight[foot[ov][1]].append((e, n))
        rows.append({"level": "overlay", "flight": foot[ov][1], "overlay": ov, "landmark": "mean",
                     "east_m": round(e, 1), "north_m": round(n, 1), "offset_m": round((e ** 2 + n ** 2) ** 0.5, 1),
                     "n": len(v), "east_range_m": round(max(x for x, _ in v) - min(x for x, _ in v), 1),
                     "north_range_m": round(max(y for _, y in v) - min(y for _, y in v), 1)})
    for fl, v in sorted(per_flight.items()):
        e, n = statistics.fmean(x for x, _ in v), statistics.fmean(y for _, y in v)
        rows.append({"level": "flight", "flight": fl, "overlay": "", "landmark": "mean of overlays",
                     "east_m": round(e, 1), "north_m": round(n, 1), "offset_m": round((e ** 2 + n ** 2) ** 0.5, 1),
                     "n": len(v), "mean_abs_offset_m": round(statistics.fmean(math.hypot(x, y) for x, y in v), 1),
                     "max_abs_offset_m": round(max(math.hypot(x, y) for x, y in v), 1)})
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with (out / "overlay_offsets.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        if r["level"] != "landmark" and r["n"] == 0:
            print(f"{r['level']:8s} {r['flight']} {r['overlay']:28s} no landmark matched: {r.get('note', '')}")
        elif r["level"] != "landmark":
            print(f"{r['level']:8s} {r['flight']} {r['overlay']:28s} east {r['east_m']:+6.1f} m  north "
                  f"{r['north_m']:+6.1f} m  |offset| {r['offset_m']:5.1f} m  (n={r['n']})"
                  + (f"  mean |offset| {r['mean_abs_offset_m']} m, max {r['max_abs_offset_m']} m"
                     if r["level"] == "flight" else ""))
    print(f"wrote {out / 'overlay_offsets.csv'}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("step", choices=["grid", "compute"])
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "results/week3")
    args = ap.parse_args()
    return make_grids(args.out) if args.step == "grid" else compute(args.out)


if __name__ == "__main__":
    sys.exit(main())
