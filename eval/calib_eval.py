#!/usr/bin/env python3
"""Week 5: evaluate the frozen error models on one flight (05 out-of-fold, or 10 with the frozen fit).

  /usr/bin/python3 eval/calib_eval.py 05   uses eval/results/week5/oof_05.csv (out-of-fold, honest)
  /usr/bin/python3 eval/calib_eval.py 10   uses calibration_frozen.json on features_10.csv (run ONCE)
Refuses flight 11. Per model role: NLL (mean, block-bootstrap 95 % CI, blocks of 15 frames), coverage
of the 50/90/95 % radii, ECE of P(wrong) (5 equal-count bins) with reliability table, AUC for wrong
fixes, AURC; risk-coverage of the old ratio gate (accept highest ratio first) vs P(wrong) gates;
the frozen validity states; effective sample size. Writes eval/results/week5/eval_<flight>.md/.json
and reliability_<flight>.png, risk_coverage_<flight>.png.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src/trn_calibration"))
import calib_metrics as cm  # noqa: E402
import envcheck  # noqa: E402
from trn_calibration.covariance import MixtureModel  # noqa: E402

RES = Path(__file__).parent / "results/week5"
FROZEN = Path(__file__).resolve().parents[1] / "src/trn_calibration/trn_calibration/calibration_frozen.json"
CUTS = FROZEN.with_name("validity_cuts.json")
ROLES = ["selected", "baseline_const", "baseline_ratio", "alt_robust"]
COLOURS = {"ratio gate (old)": "#eb6834", "selected": "#2a78d6", "alt_robust": "#eda100", "baseline_const": "#1baf7a"}
BLOCK = 15
THRESHOLDS = [0.08, 0.10, 0.15, 0.20, 0.30, 0.389]   # 0.389 = frozen t_publish


def load_predictions(flight: str, frozen: dict) -> tuple[list[dict], dict[str, dict[str, np.ndarray]], str]:
    feats = sorted(csv.DictReader((RES / f"features_{flight}.csv").open()), key=lambda r: int(r["frame"]))
    e = np.array([[float(r["e_e"]), float(r["e_n"])] for r in feats])
    preds = {}
    if flight == "05":
        oof = list(csv.DictReader((RES / "oof_05.csv").open()))
        for role in ROLES:
            by = {r["image"]: r for r in oof if r["role"] == role}
            preds[role] = {k: np.array([float(by[f["image"]][k]) for f in feats])
                           for k in ("nll", "p_wrong", "r50", "r90", "r95")}
        return feats, preds, "out-of-fold (block CV within 05)"
    for role in ROLES:
        spec = {k: v for k, v in frozen["models"][role].items() if k != "name"}
        m = MixtureModel(**spec)
        x = np.array([[float(r[f]) for f in m.features] for r in feats], float).reshape(len(feats), len(m.features))
        preds[role] = {"nll": m.nll(x, e), "p_wrong": m.p_wrong(x),
                       **{f"r{p}": m.radius(x, p / 100) for p in (50, 90, 95)}}
    return feats, preds, "frozen models fitted on 05 (out-of-sample check)"


def main() -> int:
    flight = sys.argv[1] if len(sys.argv) > 1 else "10"
    if flight == "11":
        print("refusing flight 11 (test)")
        return 2
    envcheck.require_reference_env()
    frozen = json.loads(FROZEN.read_text())
    feats, preds, source = load_predictions(flight, frozen)
    n = len(feats)
    err = np.array([float(r["err_m"]) for r in feats])
    wrong = np.array([int(r["wrong"]) for r in feats])
    ratio = np.array([float(r["ratio"]) for r in feats])
    accepted = np.array([int(r["accepted"]) for r in feats])
    neff = {"wrong": cm.n_eff(wrong), "log_err": cm.n_eff(np.log(err + 1))}
    res = {"flight": flight, "source": source, "n": n, "n_wrong": int(wrong.sum()), "n_eff": neff, "models": {}}
    lines = [f"## Flight {flight}: {source}", "",
             f"{n} frames with a candidate, {wrong.sum()} wrong (|e| > 50 m, {wrong.mean():.1%}); effective sample "
             f"size {neff['wrong']:.0f} (wrong indicator) / {neff['log_err']:.0f} (log error). 95 % intervals: "
             f"block bootstrap, blocks of {BLOCK} frames.", "",
             "| Model | NLL | Coverage 50 % | Coverage 90 % | Coverage 95 % | Sharpness: median 90 % radius [m] | "
             "ECE P(wrong) | AUC wrong | AURC |",
             "|---|---|---|---|---|---|---|---|---|"]
    for role in ROLES:
        p = preds[role]
        nll_ci = cm.block_bootstrap(lambda i: p["nll"][i].mean(), n, BLOCK)
        cov = {q: (float(np.mean(err <= p[f"r{q}"])),
                   cm.block_bootstrap(lambda i, q=q: np.mean(err[i] <= p[f"r{q}"][i]), n, BLOCK)) for q in (50, 90, 95)}
        e_ci = cm.block_bootstrap(lambda i: cm.ece(p["p_wrong"][i], wrong[i]), n, BLOCK)
        r = {"nll": float(p["nll"].mean()), "nll_ci": nll_ci, "coverage": cov, "ece": cm.ece(p["p_wrong"], wrong),
             "ece_ci": e_ci, "auc": cm.auc(p["p_wrong"], wrong), "aurc": cm.aurc(p["p_wrong"], wrong),
             "reliability": cm.reliability(p["p_wrong"], wrong), "sharpness_r90_m": float(np.median(p["r90"]))}
        res["models"][role] = r
        name = frozen["models"][role]["name"]
        lines.append(f"| {role} ({name}) | {r['nll']:.3f} [{nll_ci[0]:.3f}, {nll_ci[1]:.3f}] | "
                     + " | ".join(f"{cov[q][0]:.2f} [{cov[q][1][0]:.2f}, {cov[q][1][1]:.2f}]" for q in (50, 90, 95))
                     + f" | {r['sharpness_r90_m']:.1f} | {r['ece']:.3f} [{e_ci[0]:.3f}, {e_ci[1]:.3f}] | {r['auc']:.3f} | "
                     f"{r['aurc']:.3f} |")
    gate_aurc = cm.aurc(-ratio, wrong)
    res["ratio_gate_aurc"] = gate_aurc
    lines += ["", f"Old ratio gate (accept highest ratio first): AURC {gate_aurc:.3f}, AUC "
              f"{cm.auc(-ratio, wrong):.3f}. Frozen matcher gate (peak >= 0.2, ratio >= 1.2): accepts "
              f"{accepted.mean():.1%}, wrong among accepted {wrong[accepted == 1].mean() if accepted.any() else float('nan'):.1%}.",
              "", "Reliability of the selected model's P(wrong) (equal-count bins):", "",
              "| Bin | n | Mean predicted | Observed wrong rate | Range |", "|---|---|---|---|---|"]
    for k, b in enumerate(res["models"]["selected"]["reliability"]):
        lines.append(f"| {k + 1} | {b['n']} | {b['pred']:.3f} | {b['obs']:.3f} | {b['lo']:.3f}-{b['hi']:.3f} |")
    v = frozen["validity"]
    pw = preds["selected"]["p_wrong"]
    t_s, t_p = v["t_strong"], v["t_publish"]
    state = np.where((t_s is not None) & (pw <= (t_s if t_s is not None else -1)), "STRONG",
                     np.where(pw <= t_p, "UNCERTAIN", "DO_NOT_PUBLISH"))
    lines += ["", f"Frozen validity states (t_strong = {t_s}, t_publish = {t_p:.3f}):", "",
              "| State | Fraction of frames | Wrong rate | Coverage 95 % in state |", "|---|---|---|---|"]
    res["states"] = {}
    for s_ in ("STRONG", "UNCERTAIN", "DO_NOT_PUBLISH"):
        m = state == s_
        frac, wr = float(m.mean()), (float(wrong[m].mean()) if m.any() else float("nan"))
        c95 = float(np.mean(err[m] <= preds["selected"]["r95"][m])) if m.any() else float("nan")
        res["states"][s_] = {"fraction": frac, "wrong_rate": wr, "coverage95": c95}
        lines.append(f"| {s_} | {frac:.3f} | {wr:.3f} | {c95:.3f} |")
    cuts = json.loads(CUTS.read_text())
    t1, t2 = cuts["strong_max_p_wrong"], cuts["publish_max_p_wrong"]
    st2 = np.where(pw <= t1, "STRONG", np.where(pw <= t2, "UNCERTAIN", "DO_NOT_PUBLISH"))
    lines += ["", f"Validity cuts set 2026-11-21 (STRONG: P(wrong) <= {t1}, UNCERTAIN: <= {t2}, else DO_NOT_PUBLISH; "
              "STRONG cut chosen after the flight 10 curve had been seen):", "",
              "| State | Fraction of frames | Observed wrong rate | Coverage 90 % | Sharpness: median 90 % radius [m] |",
              "|---|---|---|---|---|"]
    res["states_cuts_2026_11_21"] = {}
    for s_ in ("STRONG", "UNCERTAIN", "DO_NOT_PUBLISH"):
        m = st2 == s_
        row = {"fraction": float(m.mean()), "wrong_rate": float(wrong[m].mean()) if m.any() else None,
               "coverage90": float(np.mean(err[m] <= preds["selected"]["r90"][m])) if m.any() else None,
               "sharpness_r90_m": float(np.median(preds["selected"]["r90"][m])) if m.any() else None}
        res["states_cuts_2026_11_21"][s_] = row
        lines.append(f"| {s_} | {row['fraction']:.3f} | " + (f"{row['wrong_rate']:.3f} | {row['coverage90']:.3f} | "
                     f"{row['sharpness_r90_m']:.1f} |" if m.any() else "- | - | - |"))
    lines += ["", "Risk-coverage at fixed acceptance (wrong rate among accepted):", "",
              "| Accepted | Ratio gate | P(wrong) selected | P(wrong) alt_robust |", "|---|---|---|---|"]
    curves = {"ratio gate (old)": cm.risk_coverage(-ratio, wrong), "selected": cm.risk_coverage(pw, wrong),
              "alt_robust": cm.risk_coverage(preds["alt_robust"]["p_wrong"], wrong)}
    for a in (0.1, 0.25, 0.5, 0.75, 0.9):
        k = max(1, int(round(a * n))) - 1
        lines.append(f"| {a:.0%} | " + " | ".join(f"{curves[c][2][k]:.3f}" for c in curves) + " |")
    lines += ["", "Candidate P(wrong) thresholds for the validity proposal (selected model; frames with "
              "P(wrong) <= t):", "", "| t | Fraction accepted | Wrong rate among accepted | Coverage 95 % among accepted |",
              "|---|---|---|---|"]
    res["threshold_table"] = []
    for t in THRESHOLDS:
        m = pw <= t
        row = {"t": t, "fraction": float(m.mean()), "wrong_rate": float(wrong[m].mean()) if m.any() else None,
               "coverage95": float(np.mean(err[m] <= preds["selected"]["r95"][m])) if m.any() else None}
        res["threshold_table"].append(row)
        lines.append(f"| {t:.3g} | {row['fraction']:.3f} | "
                     + (f"{row['wrong_rate']:.3f} | {row['coverage95']:.3f} |" if m.any() else "- | - |"))
    lines += ["", cm.LABEL_NOTE, ""]
    md = "\n".join(lines)
    (RES / f"eval_{flight}.md").write_text(md)
    (RES / f"eval_{flight}.json").write_text(json.dumps(res, indent=2, default=float) + "\n")
    print(md)
    plots(flight, res, curves, accepted, wrong)
    return 0


def plots(flight, res, curves, accepted, wrong) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(4.6, 4.2), dpi=130)
    ax.plot([0, 1], [0, 1], color="#999999", lw=1, ls="--", label="perfect calibration")
    for role in ("selected", "alt_robust", "baseline_const"):
        rel = res["models"][role]["reliability"]
        ax.plot([b["pred"] for b in rel], [b["obs"] for b in rel], marker="o", ms=6, lw=2, color=COLOURS[role],
                label=f"{role} (ECE {res['models'][role]['ece']:.3f})")
    ax.set_xlabel("predicted P(wrong)")
    ax.set_ylabel("observed wrong rate")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_title(f"Flight {flight}: reliability of P(|e| > 50 m)", fontsize=10)
    ax.grid(color="#e6e6e6", lw=0.8)
    ax.legend(frameon=False, fontsize=7, loc="upper left")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    fig.savefig(RES / f"reliability_{flight}.png", facecolor="white")
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(5.4, 4.0), dpi=130)
    for name in ("selected", "alt_robust", "ratio gate (old)"):   # dashed ratio gate on top: it can coincide
        _, frac, rate = curves[name]
        ax.step(frac, rate, where="post", lw=2, color=COLOURS[name], ls="--" if "gate" in name else "-",
                label=f"{name}, AURC {rate.mean():.3f}")
    if accepted.any():
        ax.plot([accepted.mean()], [wrong[accepted == 1].mean()], marker="D", ms=7, color="#333333", ls="none",
                label="frozen matcher gate")
    ax.set_xlabel("fraction of frames accepted")
    ax.set_ylabel("wrong rate among accepted (|e| > 50 m)")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, max(0.5, float(np.max([c[2].max() for c in curves.values()]))) * 1.05)
    ax.set_title(f"Flight {flight}: risk-coverage", fontsize=10)
    ax.grid(color="#e6e6e6", lw=0.8)
    ax.legend(frameon=False, fontsize=7, loc="upper left")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    fig.savefig(RES / f"risk_coverage_{flight}.png", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    sys.exit(main())
