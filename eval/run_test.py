#!/usr/bin/env python3
"""The single test run on flight 11, exactly as pre-registered in docs/test_preregistration.md.

Refuses to run unless
  - the environment matches eval/reference_env_fusion.json (venv: matcher + GTSAM in one process),
  - the tracked git tree is clean and the tag `pre-test` is an ancestor of HEAD,
  - every file in docs/frozen_manifest.json (read from the `pre-test` tag, not the working tree) has
    the recorded SHA-256,
  - no lock file exists in the results folder (a second run is refused); `--resume` continues an
    unfinished run only (after a crash or WSL shutdown), never a completed one.
Fits nothing: it loads the frozen matcher, calibration, validity cuts and fusion design.
Passes (all resumable: every matcher call is appended to a cache at once, flushed and fsynced):
  1. matcher pass: accept-all matcher on all frames around the loader prior (seed 0, 50 m)
  2. closed loop: seeds 0-4 x 4 drift levels, matcher around the fused prediction (HEADLINE)
  3. open loop: seeds 0-19 x 4 drift levels on the matcher-pass candidates (secondary)
  4. tables T1-T4 and predictions P1-P3 into results.md
Outputs: eval/results/test_flight11/ (errors and statistics); label-derived positions only in its
private/ subfolder (git-ignored; UAV-VisLoc forbids redistribution).

Usage: env -u PYTHONPATH ~/venvs/trn/bin/python eval/run_test.py [--resume] [--workers 14] [--check-only]
"""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import math
import multiprocessing
import os
import subprocess
import sys
import time
from datetime import datetime as dt
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for sub in ("src/trn_fusion", "src/trn_calibration", "src/trn_matcher"):
    sys.path.insert(0, str(ROOT / sub))

FLIGHT, SPLIT = "11", "test"
OUT = ROOT / "eval/results/test_flight11"
CLOSED_SEEDS, OPEN_SEEDS = range(5), range(20)
W_FLOOR, W_CAP, LOST_M, LOST_RUN, WRONG_M = 150.0, 1000.0, 150.0, 3, 50.0
NOTE = ("Errors are against dataset labels and include label registration error; the reported uncertainty is "
        "not uncertainty about the true position. Odometry is SYNTHETIC.")


class Refused(RuntimeError):
    """A guard refused the run."""


# ---------------------------------------------------------------- guards (tested in test_run_test.py)
def check_clean(repo: Path) -> None:
    out = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=repo,
                         capture_output=True, text=True, check=True).stdout.strip()
    if out:
        raise Refused(f"git tree has uncommitted changes to tracked files:\n{out}")


def check_tag_ancestor(repo: Path, tag: str = "pre-test") -> None:
    r = subprocess.run(["git", "merge-base", "--is-ancestor", tag, "HEAD"], cwd=repo, capture_output=True)
    if r.returncode != 0:
        raise Refused(f"tag {tag} is missing or not an ancestor of HEAD")


def manifest_from_tag(repo: Path, tag: str = "pre-test") -> dict:
    r = subprocess.run(["git", "show", f"{tag}:docs/frozen_manifest.json"], cwd=repo, capture_output=True, text=True)
    if r.returncode != 0:
        raise Refused(f"cannot read docs/frozen_manifest.json at tag {tag}")
    return json.loads(r.stdout)


def check_hashes(root: Path, manifest: dict) -> None:
    bad = []
    for rel, want in manifest["files"].items():
        p = root / rel
        got = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else "missing"
        if got != want:
            bad.append(f"{rel}: {got[:12]} != frozen {want[:12]}")
    if bad:
        raise Refused("frozen files changed since pre-test:\n  " + "\n  ".join(bad))


def acquire_lock(out: Path, resume: bool, info: dict) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    lock = out / "RUN.lock"
    if not resume:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise Refused(f"{lock} exists: the test has already been run (or started); a second run is refused. "
                          "Use --resume only to continue an unfinished run.") from None
        state = {"state": "running", "started": info, "resumes": []}
        with os.fdopen(fd, "w") as fh:
            json.dump(state, fh, indent=1)
        return state
    if not lock.exists():
        raise Refused("--resume given but no run was started")
    state = json.loads(lock.read_text())
    if state["state"] == "complete":
        raise Refused("the test run is complete; it cannot be resumed or repeated")
    state["resumes"].append(info)
    lock.write_text(json.dumps(state, indent=1))
    return state


def finish_lock(out: Path) -> None:
    lock = out / "RUN.lock"
    state = json.loads(lock.read_text())
    state["state"] = "complete"
    state["completed"] = dt.now().isoformat(timespec="seconds")
    lock.write_text(json.dumps(state, indent=1))


def preflight(repo: Path) -> dict:
    import envcheck
    envcheck.require_reference_env(envcheck.FUSION)
    check_clean(repo)
    check_tag_ancestor(repo)
    check_hashes(repo, manifest_from_tag(repo))
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=repo, capture_output=True,
                            text=True).stdout.strip()
    return {"time": dt.now().isoformat(timespec="seconds"), "commit": commit, "pid": os.getpid(),
            "versions": envcheck.current_versions()}


# ---------------------------------------------------------------- shared state for worker processes
_W: dict = {}


def _init_worker() -> None:
    import cv2
    cv2.setNumThreads(1)


def _dataset():
    if "ds" not in _W:
        from trn_matcher.frames import footprints
        from trn_matcher.loader import LoaderConfig, VisLocDataset
        splits = json.loads((ROOT / "eval/splits.json").read_text())
        ds = VisLocDataset(Path.home() / "data/visloc/flights", splits, SPLIT, LoaderConfig(image_px=1024))
        _W["ds"], _W["foot"] = ds, footprints(ds)
        _W["idx"] = {r.filename: k for k, (_, r) in enumerate(ds.records)}
    return _W["ds"], _W["foot"], _W["idx"]


def cache_append(fh, record: dict) -> None:
    fh.write(json.dumps(record) + "\n")
    fh.flush()
    os.fsync(fh.fileno())


def read_cache(path: Path) -> dict:
    out = {}
    if path.exists():
        for line in path.read_text().splitlines():
            try:
                c = json.loads(line)
            except json.JSONDecodeError:   # a line cut by a kill
                continue
            out[c["key"]] = c
    return out


# ---------------------------------------------------------------- pass 1: matcher around the loader prior
def _match_frame(i: int) -> dict:
    from trn_matcher.frames import prepare_frame
    from trn_matcher.interface import DEFAULT_SEARCH
    from trn_matcher.matcher import FeatureMatcher
    ds, foot, _ = _dataset()
    m = _W.setdefault("matcher", FeatureMatcher(accept_all=True))
    fr = prepare_frame(ds, i, DEFAULT_SEARCH, 50.0, 0.5, foot)
    res = m.match(fr.image, fr.patch, fr.prior, DEFAULT_SEARCH)
    d = m.last_diag if res is None else res.diag
    return {"key": fr.filename, "i": i, "res": None if res is None else [res.x, res.y],
            "ratio": d.get("ratio"), "peak": d.get("peak"), "gate_pass": bool(d.get("gate_pass", False)),
            "reason": d.get("reason", "")}


def matcher_pass(workers: int) -> list[dict]:
    ds, _, _ = _dataset()
    path = OUT / "private" / "matcher_pass.cache.jsonl"
    done = read_cache(path)
    todo = [i for i, (_, r) in enumerate(ds.records) if r.filename not in done]
    print(f"matcher pass: {len(done)} cached, {len(todo)} to run", flush=True)
    if todo:
        with path.open("a") as fh, multiprocessing.get_context("fork").Pool(workers, initializer=_init_worker) as pool:
            for k, rec in enumerate(pool.imap_unordered(_match_frame, todo, chunksize=1)):
                cache_append(fh, rec)
                if (k + 1) % 25 == 0:
                    print(f"  matcher pass {len(done) + k + 1}/{len(ds.records)}", flush=True)
    cache = read_cache(path)
    return [cache[r.filename] for _, r in ds.records]


def build_inputs(mp: list[dict]) -> dict:
    ds, _, _ = _dataset()
    meta = {}
    with (Path.home() / f"data/visloc/flights/{FLIGHT}/{FLIGHT}-UAV-coordinates.csv").open(encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            meta[r["filename"]] = dt.fromisoformat(r["date"]).timestamp()
    order = sorted(range(len(ds.records)), key=lambda i: ds.records[i][1].filename)
    t = np.array([meta[ds.records[i][1].filename] for i in order])
    lab = np.array([ds.true_position(i) for i in order])
    by_name = {m["key"]: m for m in mp}
    names = [ds.records[i][1].filename for i in order]
    has = np.array([by_name[n]["res"] is not None for n in names])
    z = np.array([by_name[n]["res"] if by_name[n]["res"] is not None else [np.nan, np.nan] for n in names], float)
    lr = np.array([math.log(max(by_name[n]["ratio"], 1e-6)) if by_name[n]["res"] is not None else np.nan
                   for n in names])
    return {"labels": lab, "t": t - t[0], "prior0": ds.prior_position(order[0]), "has": has, "z": z, "lr": lr,
            "names": names, "order": order, "gate": np.array([by_name[n]["gate_pass"] for n in names]),
            "region": ds.records[order[0]][0]}


# ---------------------------------------------------------------- pass 2: closed loop
def run_name(level: float, seed: int) -> str:
    return f"{FLIGHT}_{level:g}pct_s{seed}".replace(".", "p")


def _closed_run(task) -> str:
    from trn_fusion import validity
    from trn_fusion.core import FusionCore, load_config
    from trn_fusion.fix_factor import FixModel
    from trn_fusion.odometry_sim import drift_b, simulate
    from trn_matcher.interface import Prior, SearchSpace
    from trn_matcher.matcher import FeatureMatcher
    level, seed = task
    name = run_name(level, seed)
    runs = OUT / "closed_loop"
    if (runs / f"{name}.frames.csv").exists():
        return f"{name}: done earlier"
    t0 = time.time()
    ds, foot, idx = _dataset()
    inp = _W["inp"]
    cfg = load_config()
    so = cfg["synthetic_odometry"]
    lab = inp["labels"]
    b = drift_b(level, so["reference_distance_m"])
    odo = simulate(lab, b, so["floor_a_m"], seed=1000 * so["drift_levels_pct"].index(level) + seed)
    core = FusionCore(cfg, FixModel(), b=b)
    matcher = FeatureMatcher(accept_all=True)
    cache_path = OUT / "private" / f"{name}.cache.jsonl"
    cache = read_cache(cache_path)
    frames, attempts = [], []
    with cache_path.open("a") as cfh:
        for k in range(len(lab)):
            t = inp["t"][k]
            if k == 0:
                core.start(t, inp["prior0"], cfg["prior"]["sigma_m"])
            else:
                core.odometry(t, odo[k] - odo[k - 1])
            if core.last_fused_t is None or t - core.last_fused_t >= cfg["thinning"]["interval_s"] - 1e-9:
                bel = core.belief()
                sig = validity.major_sigma(bel.cov)
                i = inp["order"][k]
                region, rec = ds.records[i]
                reg = ds.regions[region]
                store = next(s for s in reg.stores if s.name == rec.flight)
                window = min(max(W_FLOOR, 3 * sig), W_CAP, _far_edge(store, reg.frame, bel.mean))
                hit = cache.get(str(k))
                if hit is not None and (abs(hit["cx"] - bel.mean[0]) > 1e-6 or abs(hit["cy"] - bel.mean[1]) > 1e-6):
                    raise RuntimeError(f"{name}: cached call at frame {k} around a different prediction")
                if hit is None:
                    f_m = foot[(region, rec.flight)]
                    search = SearchSpace(window_m=window)
                    size = search.patch_size_m(f_m)
                    patch = reg.map_patch(bel.mean, size, int(math.ceil(size / 0.5)))
                    res = None
                    if patch.valid.mean() > 0:
                        res = matcher.match(ds.load_image(i), patch,
                                            Prior(float(bel.mean[0]), float(bel.mean[1]), sig, f_m), search)
                    hit = {"key": str(k), "cx": float(bel.mean[0]), "cy": float(bel.mean[1]), "w": window,
                           "valid": float(patch.valid.mean()),
                           "res": None if res is None else [res.x, res.y, res.diag["ratio"]]}
                    cache_append(cfh, hit)
                att = {"k": k, "t": t, "pred_err_m": float(np.hypot(*(bel.mean - lab[k]))), "sigma_m": sig,
                       "window_m": window, "cand_err_m": "", "decision": ""}
                if hit["res"] is None:
                    att["decision"] = "no_candidate" if hit["valid"] > 0 else "window_off_map"
                else:
                    zk = np.array(hit["res"][:2])
                    att["cand_err_m"] = float(np.hypot(*(zk - lab[k])))
                    att["decision"] = core.fix(t, zk, math.log(max(hit["res"][2], 1e-6)))
                attempts.append(att)
            bel = core.belief()
            frames.append({"k": k, "t": t, "e_e": bel.mean[0] - lab[k][0], "e_n": bel.mean[1] - lab[k][1],
                           "c_ee": bel.cov[0, 0], "c_en": bel.cov[0, 1], "c_nn": bel.cov[1, 1],
                           "state": validity.NAMES[bel.validity]})
    for rows, suffix in ((attempts, ".attempts.csv"), (frames, ".frames.csv")):   # frames last: marks done
        tmp = runs / f"{name}{suffix}.tmp"
        with tmp.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        os.replace(tmp, runs / f"{name}{suffix}")
    return f"{name}: {len(attempts)} attempts ({len(cache)} cached), {time.time() - t0:.0f} s"


def _far_edge(store, frame, centre) -> float:
    lat, lon, _ = frame.to_geodetic(float(centre[0]), float(centre[1]))
    row, col = store.georef.latlon_to_pixel(lat, lon)
    g = store.georef
    lat_mid = g.lat0 + g.dlat_drow * store.height_px / 2
    m_row = abs(g.dlat_drow) * 111_320.0
    m_col = abs(g.dlon_dcol) * 111_320.0 * math.cos(math.radians(lat_mid))
    return max(abs(float(row)) * m_row, abs(store.height_px - float(row)) * m_row,
               abs(float(col)) * m_col, abs(store.width_px - float(col)) * m_col)


def closed_loop(workers: int, inp: dict) -> None:
    from trn_fusion.core import load_config
    (OUT / "closed_loop").mkdir(exist_ok=True)
    _W["inp"] = inp
    levels = load_config()["synthetic_odometry"]["drift_levels_pct"]
    tasks = [(lv, s) for lv in levels for s in CLOSED_SEEDS]
    with multiprocessing.get_context("fork").Pool(min(workers, len(tasks)), initializer=_init_worker,
                                                  maxtasksperchild=1) as pool:
        for msg in pool.imap_unordered(_closed_run, tasks):
            print(time.strftime("%H:%M:%S"), "closed loop", msg, flush=True)


# ---------------------------------------------------------------- pass 3: open loop and tables
def open_loop(inp: dict) -> list[dict]:
    import eval_fusion as ef
    from trn_fusion.core import load_config
    from trn_fusion.fix_factor import FixModel
    from trn_fusion.odometry_sim import drift_b, simulate
    cfg = load_config()
    so = cfg["synthetic_odometry"]
    fm = FixModel()
    lab = inp["labels"]
    rows = []
    for li, level in enumerate(so["drift_levels_pct"]):
        b = drift_b(level, so["reference_distance_m"])
        for s in OPEN_SEEDS:
            odo = simulate(lab, b, so["floor_a_m"], seed=1000 * li + s)
            mean, cov, state, _, _ = ef.run_fused(inp, odo, b, cfg, fm)
            e = mean - lab
            d2 = ef.nees(e, cov)
            est_o, _ = ef.run_odometry_only(inp, odo, b, so["floor_a_m"], cfg["prior"]["sigma_m"])
            et = (lab[0] + (odo - odo[0])) - lab
            err = np.hypot(*e.T)
            rows.append({"drift_pct": level, "seed": s, "rmse": float(np.sqrt(np.mean(err ** 2))),
                         "median": float(np.median(err)), "nees": float(d2.mean()),
                         "cov95": float(np.mean(d2 <= 5.991)),
                         "odo_prior_rmse": float(np.sqrt(np.mean(np.sum((est_o - lab) ** 2, axis=1)))),
                         "odo_true_rmse": float(np.sqrt(np.mean(np.sum(et ** 2, axis=1))))})
    return rows


def closed_rows() -> list[dict]:
    from trn_fusion.core import load_config
    out = []
    for level in load_config()["synthetic_odometry"]["drift_levels_pct"]:
        for s in CLOSED_SEEDS:
            name = run_name(level, s)
            fr = list(csv.DictReader((OUT / "closed_loop" / f"{name}.frames.csv").open()))
            e = np.array([[float(r["e_e"]), float(r["e_n"])] for r in fr])
            cov = np.array([[[float(r["c_ee"]), float(r["c_en"])], [float(r["c_en"]), float(r["c_nn"])]] for r in fr])
            d2 = np.einsum("ni,nij,nj->n", e, np.linalg.inv(cov), e)
            err = np.hypot(*e.T)
            over = np.convolve((err > LOST_M).astype(int), np.ones(LOST_RUN, int), "valid")
            states = [r["state"] for r in fr]
            st = {f"{x}_share": float(np.mean([y == x for y in states])) for x in
                  ("STRONG", "AGING", "UNCERTAIN", "DO_NOT_PUBLISH")}
            st.update({f"{x}_wrong": (float(np.mean(err[[y == x for y in states]] > WRONG_M))
                                      if any(y == x for y in states) else float("nan"))
                       for x in ("STRONG", "AGING", "UNCERTAIN", "DO_NOT_PUBLISH")})
            out.append({"drift_pct": level, "seed": s, "rmse": float(np.sqrt(np.mean(err ** 2))),
                        "median": float(np.median(err)), "nees": float(d2.mean()),
                        "cov95": float(np.mean(d2 <= 5.991)), "lost": int(np.any(over >= LOST_RUN)), **st})
    return out


def calibration_tables(inp: dict) -> tuple[dict, dict]:
    import calib_metrics as cm
    from trn_calibration.covariance import MixtureModel
    spec = {k: v for k, v in json.loads((ROOT / "src/trn_calibration/trn_calibration/calibration_frozen.json")
                                        .read_text())["models"]["selected"].items() if k != "name"}
    m = MixtureModel(**spec)
    cuts = json.loads((ROOT / "src/trn_calibration/trn_calibration/validity_cuts.json").read_text())
    h = inp["has"]
    x = inp["lr"][h].reshape(-1, 1)
    e = inp["z"][h] - inp["labels"][h]
    err = np.hypot(*e.T)
    wrong = (err > WRONG_M).astype(int)
    pw = m.p_wrong(x)
    r90 = m.radius(x, 0.9)
    t4 = {"n": int(h.sum()), "nll": float(m.nll(x, e).mean()),
          **{f"cov{p}": float(np.mean(err <= m.radius(x, p / 100))) for p in (50, 90, 95)},
          "sharpness_r90_m": float(np.median(r90)), "ece": cm.ece(pw, wrong), "auc": cm.auc(pw, wrong)}
    gate = inp["gate"][h]
    sets = {"all candidates": np.ones(len(pw), bool), "accepted by the frozen gate": gate,
            "fix state STRONG": pw <= cuts["strong_max_p_wrong"],
            "fix state UNCERTAIN": (pw > cuts["strong_max_p_wrong"]) & (pw <= cuts["publish_max_p_wrong"]),
            "fix state DO_NOT_PUBLISH": pw > cuts["publish_max_p_wrong"]}
    t3 = {k: {"n": int(v.sum()), "observed": float(wrong[v].mean()) if v.any() else float("nan"),
              "promise": float(pw[v].mean()) if v.any() else float("nan")} for k, v in sets.items()}
    t3["_acceptance"] = float(gate.mean())
    t3["_frames"] = int(len(inp["has"]))
    return t3, t4


def fmt(v, f="{:.1f}"):
    return "-" if v is None or (isinstance(v, float) and not math.isfinite(v)) else f.format(v)


def report(inp: dict, open_r: list[dict], closed_r: list[dict], t3: dict, t4: dict, state: dict) -> str:
    from trn_fusion.core import load_config
    levels = load_config()["synthetic_odometry"]["drift_levels_pct"]
    raw_err = np.hypot(*(inp["z"][inp["has"]] - inp["labels"][inp["has"]]).T)
    mean = lambda rows, k: float(np.nanmean([r[k] for r in rows]))  # noqa: E731
    L = ["# Flight 11 test results (single pre-registered run)", "",
         f"Run started {state['started']['time']} at commit {state['started']['commit']}; "
         f"resumes: {len(state['resumes'])} ({', '.join(r['time'] for r in state['resumes']) or 'none'}). "
         f"Environment {state['started']['versions']}.", "",
         "## T1 Fused position error, flight 11 (HEADLINE = closed loop)", "",
         "| Drift | Closed loop RMSE (median) [m], seeds 0-4 | Open loop RMSE (median) [m], seeds 0-19 | Odometry-only "
         "from prior RMSE [m] | Odometry-only from TRUE start RMSE [m] | Raw fixes RMSE (median) [m] | Closed loop NEES "
         "/ cov 95 % | Open loop NEES / cov 95 % | Closed-loop runs that lose track |", "|---|---|---|---|---|---|---|---|---|"]
    pred = {}
    for lv in levels:
        c = [r for r in closed_r if r["drift_pct"] == lv]
        o = [r for r in open_r if r["drift_pct"] == lv]
        pred[lv] = (mean(c, "rmse"), mean(o, "odo_true_rmse"))
        L.append(f"| {lv:g} % | {mean(c, 'rmse'):.1f} ({mean(c, 'median'):.1f}) | {mean(o, 'rmse'):.1f} "
                 f"({mean(o, 'median'):.1f}) | {mean(o, 'odo_prior_rmse'):.1f} | {mean(o, 'odo_true_rmse'):.1f} | "
                 f"{float(np.sqrt(np.mean(raw_err ** 2))):.1f} ({float(np.median(raw_err)):.1f}) | "
                 f"{mean(c, 'nees'):.2f} / {mean(c, 'cov95'):.2f} | {mean(o, 'nees'):.2f} / {mean(o, 'cov95'):.2f} | "
                 f"{sum(r['lost'] for r in c)}/{len(c)} |")
    L += ["", NOTE, "", "## T2 Belief validity states, closed loop (seeds 0-4)", "",
          "| Drift | STRONG share / wrong | AGING share / wrong | UNCERTAIN share / wrong | DO_NOT_PUBLISH share / wrong |",
          "|---|---|---|---|---|"]
    for lv in levels:
        c = [r for r in closed_r if r["drift_pct"] == lv]
        L.append(f"| {lv:g} % | " + " | ".join(f"{mean(c, s + '_share'):.2f} / {fmt(mean(c, s + '_wrong'), '{:.2f}')}"
                                                for s in ("STRONG", "AGING", "UNCERTAIN", "DO_NOT_PUBLISH")) + " |")
    L += ["", "wrong = share of the state's frames with fused error > 50 m. " + NOTE, "",
          f"## T3 Matcher and fix calibration (matcher pass, {t3['_frames']} frames)", "",
          "| Set | Frames | Observed wrong rate | Calibration's promise (mean P(wrong)) | Above the promise? |",
          "|---|---|---|---|---|"]
    for k, v in t3.items():
        if k.startswith("_"):
            continue
        label = k + (f" (acceptance = {t3['_acceptance']:.3f})" if k.startswith("accepted") else "")
        above = "-" if not math.isfinite(v["observed"]) else ("yes" if v["observed"] > v["promise"] else "no")
        L.append(f"| {label} | {v['n']} | {fmt(v['observed'], '{:.3f}')} | {fmt(v['promise'], '{:.3f}')} | {above} |")
    L += ["", f"## T4 Fix-error calibration on flight 11 (frozen ratio model, {t4['n']} candidates)", "",
          "| NLL | Coverage 50 % | Coverage 90 % | Coverage 95 % | Sharpness (median 90 % radius) [m] | ECE of P(wrong) | "
          "AUC wrong |", "|---|---|---|---|---|---|---|",
          f"| {t4['nll']:.3f} | {t4['cov50']:.2f} | {t4['cov90']:.2f} | {t4['cov95']:.2f} | {t4['sharpness_r90_m']:.1f} | "
          f"{t4['ece']:.3f} | {t4['auc']:.3f} |", "", "Errors are against dataset labels and include label registration "
          "error.", "", "## Predictions", ""]
    nees_c = mean(closed_r, "nees")
    acc = t3["accepted by the frozen gate"]
    p = [("P1", "closed-loop NEES > 2 (mean over levels)", nees_c > 2, f"mean NEES {nees_c:.2f}"),
         ("P2", "accepted-fix wrong rate above the promise", acc["observed"] > acc["promise"],
          f"observed {acc['observed']:.3f} vs promise {acc['promise']:.3f} (n = {acc['n']})"),
         ("P3a", "fusion does NOT beat perfect-start odometry at 0.1 %", pred[levels[0]][0] >= pred[levels[0]][1],
          f"closed {pred[levels[0]][0]:.1f} m vs odometry {pred[levels[0]][1]:.1f} m"),
         ("P3b", "fusion beats perfect-start odometry at 0.5, 1 and 2 %",
          all(pred[lv][0] < pred[lv][1] for lv in levels[1:]),
          "; ".join(f"{lv:g} %: {pred[lv][0]:.1f} vs {pred[lv][1]:.1f} m" for lv in levels[1:]))]
    L += ["| # | Prediction | Held? | Numbers |", "|---|---|---|---|"]
    L += [f"| {a} | {b} | {'HELD' if c else 'FAILED'} | {d} |" for a, b, c, d in p]
    L += ["", NOTE, ""]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--check-only", action="store_true", help="run the guards only, take no lock")
    args = ap.parse_args()
    try:
        info = preflight(ROOT)
        if args.check_only:
            print("all guards pass (no lock taken)")
            return 0
        state = acquire_lock(OUT, args.resume, info)
    except Refused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 4
    (OUT / "private").mkdir(exist_ok=True)
    print(f"{info['time']} test run {'resumed' if args.resume else 'started'} at commit {info['commit']}", flush=True)
    mp = matcher_pass(args.workers)
    inp = build_inputs(mp)
    closed_loop(args.workers, inp)
    open_r = open_loop(inp)
    closed_r = closed_rows()
    t3, t4 = calibration_tables(inp)
    for name, rows in (("open_loop.csv", open_r), ("closed_loop_summary.csv", closed_r)):
        with (OUT / name).open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    (OUT / "tables.json").write_text(json.dumps({"T3": t3, "T4": t4}, indent=1, default=float) + "\n")
    state = json.loads((OUT / "RUN.lock").read_text())
    (OUT / "results.md").write_text(report(inp, open_r, closed_r, t3, t4, state))
    finish_lock(OUT)
    print(f"{datetime.datetime.now().isoformat(timespec='seconds')} test run complete -> {OUT / 'results.md'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
