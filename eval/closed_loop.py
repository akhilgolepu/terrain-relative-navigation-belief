#!/usr/bin/env python3
"""Week 7 closed loop: the matcher searches around the FUSED prediction, not the dataset prior.

For each run (flight, drift level, seed): SYNTHETIC odometry (same seeds as the open-loop runs),
the frozen fusion design (fusion_frozen.json) and the frozen matcher in accept-all mode. At every
frame where the fusion's thinning rule allows a fix (>= 9 s since the last FUSED fix), the matcher
runs on that frame's aerial image with
  prior centre = fused predicted position (after the odometry step)
  window       = max(150 m, 3 x the predicted 1-sigma major axis), capped so the window does not
                 reach beyond the map's extent (and at 1000 m for compute)
and its best candidate is offered to the fusion (mixture factor, gate as frozen). If the window does
not overlap the map at all, or the matcher finds no candidate, there is no fix ("no candidate").
Per run: one CSV of frames (fused error, covariance, state) and one of fix attempts (window, candidate
error, fused/gated), written atomically; existing runs are skipped. Every matcher call is also cached
at once (runs/<name>.cache.jsonl), so a run killed midway (WSL shuts down when the session ends)
resumes from its last matcher call.
NOTE: the week 5 calibration (sigma, w from the ratio) was fitted with +-150 m windows; larger
windows give more chances of a wrong match than the calibration assumes.
Runs in the venv (GTSAM + matcher; OpenCV 5.0 there: matcher numbers differ slightly from the
system-Python reference runs). Never flight 11.

Usage: env -u PYTHONPATH ~/venvs/trn/bin/python eval/closed_loop.py run [--workers 14]
       env -u PYTHONPATH ~/venvs/trn/bin/python eval/closed_loop.py summary
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import multiprocessing
import os
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for sub in ("src/trn_fusion", "src/trn_calibration", "src/trn_matcher"):
    sys.path.insert(0, str(ROOT / sub))
import envcheck  # noqa: E402
import eval_fusion as ef  # noqa: E402
from trn_fusion import validity  # noqa: E402
from trn_fusion.core import FusionCore, load_config  # noqa: E402
from trn_fusion.fix_factor import FixModel  # noqa: E402
from trn_fusion.odometry_sim import drift_b, simulate  # noqa: E402

OUT = Path(__file__).parent / "results/week7/closed_loop"
SPLIT = {"10": "tune", "05": "calibrate"}
SEEDS = range(5)
W_FLOOR, W_CAP = 150.0, 1000.0
LOST_M, LOST_RUN = 150.0, 3
_W: dict = {}


def _init() -> None:
    import cv2
    cv2.setNumThreads(1)


def _dataset(flight: str):
    if flight not in _W:
        from trn_matcher.frames import footprints
        from trn_matcher.loader import LoaderConfig, VisLocDataset
        splits = json.loads((Path(__file__).parent / "splits.json").read_text())
        ds = VisLocDataset(Path.home() / "data/visloc/flights", splits, SPLIT[flight], LoaderConfig(image_px=1024))
        idx = {r.filename: k for k, (_, r) in enumerate(ds.records)}
        _W[flight] = (ds, footprints(ds), idx)
    return _W[flight]


def map_extent_window(store, frame, centre: np.ndarray) -> float:
    """Largest half-window [m] around centre that still reaches into the map (inf if inside)."""
    lat, lon, _ = frame.to_geodetic(float(centre[0]), float(centre[1]))
    row, col = store.georef.latlon_to_pixel(lat, lon)
    g = store.georef
    lat_mid = g.lat0 + g.dlat_drow * store.height_px / 2
    m_row = abs(g.dlat_drow) * 111_320.0
    m_col = abs(g.dlon_dcol) * 111_320.0 * math.cos(math.radians(lat_mid))
    # distance from the centre to the far edges: a window larger than this only adds off-map area
    far = max(abs(float(row)) * m_row, abs(store.height_px - float(row)) * m_row,
              abs(float(col)) * m_col, abs(store.width_px - float(col)) * m_col)
    return far


def run_name(flight: str, level: float, seed: int) -> str:
    """Return a run name without dots (a dot would be taken for a file suffix)."""
    return f"{flight}_{level:g}pct_s{seed}".replace(".", "p")


def run_one(task) -> str:
    flight, level, seed = task
    name = run_name(flight, level, seed)
    if (OUT / "runs" / f"{name}.frames.csv").exists():
        return f"{name}: exists, skipped"
    from trn_matcher.interface import Prior, SearchSpace
    from trn_matcher.matcher import FeatureMatcher
    t_start = time.time()
    ds, foot, idx = _dataset(flight)
    cfg = load_config()
    so = cfg["synthetic_odometry"]
    inp = ef.load_inputs(flight)
    rows_in = list(csv.DictReader((Path(__file__).parent / f"results/week6/inputs_{flight}.csv").open()))
    lab = inp["labels"]
    b = drift_b(level, so["reference_distance_m"])
    odo = simulate(lab, b, so["floor_a_m"], seed=1000 * so["drift_levels_pct"].index(level) + seed)
    core = FusionCore(cfg, FixModel(), b=b)
    matcher = FeatureMatcher(accept_all=True)
    interval = cfg["thinning"]["interval_s"]
    frames, attempts = [], []
    # matcher-call cache: one JSON line per call, flushed and fsynced at once, so a killed run resumes
    # by replaying the (cheap, deterministic) fusion and reusing every finished matcher call
    (OUT / "runs").mkdir(parents=True, exist_ok=True)
    cache_path = OUT / "runs" / f"{name}.cache.jsonl"
    cache = {}
    if cache_path.exists():
        for line in cache_path.read_text().splitlines():
            try:
                c = json.loads(line)
            except json.JSONDecodeError:   # a line cut by the kill
                continue
            cache[str(c.pop("k"))] = c
    cache_fh = cache_path.open("a")
    for k in range(len(lab)):
        t = inp["t"][k]
        if k == 0:
            core.start(t, inp["prior0"], cfg["prior"]["sigma_m"])
        else:
            core.odometry(t, odo[k] - odo[k - 1])
        if core.last_fused_t is None or t - core.last_fused_t >= interval - 1e-9:
            bel = core.belief()
            sig = validity.major_sigma(bel.cov)
            i = idx[rows_in[k]["image"]]
            region, rec = ds.records[i]
            reg = ds.regions[region]
            store = next(s for s in reg.stores if s.name == rec.flight)
            w_cov = map_extent_window(store, reg.frame, bel.mean)
            window = min(max(W_FLOOR, 3 * sig), W_CAP, w_cov)
            f_m = foot[(region, rec.flight)]
            search = SearchSpace(window_m=window)
            size = search.patch_size_m(f_m)
            patch = reg.map_patch(bel.mean, size, int(math.ceil(size / 0.5)))
            att = {"k": k, "t": t, "pred_err_m": float(np.hypot(*(bel.mean - lab[k]))), "sigma_m": sig,
                   "window_m": window, "map_valid": float(patch.valid.mean()), "cand_err_m": "", "decision": ""}
            key = f"{k}"
            hit = cache.get(key)
            if hit is not None and (abs(hit["cx"] - float(bel.mean[0])) > 1e-6 or abs(hit["cy"] - float(bel.mean[1])) > 1e-6
                                    or abs(hit["w"] - window) > 1e-6):
                raise RuntimeError(f"{name}: cached matcher call at frame {k} was made around a different prediction; "
                                   "the replay is not deterministic - delete the cache and rerun")
            if hit is None:
                res = None
                if patch.valid.mean() > 0:
                    res = matcher.match(ds.load_image(i), patch,
                                        Prior(float(bel.mean[0]), float(bel.mean[1]), sig, f_m), search)
                hit = {"cx": float(bel.mean[0]), "cy": float(bel.mean[1]), "w": window,
                       "res": None if res is None else [res.x, res.y, res.diag["ratio"]]}
                cache_fh.write(json.dumps({"k": k, **hit}) + "\n")
                cache_fh.flush()
                os.fsync(cache_fh.fileno())
            if hit["res"] is None:
                att["decision"] = "no_candidate" if patch.valid.mean() > 0 else "window_off_map"
            else:
                z = np.array(hit["res"][:2])
                att["cand_err_m"] = float(np.hypot(*(z - lab[k])))
                att["decision"] = core.fix(t, z, math.log(max(hit["res"][2], 1e-6)))
            attempts.append(att)
        bel = core.belief()
        frames.append({"k": k, "t": t, "err_m": float(np.hypot(*(bel.mean - lab[k]))),
                       "c_ee": bel.cov[0, 0], "c_en": bel.cov[0, 1], "c_nn": bel.cov[1, 1],
                       "e_e": bel.mean[0] - lab[k][0], "e_n": bel.mean[1] - lab[k][1],
                       "state": validity.NAMES[bel.validity]})
    (OUT / "runs").mkdir(parents=True, exist_ok=True)
    for rows, suffix in ((attempts, ".attempts.csv"), (frames, ".frames.csv")):   # frames last: marks done
        final = OUT / "runs" / f"{name}{suffix}"
        tmp = OUT / "runs" / f"{name}{suffix}.tmp"
        with tmp.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        os.replace(tmp, final)
    cache_fh.close()
    return f"{name}: {len(attempts)} attempts ({len(cache)} from the cache), {time.time() - t_start:.0f} s"


def run(workers: int) -> int:
    cfg = load_config()
    tasks = [(f, lv, s) for f in ("05", "10") for lv in cfg["synthetic_odometry"]["drift_levels_pct"] for s in SEEDS]
    # longest first: flight 05 runs take about 3x as long as flight 10 runs
    with multiprocessing.get_context("fork").Pool(workers, initializer=_init, maxtasksperchild=1) as pool:
        for msg in pool.imap_unordered(run_one, tasks):
            print(time.strftime("%H:%M:%S"), msg, flush=True)
    print("all runs done", flush=True)
    return 0


def summary() -> int:
    cfg = load_config()
    open_rows = {}
    for f in ("10", "05"):
        for r in csv.DictReader((Path(__file__).parent / f"results/week7/frozen_design/fusion_{f}.csv").open()):
            open_rows[(f, float(r["drift_pct"]), int(r["seed"]))] = r
    lines = ["## Closed loop (matcher around the fused prediction) vs open loop (matcher around the dataset prior)",
             "", "Same SYNTHETIC odometry seeds (0-4), frozen fusion design. Track lost = fused error > 150 m for >= 3 "
             "consecutive frames. Errors are against dataset labels and include label registration error. The week 5 "
             "calibration was fitted with +-150 m windows.", "",
             "| Flight | Drift | Closed-loop RMSE | Open-loop RMSE (same seeds) | Runs that lose track | Attempts | "
             "Wrong candidates (> 50 m) | No candidate / window off map | Median window [m] | Gated |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    out = []
    for f in ("10", "05"):
        for lv in cfg["synthetic_odometry"]["drift_levels_pct"]:
            rm, om, lost, att = [], [], 0, []
            for s in SEEDS:
                base = OUT / "runs" / run_name(f, lv, s)
                if not Path(f"{base}.frames.csv").exists():
                    continue
                fr = list(csv.DictReader(Path(f"{base}.frames.csv").open()))
                err = np.array([float(r["err_m"]) for r in fr])
                rm.append(float(np.sqrt(np.mean(err ** 2))))
                om.append(float(open_rows[(f, lv, s)]["fused_rmse"]))
                over = np.convolve((err > LOST_M).astype(int), np.ones(LOST_RUN, int), "valid")
                lost += int(np.any(over >= LOST_RUN))
                att += list(csv.DictReader(Path(f"{base}.attempts.csv").open()))
            if not rm:
                continue
            ce = [float(a["cand_err_m"]) for a in att if a["cand_err_m"] != ""]
            nocand = sum(a["decision"] in ("no_candidate", "window_off_map") for a in att)
            off = sum(a["decision"] == "window_off_map" for a in att)
            row = {"flight": f, "drift_pct": lv, "runs": len(rm), "closed_rmse": float(np.mean(rm)),
                   "open_rmse": float(np.mean(om)), "runs_lost": lost, "attempts": len(att),
                   "wrong_cand": float(np.mean(np.array(ce) > 50)) if ce else float("nan"),
                   "no_candidate": nocand / len(att), "window_off_map": off / len(att),
                   "median_window_m": float(np.median([float(a["window_m"]) for a in att])),
                   "gated": sum(a["decision"] == "gated" for a in att)}
            out.append(row)
            lines.append(f"| {f} | {lv} % | {row['closed_rmse']:.1f} | {row['open_rmse']:.1f} | {lost}/{len(rm)} | "
                         f"{len(att)} | {row['wrong_cand']:.1%} | {row['no_candidate']:.1%} / {row['window_off_map']:.1%} | "
                         f"{row['median_window_m']:.0f} | {row['gated']} |")
    lines.append("")
    (OUT / "summary.md").write_text("\n".join(lines))
    with (OUT / "summary.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "summary"])
    ap.add_argument("--workers", type=int, default=14)
    a = ap.parse_args()
    envcheck.require_reference_env(envcheck.FUSION)
    OUT.mkdir(parents=True, exist_ok=True)
    sys.exit(run(a.workers) if a.cmd == "run" else summary())
