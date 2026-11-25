"""Week 5 calibration metrics, shared by calib_fit.py and calib_eval.py.

All functions take plain arrays. Frames must be in flight order where blocks matter.
"""
from __future__ import annotations

import numpy as np

LABEL_NOTE = ("Errors are against dataset labels, so reported uncertainty includes label registration error and "
              "is not uncertainty about the true position.")


def coverage(model, x: np.ndarray, err: np.ndarray, p: float) -> float:
    """Fraction of frames whose |e| lies within the model's p-radius."""
    return float(np.mean(err <= model.radius(x, p)))


def reliability(prob: np.ndarray, y: np.ndarray, bins: int = 5) -> list[dict]:
    """Equal-count bins of predicted probability: mean prediction, observed rate, count."""
    order = np.argsort(prob, kind="stable")
    out = []
    for idx in np.array_split(order, bins):
        if len(idx):
            out.append({"n": int(len(idx)), "pred": float(prob[idx].mean()), "obs": float(y[idx].mean()),
                        "lo": float(prob[idx].min()), "hi": float(prob[idx].max())})
    return out


def ece(prob: np.ndarray, y: np.ndarray, bins: int = 5) -> float:
    """Expected calibration error over equal-count bins (count-weighted |pred - obs|)."""
    r = reliability(prob, y, bins)
    n = sum(b["n"] for b in r)
    return float(sum(b["n"] * abs(b["pred"] - b["obs"]) for b in r) / n)


def auc(score: np.ndarray, y: np.ndarray) -> float:
    """Probability that a random positive (y = 1) scores higher than a random negative (ties count half)."""
    pos, neg = score[y == 1], score[y == 0]
    if not len(pos) or not len(neg):
        return float("nan")
    greater = (pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()
    return float(greater / (len(pos) * len(neg)))


def risk_coverage(risk_score: np.ndarray, wrong: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Accept frames in order of increasing risk_score: return (thresholds, fraction accepted, wrong rate)."""
    order = np.argsort(risk_score, kind="stable")
    w = wrong[order].astype(float)
    k = np.arange(1, len(w) + 1)
    return risk_score[order], k / len(w), np.cumsum(w) / k


def aurc(risk_score: np.ndarray, wrong: np.ndarray) -> float:
    """Area under the risk-coverage curve (mean wrong rate over all acceptance levels; lower is better)."""
    _, _, rate = risk_coverage(risk_score, wrong)
    return float(rate.mean())


def contiguous_blocks(n: int, k: int) -> list[np.ndarray]:
    """Split range(n) into k contiguous blocks (for block cross-validation)."""
    return [b for b in np.array_split(np.arange(n), k) if len(b)]


def block_bootstrap(stat, n: int, block: int, reps: int = 1000, seed: int = 0) -> tuple[float, float]:
    """95 % interval of stat(indices) under a moving-block bootstrap of contiguous blocks."""
    rng = np.random.default_rng(seed)
    starts = np.arange(max(1, n - block + 1))
    vals = []
    for _ in range(reps):
        idx = np.concatenate([np.arange(s, min(s + block, n)) for s in
                              rng.choice(starts, int(np.ceil(n / block)))])[:n]
        vals.append(stat(idx))
    vals = np.asarray(vals, float)
    vals = vals[np.isfinite(vals)]
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def n_eff(series: np.ndarray, max_lag: int = 50) -> float:
    """Effective sample size n / (1 + 2 sum rho_k), summing autocorrelations until the first one <= 0."""
    x = np.asarray(series, float)
    n = len(x)
    x = x - x.mean()
    var = float(x @ x) / n
    if var == 0:
        return float(n)
    s = 0.0
    for k in range(1, min(max_lag, n - 1)):
        rho = float(x[:-k] @ x[k:]) / n / var
        if rho <= 0:
            break
        s += rho
    return float(n / (1 + 2 * s))
