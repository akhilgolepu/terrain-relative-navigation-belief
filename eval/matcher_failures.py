#!/usr/bin/env python3
"""Overlays of failed matcher frames: what the matcher saw, where the label is, where it answered.

Failures are taken from RESULTS/frames_<method>.csv, --count in total, round-robin over: wrong
fixes (error > --wrong-m, largest first), rejected frames whose best candidate was also wrong,
and rejected frames whose candidate was right but not trusted (both highest peak first).
One PNG per frame with four panels at the same ground scale per row:
  1. the aerial image as stored (north-up),
  2. the map at the LABEL position (footprint square),
  3. the map at the matcher's answer (accepted or best rejected candidate, from diag),
  4. context: the search window around the prior with the label (red +), the prior (blue) and
     the answer (orange x); black = no map imagery.
Overlays contain dataset imagery and are written to RESULTS/failures/ (git-ignored).

Usage: python3 eval/matcher_failures.py eval/results/week4/tune [--method ncc] [--count 6]
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
from trn_matcher.interface import en_to_patch_px  # noqa: E402
from trn_matcher.loader import LoaderConfig, VisLocDataset  # noqa: E402

P = 300
RED, BLUE, ORANGE, WHITE = (230, 30, 30), (40, 90, 255), (255, 150, 0), (255, 255, 255)


def _cand_err(r: dict) -> float:
    d = json.loads(r["diag"]) if r["diag"] else {}
    if "cand_east" not in d:
        return float("inf")
    return float(np.hypot(d["cand_east"] - float(r["true_e"]), d["cand_north"] - float(r["true_n"])))


def pick(rows: list[dict], wrong_m: float, count: int) -> list[dict]:
    """Round-robin over three failure kinds: wrong fixes (largest error first), rejected frames
    whose best candidate was also wrong, rejected frames whose candidate was right (both by
    highest peak first)."""
    peak = lambda r: -(json.loads(r["diag"]).get("peak", -1) if r["diag"] else -1)  # noqa: E731
    wrong = sorted((r for r in rows if r["status"] == "fix" and float(r["err_m"]) > wrong_m),
                   key=lambda r: -float(r["err_m"]))
    rej = [r for r in rows if r["status"] != "fix"]
    rej_far = sorted((r for r in rej if _cand_err(r) > wrong_m), key=peak)
    rej_near = sorted((r for r in rej if _cand_err(r) <= wrong_m), key=peak)
    out = []
    while len(out) < count and (wrong or rej_far or rej_near):
        for q in (wrong, rej_far, rej_near):
            if q and len(out) < count:
                out.append(q.pop(0))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("results", type=Path)
    ap.add_argument("--method", default="ncc")
    ap.add_argument("--count", type=int, default=6)
    ap.add_argument("--wrong-m", type=float, default=50.0)
    ap.add_argument("--root", type=Path, default=Path.home() / "data/visloc/flights")
    ap.add_argument("--splits", type=Path, default=Path(__file__).parent / "splits.json")
    args = ap.parse_args()
    rows = list(csv.DictReader((args.results / f"frames_{args.method}.csv").open()))
    split = rows[0]["split"]
    if split == "test":
        print("refusing: no failure overlays on the test split")
        return 2
    run = json.loads((args.results / f"run_{args.method}.json").read_text())
    window = run["search"]["window_m"]
    ds = VisLocDataset(args.root, json.loads(args.splits.read_text()), split, LoaderConfig(image_px=1024))
    index = {(r.flight, r.filename): k for k, (_, r) in enumerate(ds.records)}
    out = args.results / "failures"
    out.mkdir(exist_ok=True)
    chosen = pick(rows, args.wrong_m, args.count)
    with (out / "failures_index.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["file", "flight", "image", "status", "err_m", "diag"])
        for r in chosen:
            i = index[(r["flight"], r["image"])]
            region, _ = ds.records[i]
            reg = ds.regions[region]
            d = json.loads(r["diag"]) if r["diag"] else {}
            foot = float(r["footprint_m"])
            true = np.array([float(r["true_e"]), float(r["true_n"])])
            prior = np.array([float(r["prior_e"]), float(r["prior_n"])])
            ans = (np.array([float(r["est_e"]), float(r["est_n"])]) if r["status"] == "fix" else
                   np.array([d["cand_east"], d["cand_north"]]) if "cand_east" in d else None)
            panels = [Image.fromarray(ds.load_image(i)).resize((P, P), Image.BILINEAR),
                      Image.fromarray(reg.map_patch(true, foot, P).image)]
            panels.append(Image.fromarray(reg.map_patch(ans, foot, P).image) if ans is not None
                          else Image.new("RGB", (P, P), (128, 128, 128)))
            ctx_m = 2 * window + foot
            ctx = reg.map_patch(prior, ctx_m, P)
            cimg = Image.fromarray(ctx.image)
            dr = ImageDraw.Draw(cimg)
            px = lambda en: tuple(float(v) for v in en_to_patch_px(ctx, en[0], en[1]))  # noqa: E731
            a, b = px(prior - window), px(prior + window)
            dr.rectangle([a[0], b[1], b[0], a[1]], outline=WHITE, width=1)
            x, y = px(true)
            dr.line([(x - 7, y), (x + 7, y)], fill=RED, width=2)
            dr.line([(x, y - 7), (x, y + 7)], fill=RED, width=2)
            x, y = px(prior)
            dr.ellipse([x - 4, y - 4, x + 4, y + 4], fill=BLUE)
            if ans is not None:
                x, y = px(ans)
                dr.line([(x - 6, y - 6), (x + 6, y + 6)], fill=ORANGE, width=2)
                dr.line([(x - 6, y + 6), (x + 6, y - 6)], fill=ORANGE, width=2)
            panels.append(cimg)
            canvas = Image.new("RGB", (4 * P + 50, P + 70), WHITE)
            for k, im in enumerate(panels):
                canvas.paste(im, (10 + k * (P + 10), 10))
            t = ImageDraw.Draw(canvas)
            err = f"{float(r['err_m']):.0f} m" if r["status"] == "fix" else "no fix"
            cand = (f"candidate {np.linalg.norm(ans - true):.0f} m from label" if ans is not None else "")
            t.text((10, P + 14), f"flight {r['flight']} {r['image']} | status {r['status']} ({err}; {cand}) | "
                   f"peak {d.get('peak')} ratio {d.get('ratio')} overlap {d.get('overlap_valid_frac')} scale "
                   f"{d.get('scale')} rot {d.get('rot_deg')} | patch imagery {r['map_valid_frac']}", fill=(0, 0, 0))
            t.text((10, P + 30), f"1 aerial image | 2 map at label ({foot:.0f} m) | 3 map at answer | 4 window "
                   f"+-{window:g} m: red + label, blue prior, orange x answer, black = no imagery", fill=(0, 0, 0))
            t.text((10, P + 46), "UAV-VisLoc (Zenodo 19603534), map imagery Google Earth; academic use only, "
                   "not for redistribution", fill=(90, 90, 90))
            name = f"fail_{r['flight']}_{Path(r['image']).stem}.png"
            canvas.save(out / name)
            w.writerow([f"failures/{name}", r["flight"], r["image"], r["status"], r["err_m"], r["diag"]])
            print(f"{name}: {r['status']} {err}", flush=True)
    print(f"wrote {len(chosen)} failure overlays to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
