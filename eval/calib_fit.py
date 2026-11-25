#!/usr/bin/env python3
"""Week 5: fit the fix-error model on the CALIBRATE flight (05) only, choose it by block CV, freeze it.

Rules, fixed before the first fit (2026-11-20):
  Data: eval/results/week5/features_05.csv (all frames with a candidate, frozen matcher), in frame
  order. Nothing from flight 11. Flight 10's LABELS are not used here; only its unlabelled feature
  distributions enter the shift preference below.
  Candidate models (feature sets, each with ridge lam in LAMS):
    M0 const         []
    M1 ratio         [log_ratio]
    M2 robust        [peak_z_norm, alt_dist_fp]
    M3 ratio+gap     [log_ratio, rel_gap]
    M4 robust+cover  [peak_z_norm, alt_dist_fp, overlap, edge_fp]
    M5 ratio+all     [log_ratio, rel_gap, overlap, edge_fp, at_bound]
    M6 peak+robust   [peak, peak_z_norm, alt_dist_fp, overlap, edge_fp]
  Model choice: K = 8 contiguous blocks of frames; out-of-fold NLL per frame.
    1. best = lowest mean CV NLL; eligible = models whose mean NLL difference to best (paired, frame
       by frame) is within 1 SE of that difference (SE = std of its 8 block means / sqrt 8);
       CHANGED 2026-11-20 after the first run: the declared rule used the unpaired SE of each
       model's own block means, which is dominated by terrain differences between blocks (about
       0.2 nats) and made all 13 models "eligible", so it picked the constant model by default.
       That output is kept in eval/results/week5/calib_fit_declared_rule_unpaired_se.txt;
    2. among eligible, smallest feature shift (max two-sample KS statistic, 05 vs 10, over the
       model's features; 0 for M0), then fewer features, then larger lam;
    3. separation check: if the chosen model's out-of-fold AUC for wrong fixes (|e| > 50 m) is
       below 0.65, the features cannot separate wrong from right: use M0 instead.
  Baselines, frozen alongside: M0 (constant) and M1 (ratio only), each with its best lam; also M2
  (shift-robust features) as a comparison, added after the first run, before any flight 10 check.
  Validity thresholds on the chosen model's predicted P(wrong), from its out-of-fold predictions
  on 05 (frames sorted by P(wrong), at least 20 accepted):
    STRONG          P(wrong) <= t_strong,  t_strong  = largest threshold with wrong rate <= 2 %
    UNCERTAIN       t_strong < P(wrong) <= t_publish, t_publish = largest with wrong rate <= 10 %
    DO_NOT_PUBLISH  P(wrong) > t_publish, or no candidate
  (wrong rate = among all frames up to that threshold; AGING is week 6, from fix age.)
Outputs: src/trn_calibration/trn_calibration/calibration_frozen.json (the frozen models and
thresholds), eval/results/week5/cv_models.csv, oof_05.csv (out-of-fold predictions of the chosen
model and both baselines), and a printed summary.

Usage: /usr/bin/python3 eval/calib_fit.py
"""
from __future__ import annotations

import csv
import datetime
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src/trn_calibration"))
import calib_metrics as cm  # noqa: E402
import envcheck  # noqa: E402
from trn_calibration.covariance import fit, WRONG_M  # noqa: E402

RES = Path(__file__).parent / "results/week5"
FROZEN = Path(__file__).resolve().parents[1] / "src/trn_calibration/trn_calibration/calibration_frozen.json"
MODELS = {"M0 const": [], "M1 ratio": ["log_ratio"], "M2 robust": ["peak_z_norm", "alt_dist_fp"],
          "M3 ratio+gap": ["log_ratio", "rel_gap"],
          "M4 robust+cover": ["peak_z_norm", "alt_dist_fp", "overlap", "edge_fp"],
          "M5 ratio+all": ["log_ratio", "rel_gap", "overlap", "edge_fp", "at_bound"],
          "M6 peak+robust": ["peak", "peak_z_norm", "alt_dist_fp", "overlap", "edge_fp"]}
LAMS = [1.0, 10.0]
K = 8
AUC_MIN = 0.65
STRONG_MAX_WRONG, PUBLISH_MAX_WRONG, MIN_ACCEPTED = 0.02, 0.10, 20


def load(path: Path) -> list[dict]:
    rows = list(csv.DictReader(path.open()))
    if any(r["split"] == "test" for r in rows):
        raise SystemExit("refusing the test split")
    return sorted(rows, key=lambda r: int(r["frame"]))


def arrays(rows: list[dict], feats: list[str]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    x = np.array([[float(r[f]) for f in feats] for r in rows], float).reshape(len(rows), len(feats))
    e = np.array([[float(r["e_e"]), float(r["e_n"])] for r in rows])
    return x, e, np.hypot(e[:, 0], e[:, 1]), np.array([int(r["wrong"]) for r in rows])


def oof(rows: list[dict], feats: list[str], lam: float) -> dict[str, np.ndarray]:
    """Out-of-fold predictions over K contiguous blocks."""
    x, e, err, wrong = arrays(rows, feats)
    n = len(rows)
    out = {k: np.zeros(n) for k in ("nll", "p_wrong", "sigma", "w", "r50", "r90", "r95")}
    out["block"] = np.zeros(n, int)
    for b, idx in enumerate(cm.contiguous_blocks(n, K)):
        train = np.setdiff1d(np.arange(n), idx)
        m = fit(x[train], e[train], feats, lam)
        sig, w, _ = m.predict(x[idx])
        out["nll"][idx] = m.nll(x[idx], e[idx])
        out["p_wrong"][idx] = m.p_wrong(x[idx])
        out["sigma"][idx], out["w"][idx] = sig, w
        for p in (50, 90, 95):
            out[f"r{p}"][idx] = m.radius(x[idx], p / 100)
        out["block"][idx] = b
    out["err"], out["wrong"] = err, wrong
    return out


def thresholds(p_wrong: np.ndarray, wrong: np.ndarray) -> dict:
    thr, frac, rate = cm.risk_coverage(p_wrong, wrong)
    res = {}
    for name, target in (("t_strong", STRONG_MAX_WRONG), ("t_publish", PUBLISH_MAX_WRONG)):
        ok = np.where((rate <= target) & (np.arange(1, len(rate) + 1) >= MIN_ACCEPTED))[0]
        res[name] = float(thr[ok[-1]]) if len(ok) else None
        res[name + "_accepted_frac_05"] = float(frac[ok[-1]]) if len(ok) else 0.0
        res[name + "_wrong_rate_05"] = float(rate[ok[-1]]) if len(ok) else None
    return res


def main() -> int:
    envcheck.require_reference_env()
    rows = load(RES / "features_05.csv")
    rows10 = list(csv.DictReader((RES / "features_10.csv").open()))   # features only, no labels used
    ks = {f: float(stats.ks_2samp([float(r[f]) for r in rows], [float(r[f]) for r in rows10]).statistic)
          for fs in MODELS.values() for f in fs}
    table, preds = [], {}
    for name, feats in MODELS.items():
        for lam in (LAMS if feats else [LAMS[0]]):
            o = oof(rows, feats, lam)
            blocks = [o["nll"][o["block"] == b].mean() for b in range(K)]
            row = {"model": name, "features": " ".join(feats) or "-", "lam": lam, "n_features": len(feats),
                   "cv_nll": float(o["nll"].mean()), "cv_nll_se": float(np.std(blocks, ddof=1) / np.sqrt(K)),
                   "cv_auc_wrong": cm.auc(o["p_wrong"], o["wrong"]), "cv_ece": cm.ece(o["p_wrong"], o["wrong"]),
                   "max_ks_05_vs_10": max((ks[f] for f in feats), default=0.0),
                   **{f"cv_cov{p}": float(np.mean(o["err"] <= o[f"r{p}"])) for p in (50, 90, 95)}}
            table.append(row)
            preds[(name, lam)] = o
            print(f"{name:16s} lam {lam:4g}: CV NLL {row['cv_nll']:.3f} +- {row['cv_nll_se']:.3f}, AUC "
                  f"{row['cv_auc_wrong']:.3f}, ECE {row['cv_ece']:.3f}, coverage 50/90/95 "
                  f"{row['cv_cov50']:.2f}/{row['cv_cov90']:.2f}/{row['cv_cov95']:.2f}, max KS "
                  f"{row['max_ks_05_vs_10']:.2f}", flush=True)
    best = min(table, key=lambda r: r["cv_nll"])
    nll_best = preds[(best["model"], best["lam"])]["nll"]
    blk = preds[(best["model"], best["lam"])]["block"]
    for r in table:
        d = preds[(r["model"], r["lam"])]["nll"] - nll_best
        r["cv_nll_diff_vs_best"] = float(d.mean())
        r["cv_nll_diff_se"] = float(np.std([d[blk == b].mean() for b in range(K)], ddof=1) / np.sqrt(K))
    eligible = [r for r in table if r["cv_nll_diff_vs_best"] <= r["cv_nll_diff_se"]]
    chosen = min(eligible, key=lambda r: (r["max_ks_05_vs_10"], r["n_features"], -r["lam"]))
    note = ""
    if chosen["n_features"] and chosen["cv_auc_wrong"] < AUC_MIN:
        note = f"chosen model's CV AUC {chosen['cv_auc_wrong']:.3f} < {AUC_MIN}: features cannot separate; using M0"
        chosen = next(r for r in table if r["model"] == "M0 const")
    best_of = lambda name: min((r for r in table if r["model"] == name), key=lambda r: r["cv_nll"])  # noqa: E731
    roles = {"selected": chosen, "baseline_const": best_of("M0 const"), "baseline_ratio": best_of("M1 ratio"),
             "alt_robust": best_of("M2 robust")}   # shift-robust comparison only; not used for selection
    print(f"\nbest CV NLL: {best['model']} lam {best['lam']:g} ({best['cv_nll']:.3f} +- {best['cv_nll_se']:.3f}); "
          f"paired differences to best: {[(r['model'], r['lam'], round(r['cv_nll_diff_vs_best'], 3), round(r['cv_nll_diff_se'], 3)) for r in table]}\n"
          f"eligible within 1 paired SE: {[(r['model'], r['lam']) for r in eligible]}\nchosen: {chosen['model']} lam "
          f"{chosen['lam']:g} {note}")

    o_sel = preds[(chosen["model"], chosen["lam"])]
    thr = thresholds(o_sel["p_wrong"], o_sel["wrong"])
    d_nll = preds[(chosen["model"], chosen["lam"])]["nll"] - preds[("M0 const", LAMS[0])]["nll"]
    ci = cm.block_bootstrap(lambda i: d_nll[i].mean(), len(d_nll), 15)
    neff = {"wrong": cm.n_eff(o_sel["wrong"]), "nll": cm.n_eff(o_sel["nll"])}
    print(f"validity thresholds (05 out-of-fold): {thr}\nCV NLL difference chosen - const: {d_nll.mean():+.3f} "
          f"(block-bootstrap 95 % CI {ci[0]:+.3f}..{ci[1]:+.3f}); n = {len(rows)}, n_eff wrong {neff['wrong']:.0f}, "
          f"nll {neff['nll']:.0f}")

    x_all = {name: arrays(rows, MODELS[r["model"]]) for name, r in roles.items()}
    frozen = {"frozen": datetime.date.today().isoformat() + ", fitted on flight 05 (calibrate) only; "
                                                             "before any evaluation on flight 10",
              "git_commit_at_fit": subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                                                  text=True, cwd=Path(__file__).parent).stdout.strip(),
              "wrong_m": WRONG_M, "data": "eval/results/week5/features_05.csv (frozen matcher, 473 frames)",
              "note": "errors are against dataset labels: the predicted uncertainty includes label registration "
                      "error and is not uncertainty about the true position",
              "selection": {"rule": "lowest CV NLL; eligible = within 1 paired SE of the best (changed from the "
                                    "unpaired SE after the first run, see docs/log.md); then the smallest "
                                    "05-vs-10 feature shift, fewer features, larger lam; AUC < 0.65 -> constant",
                            "chosen": chosen["model"],
                            "lam": chosen["lam"], "best_cv": best["model"], "override_note": note,
                            "cv_nll_diff_vs_const": float(d_nll.mean()), "cv_nll_diff_ci95": list(ci),
                            "n_frames": len(rows), "n_eff": neff},
              "validity": {**thr, "rule": f"STRONG: P(wrong) <= t_strong (wrong <= {STRONG_MAX_WRONG:.0%} on 05 "
                                          f"out-of-fold); UNCERTAIN: <= t_publish (<= {PUBLISH_MAX_WRONG:.0%}); "
                                          "DO_NOT_PUBLISH otherwise or without a candidate"},
              "models": {}}
    for role, r in roles.items():
        x, e, _, _ = x_all[role]
        m = fit(x, e, MODELS[r["model"]], r["lam"])
        frozen["models"][role] = {"name": r["model"], **m.to_dict()}
    FROZEN.write_text(json.dumps(frozen, indent=2) + "\n")
    with (RES / "cv_models.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(table[0]))
        w.writeheader()
        w.writerows(table)
    with (RES / "oof_05.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["image", "frame", "err_m", "wrong", "role", "nll", "p_wrong", "sigma", "w", "r50", "r90", "r95"])
        for role, r in roles.items():
            o = preds[(r["model"], r["lam"])]
            for i, row in enumerate(rows):
                w.writerow([row["image"], row["frame"], round(o["err"][i], 3), o["wrong"][i], role,
                            *(round(float(o[k][i]), 5) for k in ("nll", "p_wrong", "sigma", "w", "r50", "r90", "r95"))])
    print(f"wrote {FROZEN}, {RES / 'cv_models.csv'}, {RES / 'oof_05.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
