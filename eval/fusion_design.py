#!/usr/bin/env python3
"""Week 7 fusion design freeze: fix-covariance inflation and gate choice on flight 05, check on 10.

Rules (Akhil, 2026-11-22; fixed before any run):
  inflation  kappa multiplies the fix inlier sigma. Grid 1.0..3.0 step 0.1, flight 05, 20 seeds x
             4 drift levels, week 6 gate (chi-square on the inlier model). Choose the kappa whose
             mean NEES (mean over all runs of each run's mean NEES) is closest to 2. Flight 05 is
             IN-SAMPLE for the fix model (week 5 fitted it on 05).
  gate       with that kappa, three variants on flight 05: 'chi2_inlier' (week 6), 'off' (mixture
             only), 'mixture_pvalue'. Choose the lowest RMSE averaged over the four drift levels
             (mean over seeds per level, then over levels).
  freeze     write fix_inflation and gate_mode into src/trn_fusion/trn_fusion/fusion_frozen.json
             (the week 6 version is kept as eval/results/week6/prefreeze/fusion_frozen_week6.json).
  check      only then run the frozen design on flight 10 and report NEES and RMSE.
Never flight 11. Venv (GTSAM), envcheck against reference_env_fusion.json.

Usage: env -u PYTHONPATH ~/venvs/trn/bin/python eval/fusion_design.py fit     (05: inflation, gates, freeze)
       env -u PYTHONPATH ~/venvs/trn/bin/python eval/fusion_design.py check10 (10: frozen design)
"""
from __future__ import annotations

import csv
import json
import multiprocessing
import shutil
import sys
from pathlib import Path

import numpy as np

import envcheck
import eval_fusion as ef
from trn_fusion.core import load_config
from trn_fusion.config import FROZEN
from trn_fusion.fix_factor import FixModel
from trn_fusion.odometry_sim import drift_b, simulate

OUT = Path(__file__).parent / "results/week7"
KAPPAS = [round(1.0 + 0.1 * i, 1) for i in range(21)]
GATES = ["chi2_inlier", "off", "mixture_pvalue"]
_W: dict = {}


def _init(flight: str) -> None:
    _W["inp"] = ef.load_inputs(flight)
    _W["fm"] = FixModel()


def _run(task):
    kappa, gate, level, seed = task
    cfg = {**load_config(), "fix_inflation": kappa, "gate_mode": gate}
    so = cfg["synthetic_odometry"]
    inp = _W["inp"]
    b = drift_b(level, so["reference_distance_m"])
    odo = simulate(inp["labels"], b, so["floor_a_m"], seed=1000 * so["drift_levels_pct"].index(level) + seed)
    mean, cov, _, _, core = ef.run_fused(inp, odo, b, cfg, _W["fm"])
    e = mean - inp["labels"]
    d2 = ef.nees(e, cov)
    return {"kappa": kappa, "gate": gate, "drift_pct": level, "seed": seed,
            "rmse": float(np.sqrt(np.mean(np.sum(e ** 2, axis=1)))), "nees": float(d2.mean()),
            "cov95": float(np.mean(d2 <= ef.CHI2_95)), "fused": core.count.fused, "gated": core.count.gated}


def run_grid(flight: str, tasks: list) -> list[dict]:
    with multiprocessing.get_context("fork").Pool(14, initializer=_init, initargs=(flight,)) as pool:
        return pool.map(_run, tasks, chunksize=4)


def write(rows: list[dict], name: str) -> None:
    with (OUT / name).open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def per_level(rows, key):
    levels = sorted({r["drift_pct"] for r in rows})
    return {lv: float(np.mean([r[key] for r in rows if r["drift_pct"] == lv])) for lv in levels}


def fit() -> int:
    cfg = load_config()
    so = cfg["synthetic_odometry"]
    seeds, levels = range(so["seeds"]), so["drift_levels_pct"]
    rows = run_grid("05", [(k, "chi2_inlier", lv, s) for k in KAPPAS for lv in levels for s in seeds])
    write(rows, "design_inflation_05.csv")
    nees = {k: float(np.mean([r["nees"] for r in rows if r["kappa"] == k])) for k in KAPPAS}
    kappa = min(KAPPAS, key=lambda k: abs(nees[k] - 2.0))
    lines = ["## Fix-covariance inflation on flight 05 (in-sample for the fix model), chi-square gate", "",
             "| kappa | mean NEES | NEES by drift 0.1 / 0.5 / 1 / 2 % | cov 95 % | RMSE mean over levels [m] |",
             "|---|---|---|---|---|"]
    for k in KAPPAS:
        rk = [r for r in rows if r["kappa"] == k]
        pl = per_level(rk, "nees")
        lines.append(f"| {k} | {nees[k]:.2f} | " + " / ".join(f"{v:.2f}" for v in pl.values())
                     + f" | {np.mean([r['cov95'] for r in rk]):.2f} | {np.mean(list(per_level(rk, 'rmse').values())):.1f} |")
    lines += ["", f"Chosen kappa = {kappa} (mean NEES {nees[kappa]:.2f}, closest to 2).", ""]
    rows_g = run_grid("05", [(kappa, g, lv, s) for g in GATES for lv in levels for s in seeds])
    write(rows_g, "design_gates_05.csv")
    score = {g: float(np.mean(list(per_level([r for r in rows_g if r["gate"] == g], "rmse").values()))) for g in GATES}
    gate = min(GATES, key=lambda g: score[g])
    lines += [f"## Gate variants on flight 05 with kappa {kappa}", "",
              "| Gate | RMSE by drift 0.1 / 0.5 / 1 / 2 % [m] | Mean RMSE | Mean NEES | Fused / gated per run |",
              "|---|---|---|---|---|"]
    for g in GATES:
        rg = [r for r in rows_g if r["gate"] == g]
        lines.append(f"| {g} | " + " / ".join(f"{v:.1f}" for v in per_level(rg, "rmse").values())
                     + f" | {score[g]:.2f} | {np.mean([r['nees'] for r in rg]):.2f} | "
                       f"{np.mean([r['fused'] for r in rg]):.0f} / {np.mean([r['gated'] for r in rg]):.0f} |")
    lines += ["", f"Chosen gate = {gate} (lowest mean RMSE over the four drift levels).", "",
              "Errors are against dataset labels and include label registration error; odometry is SYNTHETIC.", ""]
    keep = Path(__file__).parent / "results/week6/prefreeze/fusion_frozen_week6.json"
    keep.parent.mkdir(parents=True, exist_ok=True)
    if not keep.exists():
        shutil.copy(FROZEN, keep)
    frozen = json.loads(FROZEN.read_text())
    frozen["fix_inflation"] = kappa
    frozen["gate_mode"] = gate
    frozen["design_freeze_week7"] = {
        "frozen": "2026-11-22, fitted on flight 05 (in-sample for the fix model), before the flight 10 check",
        "fix_inflation": f"kappa {kappa}: fix inlier sigma x kappa; mean NEES on 05 {nees[kappa]:.2f} "
                         "(grid 1.0..3.0, closest to 2, chi-square gate)",
        "gate_mode": f"{gate}: lowest mean RMSE over the four drift levels on 05 "
                     f"({', '.join(f'{g} {score[g]:.2f} m' for g in GATES)})",
        "results": "eval/results/week7/design_*.csv, design_05.md"}
    FROZEN.write_text(json.dumps(frozen, indent=2) + "\n")
    (OUT / "design_05.md").write_text("\n".join(lines))
    print("\n".join(lines))
    return 0


def check10() -> int:
    cfg = load_config()
    kappa, gate = cfg["fix_inflation"], cfg["gate_mode"]
    so = cfg["synthetic_odometry"]
    rows = run_grid("10", [(kappa, gate, lv, s) for lv in so["drift_levels_pct"] for s in range(so["seeds"])])
    write(rows, "design_check_10.csv")
    lines = [f"## Frozen design (kappa {kappa}, gate {gate}) on flight 10 (out-of-sample check)", "",
             "| Drift | RMSE [m] | NEES | cov 95 % |", "|---|---|---|---|"]
    for lv, v in per_level(rows, "rmse").items():
        rl = [r for r in rows if r["drift_pct"] == lv]
        lines.append(f"| {lv} % | {v:.1f} | {np.mean([r['nees'] for r in rl]):.2f} | "
                     f"{np.mean([r['cov95'] for r in rl]):.2f} |")
    lines += ["", f"Mean NEES {np.mean([r['nees'] for r in rows]):.2f}. Errors are against dataset labels and include "
              "label registration error; odometry is SYNTHETIC.", ""]
    (OUT / "design_check_10.md").write_text("\n".join(lines))
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    envcheck.require_reference_env(envcheck.FUSION)
    OUT.mkdir(parents=True, exist_ok=True)
    sys.exit({"fit": fit, "check10": check10}[sys.argv[1]]())
