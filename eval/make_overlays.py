#!/usr/bin/env python3
"""Save overlay images that show where each aerial image's footprint lands on the map.

For each chosen image (--per-flight per flight, or --count FLIGHT=N, evenly spread along the flight, across every
split) one PNG with
three panels at the same ground scale:
  1. the aerial image as stored (north-up; the dataset's images are already rotated, see docs/log.md),
  2. the map cropped to the image's footprint (north-up square of side footprint_m, centred on the
     true position),
  3. context: map of 3 x footprint around the true position, the aerial image blended in at 50 %
     inside the red footprint square, a cross at the true position, and the loader's prior position
     (blue dot) with its 1-sigma circle.
The footprint side per flight is the ground size of that flight's satellite chips: the dataset authors sized
each flight's chips to the aerial image footprint (checked where the consecutive-image estimate in
eval/results/week3/uav_scale.csv works: flight 18 39.0 m vs chip 38.8 m; flight 05 ~190 m, noisy, vs ~180 m).
That estimate, when present, is printed next to it as a cross-check.
Overlays contain dataset imagery: they are written to eval/results/week3/overlays/ (git-ignored).
An index without imagery, overlay_index.csv, is written next to them and to eval/results/week3/.

Usage: python3 eval/make_overlays.py [--root ~/data/visloc/flights] [--splits eval/splits.json]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src/trn_matcher"))
from trn_matcher.loader import LoaderConfig, VisLocDataset  # noqa: E402

PANEL = 400  # pixels per panel side
RED, BLUE, WHITE = (230, 30, 30), (40, 90, 255), (255, 255, 255)


def footprints(scale_csv: Path) -> dict[str, tuple[float, str]]:
    out = {}
    if scale_csv.exists():
        for r in csv.DictReader(scale_csv.open()):
            if r.get("footprint_m_median"):
                out[r["flight"]] = (float(r["footprint_m_median"]), "consecutive-image scale estimate")
    return out


def chip_ground_size(ds: VisLocDataset, region: str, flight: str) -> float:
    return next(st for st in ds.regions[region].stores if st.name == flight).chip_ground_size_m()


def overlay(ds: VisLocDataset, i: int, foot_m: float, foot_src: str, split: str) -> tuple[Image.Image, dict]:
    region, rec = ds.records[i]
    reg = ds.regions[region]
    true, prior = ds.true_position(i), ds.prior_position(i)
    uav = Image.fromarray(ds.load_image(i)).resize((PANEL, PANEL), Image.BILINEAR)
    crop = reg.map_patch(true, foot_m, PANEL)
    ctx_m = 3 * foot_m
    ctx = reg.map_patch(true, ctx_m, PANEL)
    ctx_img = Image.fromarray(ctx.image)
    m_per_px = ctx_m / PANEL

    def to_px(en):  # east/north [m] -> context-panel pixel (x right, y down)
        return (PANEL / 2 + (en[0] - true[0]) / m_per_px, PANEL / 2 - (en[1] - true[1]) / m_per_px)

    side = foot_m / m_per_px
    x0 = round(PANEL / 2 - side / 2)
    small = uav.resize((round(side), round(side)), Image.BILINEAR)
    region_box = (x0, x0, x0 + small.width, x0 + small.height)
    blended = Image.blend(ctx_img.crop(region_box), small, 0.5)
    ctx_img.paste(blended, region_box[:2])
    d = ImageDraw.Draw(ctx_img)
    d.rectangle(region_box, outline=RED, width=2)
    cx, cy = to_px(true)
    d.line([(cx - 8, cy), (cx + 8, cy)], fill=RED, width=2)
    d.line([(cx, cy - 8), (cx, cy + 8)], fill=RED, width=2)
    px_, py_ = to_px(prior)
    r_sig = ds.config.prior_sigma_m / m_per_px
    d.ellipse([px_ - r_sig, py_ - r_sig, px_ + r_sig, py_ + r_sig], outline=BLUE, width=2)
    d.ellipse([px_ - 4, py_ - 4, px_ + 4, py_ + 4], fill=BLUE)

    canvas = Image.new("RGB", (3 * PANEL + 40, PANEL + 70), WHITE)
    for k, im in enumerate((uav, Image.fromarray(crop.image), ctx_img)):
        canvas.paste(im, (10 + k * (PANEL + 10), 10))
    t = ImageDraw.Draw(canvas)
    t.text((10, PANEL + 14), f"flight {rec.flight} {rec.filename} | region {region} ({split}) | lat {rec.lat:.6f} "
           f"lon {rec.lon:.6f} | ENU E {true[0]:.1f} N {true[1]:.1f} m | height {rec.height_m:.0f} m | heading "
           f"{rec.heading_deg:.0f} deg ({rec.heading_source}), not applied: images stored north-up", fill=(0, 0, 0))
    t.text((10, PANEL + 30), f"1: aerial image | 2: map, footprint {foot_m:.0f} m square, north-up ({foot_src}) | "
           f"3: map {ctx_m:.0f} m, image blended 50 % in red square, + true position, blue prior "
           f"(sigma {ds.config.prior_sigma_m:.0f} m, error {np.linalg.norm(prior - true):.0f} m)", fill=(0, 0, 0))
    t.text((10, PANEL + 46), "UAV-VisLoc (Zenodo 19603534), map imagery Google Earth; academic use only, "
           "not for redistribution", fill=(90, 90, 90))
    info = {"flight": rec.flight, "image": rec.filename, "region": region, "split": split,
            "lat": rec.lat, "lon": rec.lon, "east_m": round(float(true[0]), 2), "north_m": round(float(true[1]), 2),
            "footprint_m": round(foot_m, 1), "footprint_source": foot_src, "map_source": crop.source_map,
            "map_valid_fraction": round(float(crop.valid.mean()), 3),
            "prior_error_m": round(float(np.linalg.norm(prior - true)), 1)}
    return canvas, info


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=Path.home() / "data/visloc/flights")
    ap.add_argument("--splits", type=Path, default=Path(__file__).parent / "splits.json")
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "results/week3")
    ap.add_argument("--per-flight", type=int, default=2)
    ap.add_argument("--count", action="append", default=[],
                    help="FLIGHT=N overlays for one flight (overrides --per-flight), e.g. --count 10=4")
    ap.add_argument("--split", action="append", help="only these splits (default: all)")
    args = ap.parse_args()
    splits = json.loads(args.splits.read_text())
    counts = {k: int(v) for k, v in (c.split("=") for c in args.count)}
    foot = footprints(args.out / "uav_scale.csv")
    (args.out / "overlays").mkdir(parents=True, exist_ok=True)
    rows = []
    for split in args.split or list(splits["splits"]):
        ds = VisLocDataset(args.root, splits, split, LoaderConfig(image_px=1024))
        for region in splits["splits"][split]:
            for flight in splits["regions"][region]["flights"]:
                idx = [k for k, (_, r) in enumerate(ds.records) if r.flight == flight]
                n = counts.get(flight, args.per_flight)
                picks = [idx[int(len(idx) * (j + 1) / (n + 1))] for j in range(n)]  # evenly spread
                f_m = chip_ground_size(ds, region, flight)
                est = foot.get(flight)
                src = "chip ground size" + (f"; image-pair estimate {est[0]:.0f} m" if est else
                                            "; no image-pair estimate")
                for i in picks:
                    img, info = overlay(ds, i, f_m, src, split)
                    name = f"overlay_{info['flight']}_{Path(info['image']).stem}.png"
                    img.save(args.out / "overlays" / name)
                    rows.append({"file": f"overlays/{name}", **info})
                    print(f"{name}: footprint {f_m:.0f} m, map valid {info['map_valid_fraction']:.2f}", flush=True)
    for path in (args.out / "overlay_index.csv",):
        with path.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    print(f"wrote {len(rows)} overlays to {args.out / 'overlays'} and {args.out / 'overlay_index.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
