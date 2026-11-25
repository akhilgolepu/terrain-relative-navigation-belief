#!/usr/bin/env python3
"""Fit a VIO drift model: translation RPE RMSE as a function of segment length delta.

Data: <run>_rpe_vs_delta.csv of the DISTINCT runs (vio_run_identity.csv; byte-identical repeats count once), segment
lengths <= --max-delta-m (default 20 m; longer segments are too few per run), pooled over runs and sequences.
The RPE files must come from score_vio.py with the start-up skip in force (skip_start_s is copied into the output).

Candidate models (e and delta in metres):
  power      e = c * delta^p                          c [m^(1-p)], p [-]
  threeterm  e = sqrt(a^2 + b * delta + (c * delta)^2) a [m] (noise floor), b [m] (random-walk-like growth,
                                                       b*delta is m^2), c [-] (error per metre travelled)
  floorwalk  e = sqrt(a^2 + b * delta)                 the three-term model with c fixed at 0 (noise floor plus
                                                       random walk); a [m], b [m]
All models are fitted to the same n points, so their AICc values are directly comparable.
Fit: scipy.optimize.curve_fit on e (not log e), parameters bounded >= 0 (p in [0, 2]), each point weighted by the
approximate standard error of an RMSE over n segments, sigma = e / sqrt(2 n) (relative sigma, absolute_sigma=False),
so a value from 130 one-metre segments counts more than one from 6 twenty-metre segments.
Comparison:
  - weighted residual sum of squares (chi2) and AICc (small-sample Akaike criterion, Gaussian likelihood),
  - RMS of log residuals log(e_fit / e_obs) (unweighted, scale-free),
  - leave-one-sequence-out: fit on all runs of one sequence, RMS log residual on the other (whole sequences held
    out, never single segments).
Selection: the power law, unless another model is clearly better: AICc lower by more than 2 AND a lower
leave-one-sequence-out RMS log residual (pooled over both held-out sequences); if several are, the lowest AICc.
Sensitivity (power law only, reported, not used for selection): c and p with equal weights per point, and with each
distinct run left out in turn.

Writes RESULTS/drift_params.json (parameters with standard errors and units, method, fitted range, inputs with
SHA-256, scoring/alignment settings incl. skip_start_s, comparison, choice and reason, sensitivity, and a note on
use) and RESULTS/drift_fit.png.
Indoor TUM VI room sequences only (small loops, < 150 m each, public data): not a flight drift model.

Usage (in ~/venvs/trn): python eval/fit_drift_model.py eval/results/vio [--max-delta-m 20]
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
from scipy.optimize import curve_fit

from drift_data import RpePoints, distinct_runs, file_sha256, load_rpe_points, plot_rpe_vs_delta, scoring_settings

AICC_MARGIN = 2.0  # another model must beat the power law's AICc by more than this
NOTE_WEEK6 = ("The power law describes this indoor data (RPE RMSE vs segment length on TUM VI room1/room2). It is not "
              "the drift generator for week 6 synthetic odometry; that generator is a separate decision.")


def power(delta: np.ndarray, c: float, p: float) -> np.ndarray:
    return c * delta ** p


def threeterm(delta: np.ndarray, a: float, b: float, c: float) -> np.ndarray:
    return np.sqrt(a ** 2 + b * delta + (c * delta) ** 2)


def floorwalk(delta: np.ndarray, a: float, b: float) -> np.ndarray:
    return np.sqrt(a ** 2 + b * delta)


@dataclass
class ModelSpec:
    name: str
    f: Callable[..., np.ndarray]
    params: tuple[str, ...]
    units: dict[str, str]
    formula: str
    p0: Callable[[np.ndarray, np.ndarray], list[float]]
    bounds: tuple[list[float], list[float]]


MODELS = {
    "power": ModelSpec("power", power, ("c", "p"), {"c": "m^(1-p)", "p": "dimensionless"}, "e = c * delta^p",
                       lambda d, e: [float(e[np.argmin(d)]), 0.5], ([0.0, 0.0], [np.inf, 2.0])),
    "threeterm": ModelSpec("threeterm", threeterm, ("a", "b", "c"),
                           {"a": "m", "b": "m (b * delta in m^2)", "c": "dimensionless (m per m)"},
                           "e = sqrt(a^2 + b * delta + (c * delta)^2)",
                           lambda d, e: [float(0.5 * e[np.argmin(d)]), float(np.median(e ** 2 / d)), 0.001],
                           ([0.0, 0.0, 0.0], [np.inf, np.inf, np.inf])),
    "floorwalk": ModelSpec("floorwalk", floorwalk, ("a", "b"), {"a": "m", "b": "m (b * delta in m^2)"},
                           "e = sqrt(a^2 + b * delta)",
                           lambda d, e: [float(0.5 * e[np.argmin(d)]), float(np.median(e ** 2 / d))],
                           ([0.0, 0.0], [np.inf, np.inf])),
}


@dataclass
class Fit:
    model: str
    values: dict[str, float]
    std_errors: dict[str, float]
    chi2: float
    aicc: float
    rms_log_residual: float
    n_points: int
    at_bound: list[str]  # parameters within 1e-9 (relative) of a bound: their standard error is not meaningful


def pool(points: list[RpePoints]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Pooled (delta, rmse, sigma) over runs; sigma = rmse / sqrt(2 n_segments)."""
    d = np.concatenate([p.delta_m for p in points])
    e = np.concatenate([p.rmse_m for p in points])
    n = np.concatenate([p.n_segments for p in points]).astype(float)
    return d, e, e / np.sqrt(2.0 * n)


def aicc(chi2: float, n: int, k: int) -> float:
    """AICc for least squares with unknown common error scale: n ln(chi2/n) + 2k + 2k(k+1)/(n-k-1)."""
    if n - k - 1 <= 0:
        return float("inf")
    if chi2 <= 0:  # exact fit (noise-free synthetic data only)
        return float("-inf")
    return n * np.log(chi2 / n) + 2 * k + 2 * k * (k + 1) / (n - k - 1)


def rms_log_residual(spec: ModelSpec, values: dict[str, float], d: np.ndarray, e: np.ndarray) -> float:
    pred = spec.f(d, *[values[k] for k in spec.params])
    return float(np.sqrt(np.mean(np.log(pred / e) ** 2)))


def fit_model(spec: ModelSpec, points: list[RpePoints], weights: str = "segments") -> Fit:
    """weights: "segments" (sigma = e / sqrt(2 n), the default) or "equal" (every point the same weight)."""
    d, e, sigma = pool(points)
    if weights == "equal":
        sigma = np.ones_like(e)
    elif weights != "segments":
        raise ValueError(f"unknown weights {weights!r}")
    popt, pcov = curve_fit(spec.f, d, e, p0=spec.p0(d, e), sigma=sigma, absolute_sigma=False,
                           bounds=spec.bounds, maxfev=20000)
    values = dict(zip(spec.params, map(float, popt)))
    errs = dict(zip(spec.params, map(float, np.sqrt(np.diag(pcov)))))
    chi2 = float(np.sum(((spec.f(d, *popt) - e) / sigma) ** 2))
    lo, hi = spec.bounds
    at_bound = [k for k, v, l, h in zip(spec.params, popt, lo, hi)
                if abs(v - l) <= 1e-9 * max(1.0, abs(l)) or (np.isfinite(h) and abs(v - h) <= 1e-9 * max(1.0, abs(h)))]
    return Fit(spec.name, values, errs, chi2, aicc(chi2, len(d), len(spec.params)),
               rms_log_residual(spec, values, d, e), len(d), at_bound)


def leave_one_sequence_out(spec: ModelSpec, points: list[RpePoints]) -> dict[str, float]:
    """Fit on every sequence but one, RMS log residual on the held-out one; plus 'pooled' over all held-out points."""
    out, sq, count = {}, 0.0, 0
    for held in sorted({p.sequence for p in points}):
        train = [p for p in points if p.sequence != held]
        test = [p for p in points if p.sequence == held]
        fit = fit_model(spec, train)
        d, e, _ = pool(test)
        r = rms_log_residual(spec, fit.values, d, e)
        out[f"held_out_{held}"] = r
        sq, count = sq + r ** 2 * len(d), count + len(d)
    out["pooled"] = float(np.sqrt(sq / count))
    return out


def choose(fits: dict[str, Fit], loso: dict[str, dict[str, float]]) -> tuple[str, str]:
    """Power law unless another model wins on AICc by > AICC_MARGIN and on held-out residual (then lowest AICc)."""
    pw, lo_pw = fits["power"], loso["power"]["pooled"]
    others = [n for n in fits if n != "power"]
    assert all(fits[n].n_points == pw.n_points for n in others), "AICc needs the same points for every model"
    better = [n for n in others if pw.aicc - fits[n].aicc > AICC_MARGIN and loso[n]["pooled"] < lo_pw]
    if better:
        n = min(better, key=lambda k: fits[k].aicc)
        return n, (f"The {n} model is clearly better than the power law: its AICc is {pw.aicc - fits[n].aicc:.1f} lower "
                   f"(margin {AICC_MARGIN:g}, n = {pw.n_points}) and its held-out-sequence RMS log residual is lower "
                   f"({loso[n]['pooled']:.3f} vs {lo_pw:.3f}).")
    why = [f"{n}: AICc difference {pw.aicc - fits[n].aicc:+.1f} (power minus {n}; needs > {AICC_MARGIN:g}), held-out "
           f"RMS log residual {loso[n]['pooled']:.3f} vs {lo_pw:.3f} power" for n in others]
    return "power", (f"The power law is kept because no other model is clearly better (n = {pw.n_points} for all): "
                     + "; ".join(why) + ".")


def power_sensitivity(points: list[RpePoints]) -> list[dict[str, object]]:
    """Power-law c and p under: the default fit, equal weights per point, and each distinct run left out in turn."""
    spec = MODELS["power"]
    variants: list[tuple[str, list[RpePoints], str]] = [("baseline (segment weights, all runs)", points, "segments"),
                                                         ("equal weights per point", points, "equal")]
    variants += [(f"without {p.run}", [q for q in points if q.run != p.run], "segments") for p in points]
    out = []
    for label, pts, weights in variants:
        f = fit_model(spec, pts, weights)
        out.append({"variant": label, "weights": weights, "runs": [q.run for q in pts], "n_points": f.n_points,
                    "c": f.values["c"], "c_std_error": f.std_errors["c"],
                    "p": f.values["p"], "p_std_error": f.std_errors["p"]})
    return out


def build_params(results: Path, points: list[RpePoints], fits: dict[str, Fit], loso: dict[str, dict[str, float]],
                 chosen: str, reason: str, max_delta_m: float, sensitivity: list[dict[str, object]]) -> dict:
    d, _, _ = pool(points)
    return {
        "chosen_model": chosen,
        "reason": reason,
        "note": NOTE_WEEK6,
        "models": {name: {"formula": MODELS[name].formula, "parameters": fits[name].values,
                          "std_errors": fits[name].std_errors, "units": MODELS[name].units,
                          "parameters_at_bound": fits[name].at_bound,
                          "n_points": fits[name].n_points, "chi2_weighted": fits[name].chi2, "aicc": fits[name].aicc,
                          "aicc_minus_power": fits[name].aicc - fits["power"].aicc,
                          "rms_log_residual": fits[name].rms_log_residual,
                          "leave_one_sequence_out_rms_log_residual": loso[name]} for name in fits},
        "quantity": "translation RPE RMSE [m] over segments of delta metres",
        "units": {"delta": "m, path length along the ESTIMATE's path (evo pairs_from_reference=False)",
                  "e": "m, RMSE of translation RPE over all non-overlapping segments of that length"},
        "method": {"fit": "scipy.optimize.curve_fit on e (not log e), bounds: all parameters >= 0, power p <= 2",
                   "weights": "sigma = e / sqrt(2 n_segments), relative (absolute_sigma=False)",
                   "pooling": "all distinct runs and sequences pooled, one point per run and segment length",
                   "comparison": "weighted chi2, AICc, RMS log residual, leave-one-sequence-out RMS log residual",
                   "selection": f"power unless another model has AICc lower by > {AICC_MARGIN:g} (same n) and a lower "
                                "held-out residual; if several, the lowest AICc"},
        "fitted_range": {"delta_min_m": float(d.min()), "delta_max_m": float(d.max()), "max_delta_m": max_delta_m,
                         "n_points": int(len(d)), "segment_lengths_m": sorted({float(x) for x in d})},
        "runs": [p.run for p in points],
        "inputs": {p.run: {"file": str(p.source), "sha256": file_sha256(p.source)} for p in points},
        "scoring_settings": scoring_settings(results),
        "scope": "TUM VI room1/room2 (indoor, small loops, < 150 m per sequence), OpenVINS shipped tum_vi config, "
                 "public data replayed at 1x; not flight data. Extrapolation beyond the fitted range is untested.",
        "sensitivity_power": sensitivity,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("results", type=Path)
    ap.add_argument("--max-delta-m", type=float, default=20.0, help="longest segment length used in the fit [m]")
    args = ap.parse_args()

    points = [load_rpe_points(args.results, run, args.max_delta_m) for run in distinct_runs(args.results)]
    fits = {name: fit_model(spec, points) for name, spec in MODELS.items()}
    loso = {name: leave_one_sequence_out(spec, points) for name, spec in MODELS.items()}
    chosen, reason = choose(fits, loso)
    sens = power_sensitivity(points)
    params = build_params(args.results, points, fits, loso, chosen, reason, args.max_delta_m, sens)
    out = args.results / "drift_params.json"
    out.write_text(json.dumps(params, indent=2) + "\n")

    skip = params["scoring_settings"]["rpe_skip_start_s"]
    curves = {f"{n} fit{' (chosen)' if n == chosen else ''}: {MODELS[n].formula}":
              (lambda d, n=n: MODELS[n].f(d, *[fits[n].values[k] for k in MODELS[n].params])) for n in MODELS}
    plot_rpe_vs_delta(args.results / "drift_fit.png",
                      [load_rpe_points(args.results, p.run) for p in points],  # show all lengths, fit used <= max
                      f"Drift model fit on delta <= {args.max_delta_m:g} m, distinct runs, skip_start_s = {skip:g} s\n"
                      "(point labels: number of segments; dotted: reference slopes)", fits=curves,
                      fit_max_delta_m=args.max_delta_m)

    for name, f in fits.items():
        ps = ", ".join(f"{k} = {v:.4g} ± {f.std_errors[k]:.2g} {MODELS[name].units[k].split(' ')[0]}"
                       for k, v in f.values.items())
        print(f"{name:9s} {ps} | n {f.n_points}, chi2 {f.chi2:.2f}, AICc {f.aicc:.2f} "
              f"({f.aicc - fits['power'].aicc:+.2f} vs power), RMS log resid {f.rms_log_residual:.3f}, "
              f"held-out " + ", ".join(f"{k} {v:.3f}" for k, v in loso[name].items())
              + (f" | AT BOUND (std error not meaningful): {', '.join(f.at_bound)}" if f.at_bound else ""))
    print(f"chosen: {chosen}. {reason}")
    print("power-law sensitivity:")
    for v in sens:
        print(f"  {v['variant']:38s} n {v['n_points']:2d}  c = {v['c']:.5f} ± {v['c_std_error']:.5f}  "
              f"p = {v['p']:.3f} ± {v['p_std_error']:.3f}")
    print(f"wrote {out} and {args.results / 'drift_fit.png'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
