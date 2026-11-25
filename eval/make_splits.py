#!/usr/bin/env python3
"""Write eval/splits.json: whole UAV-VisLoc regions per split, with each region's ENU origin.

Regions (chosen 2026-11-18 for terrain variety within the 5 GB download limit; terrain and modality
checked against the images, see docs/log.md):
  hebei_huailai flight 10           plains / farmland, RGB     -> tune     (tune the week 4 matcher)
  yunnan        flight 05           mountainous plateau, RGB   -> calibrate (fit the week 5 calibration)
  gansu         flight 11           arid, RGB                  -> test     (final test, kept untouched)
Excluded (on disk, in no split): jiangsu_wuxi, flights 18, 19, 20: thermal infrared, reserved as a
cross-modal stress test. Their modality was found from the overlays; the dataset metadata does not say it.
Each region's ENU origin is the centre of the bounding box of its satellite-chip centres (from the
coordinate CSVs in INDEX, default ~/data/visloc/index), rounded to 1e-5 degrees, so it does not
depend on any UAV position.

Usage: python3 eval/make_splits.py [--index ~/data/visloc/index] [--out eval/splits.json]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REGIONS = {
    "hebei_huailai": {"flights": ["10"], "terrain": "plains / farmland", "modality": "RGB",
                      "place": "Huailai-Yanqing area north-west of Beijing, China"},
    "yunnan": {"flights": ["05"], "terrain": "mountainous plateau", "modality": "RGB",
               "place": "central Yunnan, China"},
    "gansu": {"flights": ["11"], "terrain": "arid", "modality": "RGB",
              "place": "Zhangye area, Gansu, China"},
}
EXCLUDED = {
    "jiangsu_wuxi": {"flights": ["18", "19", "20"], "modality": "thermal infrared",
                     "place": "Jiangyin-Wuxi area, Jiangsu, China",
                     "status": "excluded from tune/calibrate/test, reserved as a cross-modal stress test",
                     "note": "modality found from the overlays (2026-11-18); the dataset metadata does not say it"},
}
SPLITS = {"tune": ["hebei_huailai"], "calibrate": ["yunnan"], "test": ["gansu"]}
PURPOSE = {"tune": "tune the week 4 matcher", "calibrate": "fit the week 5 calibration",
           "test": "final test only; do not look at it while tuning or calibrating"}


def chip_centres(index: Path, flight: str) -> tuple[list[float], list[float]]:
    with (index / flight / f"{flight}-satellite-tile-coordinates.csv").open(encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    return [float(r["latitude"]) for r in rows], [float(r["longitude"]) for r in rows]


def build(index: Path) -> dict:
    regions = {}
    for name, info in REGIONS.items():
        lats, lons = [], []
        for f in info["flights"]:
            la, lo = chip_centres(index, f)
            lats += la
            lons += lo
        regions[name] = {**info, "enu_origin": {"lat": round((min(lats) + max(lats)) / 2, 5),
                                                "lon": round((min(lons) + max(lons)) / 2, 5)},
                         "chip_centre_bbox": {"lat_min": min(lats), "lat_max": max(lats),
                                              "lon_min": min(lons), "lon_max": max(lons)}}
    return {"dataset": "UAV-VisLoc, Zenodo record 19603534 (academic use only, no redistribution)",
            "rule": "whole regions per split; every flight in exactly one region; no flight in two splits",
            "frames": "positions in metres, east/north in each region's local ENU frame tangent to WGS84 at "
                      "enu_origin (degrees, WGS84)",
            "purpose": PURPOSE, "regions": regions, "splits": SPLITS, "excluded_regions": EXCLUDED}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--index", type=Path, default=Path.home() / "data/visloc/index")
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "splits.json")
    args = ap.parse_args()
    args.out.write_text(json.dumps(build(args.index), indent=2) + "\n")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
