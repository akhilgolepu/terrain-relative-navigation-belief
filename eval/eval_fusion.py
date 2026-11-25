#!/usr/bin/env python3
"""Week 6: fused belief vs odometry-only vs fixes-only, per flight and SYNTHETIC drift level.

Odometry is SYNTHETIC (label-path increments + floor/random-walk drift, trn_fusion.odometry_sim);
fixes are the frozen matcher's accept-all candidates (eval/results/week6/inputs_<flight>.csv).
For each drift level in fusion_frozen.json and each seed:
  fused         trn_fusion.core.FusionCore (iSAM2, mixture fixes, 9 s thinning, chi-square gate)
  odometry-only dead reckoning from the first-frame prior, covariance prior + matched odometry noise
  fixes-only    the raw candidate fixes (no odometry, no gate)
Metrics against the LABELS (which include label registration error): ATE RMSE / median / p95
over all frames; NEES (mean of e^T P^-1 e, 2 if consistent) and coverage of the 95 % ellipse
(e^T P^-1 e <= 5.991) for fused and odometry-only; validity state shares; error and coverage on
published frames (not DO_NOT_PUBLISH); fix counts (candidates, thinned, gated, fused, explained as
outlier at the end); update latency. Also a fix-outage scenario (fixes stop after 30 % of the
frames) to show AGING and DO_NOT_PUBLISH.
Runs in the venv (GTSAM); envcheck against eval/reference_env_fusion.json. Refuses flight 11.

Usage: env -u PYTHONPATH ~/venvs/trn/bin/python eval/eval_fusion.py 10 [--seeds 20]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/trn_fusion"))
sys.path.insert(0, str(ROOT / "src/trn_calibration"))
import envcheck  # noqa: E402
from trn_fusion import validity  # noqa: E402
from trn_fusion.core import FusionCore, load_config  # noqa: E402
from trn_fusion.fix_factor import FixModel  # noqa: E402
from trn_fusion.odometry_sim import drift_b, simulate, step_sigma  # noqa: E402

RES = Path(__file__).parent / "results/week6"
NOTE = ("Errors are against dataset labels and include label registration error; odometry is SYNTHETIC "
        "(label path + sampled drift).")
CHI2_95 = 5.991


def load_inputs(flight: str) -> dict:
    rows = list(csv.DictReader((RES / f"inputs_{flight}.csv").open()))
    return {"labels": np.array([[float(r["true_e"]), float(r["true_n"])] for r in rows]),
            "t": np.array([float(r["t_s"]) for r in rows]),
            "prior0": np.array([float(rows[0]["prior_e"]), float(rows[0]["prior_n"])]),
            "has": np.array([int(r["has_fix"]) for r in rows], bool),
            "z": np.array([[float(r["fix_e"]), float(r["fix_n"])] if int(r["has_fix"]) else [np.nan, np.nan]
                           for r in rows]),
            "lr": np.array([float(r["log_ratio"]) if int(r["has_fix"]) else np.nan for r in rows]),
            "region": rows[0]["region"]}


def run_fused(inp: dict, odo: np.ndarray, b: float, cfg: dict, fm: FixModel, fixes_until: int | None = None):
    core = FusionCore(cfg, fm, b=b)
    n = len(odo)
    mean, cov, state, age = np.zeros((n, 2)), np.zeros((n, 2, 2)), np.zeros(n, int), np.full(n, np.nan)
    sigma0 = cfg["prior"]["sigma_m"]
    core.frame_s = []
    for k in range(n):
        t_frame = time.perf_counter()
        if k == 0:
            core.start(inp["t"][0], inp["prior0"], sigma0)
        else:
            core.odometry(inp["t"][k], odo[k] - odo[k - 1])
        if inp["has"][k] and (fixes_until is None or k < fixes_until):
            core.fix(inp["t"][k], inp["z"][k], inp["lr"][k])
        bel = core.belief()
        mean[k], cov[k], state[k] = bel.mean, bel.cov, bel.validity
        age[k] = np.nan if bel.fix_age_s is None else bel.fix_age_s
        core.frame_s.append(time.perf_counter() - t_frame)
    return mean, cov, state, age, core


def run_odometry_only(inp: dict, odo: np.ndarray, b: float, a: float, sigma0: float):
    est = inp["prior0"] + (odo - odo[0])
    var = sigma0 ** 2 + np.r_[0.0, np.cumsum([step_sigma(u, b, a) ** 2 for u in np.diff(odo, axis=0)])]
    return est, var[:, None, None] * np.eye(2)[None]


def err_stats(err: np.ndarray) -> dict:
    return {"rmse": float(np.sqrt(np.mean(err ** 2))), "median": float(np.median(err)),
            "p95": float(np.percentile(err, 95))}


def nees(e: np.ndarray, cov: np.ndarray) -> np.ndarray:
    return np.einsum("ni,nij,nj->n", e, np.linalg.inv(cov), e)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("flight", choices=["10", "05"])
    ap.add_argument("--seeds", type=int, default=None)
    ap.add_argument("--out", type=Path, default=RES, help="output folder (inputs are always read from week6)")
    args = ap.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    envcheck.require_reference_env(envcheck.FUSION)
    cfg = load_config()
    fm = FixModel()
    inp = load_inputs(args.flight)
    lab = inp["labels"]
    so = cfg["synthetic_odometry"]
    seeds = args.seeds or so["seeds"]
    a = so["floor_a_m"]
    fix_err = np.hypot(*(inp["z"][inp["has"]] - lab[inp["has"]]).T)
    rows, keep = [], {}
    for li, level in enumerate(so["drift_levels_pct"]):
        b = drift_b(level, so["reference_distance_m"])
        for s in range(seeds):
            odo = simulate(lab, b, a, seed=1000 * li + s)
            t0 = time.perf_counter()
            mean, cov, state, age, core = run_fused(inp, odo, b, cfg, fm)
            wall = time.perf_counter() - t0
            e_f = mean - lab
            d2f = nees(e_f, cov)
            est_o, cov_o = run_odometry_only(inp, odo, b, a, cfg["prior"]["sigma_m"])
            e_true_start = np.hypot(*((lab[0] + (odo - odo[0])) - lab).T)   # dead reckoning from the TRUE start
            e_o = est_o - lab
            d2o = nees(e_o, cov_o)
            pub = state != validity.DO_NOT_PUBLISH
            ef, eo = np.hypot(*e_f.T), np.hypot(*e_o.T)
            row = {"flight": args.flight, "drift_pct": level, "seed": s,
                   **{f"fused_{k}": v for k, v in err_stats(ef).items()},
                   **{f"odo_{k}": v for k, v in err_stats(eo).items()},
                   **{f"odotrue_{k}": v for k, v in err_stats(e_true_start).items()},
                   **{f"fixes_{k}": v for k, v in err_stats(fix_err).items()},
                   "fused_nees": float(d2f.mean()), "fused_cov95": float(np.mean(d2f <= CHI2_95)),
                   "odo_nees": float(d2o.mean()), "odo_cov95": float(np.mean(d2o <= CHI2_95)),
                   **{f"state_{validity.NAMES[v]}": float(np.mean(state == v)) for v in validity.NAMES},
                   "published_median": float(np.median(ef[pub])) if pub.any() else float("nan"),
                   "published_cov95": float(np.mean(d2f[pub] <= CHI2_95)) if pub.any() else float("nan"),
                   "candidates": core.count.candidates, "thinned": core.count.thinned,
                   "gated": core.count.gated, "fused": core.count.fused,
                   "outlier_share": core.outlier_share(),
                   "update_ms_median": 1000 * float(np.median(core.frame_s)),
                   "update_ms_p95": 1000 * float(np.percentile(core.frame_s, 95)),
                   "isam_update_ms_median": 1000 * float(np.median(core.count.update_s)),
                   "wall_s": wall}
            rows.append(row)
            if s == 0:
                keep[level] = (mean, cov, state, est_o, cov_o)
            print(f"flight {args.flight} drift {level}% seed {s}: fused RMSE {row['fused_rmse']:.1f} m, odo "
                  f"{row['odo_rmse']:.1f} m, fixes {row['fixes_rmse']:.1f} m; NEES {row['fused_nees']:.2f}; "
                  f"fused {row['fused']}/{row['candidates']} (gated {row['gated']})", flush=True)
    out_csv = out / f"fusion_{args.flight}.csv"
    with out_csv.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    md = summary(args.flight, rows, inp)
    # fix outage: fixes stop after 30 % of the frames (declared: 1 % drift; 2 % added after the first
    # development run showed that 1 % does not reach DO_NOT_PUBLISH within flight 10)
    n = len(lab)
    cut = int(0.3 * n)
    md += f"\n### Fix outage: fixes stop at frame {cut} (t = {inp['t'][cut]:.0f} s), seed 0\n\n"
    for level in (1.0, 2.0):
        bl = drift_b(level, so["reference_distance_m"])
        odo = simulate(lab, bl, a, seed=1000 * so["drift_levels_pct"].index(level))
        m_out, c_out, s_out, _, _ = run_fused(inp, odo, bl, cfg, fm, fixes_until=cut)
        after = np.arange(n) >= cut
        first = {validity.NAMES[v]: (float(inp["t"][np.argmax((s_out == v) & after)])
                                     if np.any((s_out == v) & after) else None)
                 for v in (validity.AGING, validity.DO_NOT_PUBLISH)}
        e_cut = np.hypot(*(m_out - lab).T)
        sig = np.array([validity.major_sigma(c) for c in c_out])
        inside = float(np.mean(e_cut[after] <= 2 * sig[after]))
        md += (f"- {level} % drift: first AGING at t = {first['AGING']} s, first DO_NOT_PUBLISH at t = "
               f"{first['DO_NOT_PUBLISH']} s; at the end error {e_cut[-1]:.0f} m, 1-sigma {sig[-1]:.0f} m; error "
               f"inside the 2-sigma band on {inside:.0%} of the outage frames.\n")
        timeline(args.flight, inp, (m_out, c_out, s_out, None, None),
                 out / f"timeline_{args.flight}_outage_{level:g}pct.png",
                 f"{level:g} % drift, seed 0, fixes stop at t = {inp['t'][cut]:.0f} s", cut_t=inp["t"][cut])
    md += f"\n{NOTE}\n"
    (out / f"fusion_{args.flight}.md").write_text(md)
    print(md)
    timeline(args.flight, inp, keep[1.0], out / f"timeline_{args.flight}_drift1pct.png", "1 % drift, seed 0")
    return 0


def summary(flight: str, rows: list[dict], inp: dict) -> str:
    cfg = load_config()
    lines = [f"## Flight {flight}: fused vs odometry-only vs fixes-only (mean over seeds [p5, p95]); design: "
             f"fix_inflation {cfg.get('fix_inflation', 1.0)}, gate {cfg.get('gate_mode', 'chi2_inlier')}", "",
             "| Drift | Fused ATE RMSE | Fused median | Odometry-only RMSE (from prior) | Odometry-only RMSE from TRUE "
             "start (oracle) | Fixes-only RMSE / median | Fused NEES "
             "(2 = consistent) | Fused cov 95 % | Odo cov 95 % | Published share | Published median | "
             "Published cov 95 % | Fixes fused / gated / thinned (of candidates) | Outlier share | Per-frame "
             "latency ms (median / p95: odometry + fix + belief) |", "|" + "---|" * 15]
    for level in sorted({r["drift_pct"] for r in rows}):
        rs = [r for r in rows if r["drift_pct"] == level]

        def m(k, fmt="{:.1f}"):
            v = np.array([r[k] for r in rs], float)
            return fmt.format(np.nanmean(v)) + " [" + fmt.format(np.nanpercentile(v, 5)) + ", " + \
                fmt.format(np.nanpercentile(v, 95)) + "]"
        pub = 1 - np.mean([r["state_DO_NOT_PUBLISH"] for r in rs])
        lines.append(f"| {level} % | {m('fused_rmse')} | {m('fused_median')} | {m('odo_rmse')} | {m('odotrue_rmse')} | "
                     f"{rs[0]['fixes_rmse']:.1f} / {rs[0]['fixes_median']:.1f} | {m('fused_nees', '{:.2f}')} | "
                     f"{m('fused_cov95', '{:.2f}')} | {m('odo_cov95', '{:.2f}')} | {pub:.2f} | "
                     f"{m('published_median')} | {m('published_cov95', '{:.2f}')} | "
                     f"{np.mean([r['fused'] for r in rs]):.0f} / {np.mean([r['gated'] for r in rs]):.0f} / "
                     f"{np.mean([r['thinned'] for r in rs]):.0f} ({rs[0]['candidates']}) | "
                     f"{np.nanmean([r['outlier_share'] for r in rs]):.2f} | "
                     f"{np.mean([r['update_ms_median'] for r in rs]):.2f} / "
                     f"{np.mean([r['update_ms_p95'] for r in rs]):.2f} |")
    lines += ["", "State shares (mean over seeds):", "", "| Drift | STRONG | AGING | UNCERTAIN | DO_NOT_PUBLISH |",
              "|---|---|---|---|---|"]
    for level in sorted({r["drift_pct"] for r in rows}):
        rs = [r for r in rows if r["drift_pct"] == level]
        lines.append(f"| {level} % | " + " | ".join(f"{np.mean([r['state_' + s] for r in rs]):.2f}"
                                                   for s in ("STRONG", "AGING", "UNCERTAIN", "DO_NOT_PUBLISH")) + " |")
    lines += ["", f"{len(inp['labels'])} frames; ATE over all frames. {NOTE}", ""]
    return "\n".join(lines)


def timeline(flight, inp, run, path, title, cut_t=None) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    mean, cov, state, est_o, _ = run
    t, lab = inp["t"], inp["labels"]
    err = np.hypot(*(mean - lab).T)
    sig = np.array([validity.major_sigma(c) for c in cov])
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(8, 4.8), dpi=130, sharex=True, gridspec_kw={"height_ratios": [4, 1]})
    ax.fill_between(t, 0, 2 * sig, color="#2a78d6", alpha=0.15, lw=0, label="2-sigma (major axis)")
    ax.plot(t, err, color="#2a78d6", lw=2, label="fused error vs label")
    if est_o is not None:
        ax.plot(t, np.hypot(*(est_o - lab).T), color="#eb6834", lw=2, ls="--", label="odometry-only error")
    if cut_t is not None:
        ax.axvline(cut_t, color="#555555", lw=1, ls=":")
        ax.text(cut_t, ax.get_ylim()[1] * 0.95, " fixes stop", fontsize=7, va="top")
    ax.set_ylabel("position error [m]")
    ax.set_title(f"Flight {flight}: {title}. SYNTHETIC odometry; errors vs labels (incl. label error)", fontsize=9)
    ax.grid(color="#e6e6e6", lw=0.8)
    ax.legend(frameon=False, fontsize=7, loc="upper left")
    colours = {validity.STRONG: "#1baf7a", validity.UNCERTAIN: "#eda100", validity.AGING: "#e87ba4",
               validity.DO_NOT_PUBLISH: "#e34948"}
    for v, c in colours.items():
        m = state == v
        ax2.scatter(t[m], np.full(m.sum(), v), s=6, color=c, label=validity.NAMES[v])
    ax2.set_yticks(list(colours))
    ax2.set_yticklabels([validity.NAMES[v] for v in colours], fontsize=6)
    ax2.set_xlabel("time [s]")
    for a_ in (ax, ax2):
        for side in ("top", "right"):
            a_.spines[side].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    sys.exit(main())
