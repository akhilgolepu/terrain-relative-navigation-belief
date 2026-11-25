"""
Error model for terrain fixes: Gaussian inliers plus broad outliers, both depending on features.

The 2-D error e = fix - label [m] is modelled as a mixture:
  with probability 1 - w(x): isotropic Gaussian, standard deviation sigma(x) per axis,
  with probability w(x):     isotropic Gaussian, standard deviation sigma_out (constant, broad),
where x are the matcher's diagnostics (standardised with the fit data's mean and std):
  log sigma(x) = a0 + a . x        logit w(x) = b0 + b . x
sigma_out = SIGMA_OUT_MIN + exp(c) keeps the outlier part broader than any inlier.
The mean is zero: no label offset is estimated or applied.
Slopes a, b get an L2 penalty lam * (|a|^2 + |b|^2). With no features it is the constant model.
Errors are against dataset labels, so the predicted uncertainty includes label registration
error and is not uncertainty about the true position.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math

import numpy as np
from scipy import optimize

SIGMA_OUT_MIN = 60.0     # m; outlier component at least this broad
WRONG_M = 50.0           # a fix is "wrong" if |e| > this


def _log_norm2(e2: np.ndarray, sigma: np.ndarray) -> np.ndarray:
    """Log density of an isotropic 2-D Gaussian at squared radius e2."""
    return -e2 / (2 * sigma ** 2) - np.log(2 * np.pi * sigma ** 2)


@dataclass
class MixtureModel:
    """Fitted parameters plus the standardisation of its features."""

    features: list[str]
    mean: list[float]
    std: list[float]
    a0: float = math.log(20.0)
    a: list[float] = field(default_factory=list)
    b0: float = 0.0
    b: list[float] = field(default_factory=list)
    c: float = math.log(40.0)
    lam: float = 0.0

    def _z(self, x: np.ndarray) -> np.ndarray:
        """Return standardised features as an (n, k) array (k = 0 for the constant model)."""
        x = np.asarray(x, float)
        x = x.reshape(len(x), len(self.features))
        return (x - np.asarray(self.mean, float)) / np.asarray(self.std, float)

    def predict(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
        """Return sigma (m), outlier weight w and sigma_out (m) for feature rows x (n, k)."""
        z = self._z(x)
        sigma = np.exp(self.a0 + z @ np.asarray(self.a, float))
        w = 1.0 / (1.0 + np.exp(-(self.b0 + z @ np.asarray(self.b, float))))
        return sigma, w, SIGMA_OUT_MIN + math.exp(self.c)

    def nll(self, x: np.ndarray, e: np.ndarray) -> np.ndarray:
        """Return the negative log likelihood of each 2-D error (rows of e), in log(m^-2) units."""
        sigma, w, so = self.predict(x)
        e2 = np.sum(np.asarray(e, float) ** 2, axis=1)
        lin = np.log1p(-w) + _log_norm2(e2, sigma)
        lout = np.log(w) + _log_norm2(e2, np.full_like(sigma, so))
        return -np.logaddexp(lin, lout)

    def cdf_radius(self, x: np.ndarray, r) -> np.ndarray:
        """Return P(|e| <= r) under the predicted mixture (r scalar or per row)."""
        sigma, w, so = self.predict(x)
        r = np.asarray(r, float)
        inlier = 1 - np.exp(-r ** 2 / (2 * sigma ** 2))
        outlier = 1 - np.exp(-r ** 2 / (2 * so ** 2))
        return (1 - w) * inlier + w * outlier

    def p_wrong(self, x: np.ndarray, wrong_m: float = WRONG_M) -> np.ndarray:
        """Return the predicted probability that |e| > wrong_m."""
        return 1.0 - self.cdf_radius(x, wrong_m)

    def radius(self, x: np.ndarray, p: float) -> np.ndarray:
        """Return the radius r with P(|e| <= r) = p for each row (bisection, 1 mm precision)."""
        n = len(np.asarray(x))
        lo, hi = np.zeros(n), np.full(n, 1e4)
        for _ in range(60):
            mid = (lo + hi) / 2
            below = self.cdf_radius(x, mid) < p
            lo, hi = np.where(below, mid, lo), np.where(below, hi, mid)
        return (lo + hi) / 2

    def to_dict(self) -> dict:
        """Return the parameters as a JSON-ready dict."""
        return asdict(self)


def fit(x: np.ndarray, e: np.ndarray, features: list[str], lam: float,
        starts: int = 4, seed: int = 0) -> MixtureModel:
    """Fit by penalised maximum likelihood (L-BFGS from a few starting points); x is (n, k)."""
    e = np.asarray(e, float)
    k = len(features)
    x = np.asarray(x, float).reshape(len(e), k)
    mean = x.mean(axis=0).tolist()
    std = np.where(x.std(axis=0) > 1e-9, x.std(axis=0), 1.0).tolist()

    def unpack(th):
        return MixtureModel(features, mean, std, float(th[0]), th[1:1 + k].tolist(),
                            float(th[1 + k]), th[2 + k:2 + 2 * k].tolist(), float(th[2 + 2 * k]),
                            lam)

    def objective(th):
        pen = lam * (np.sum(np.square(th[1:1 + k])) + np.sum(np.square(th[2 + k:2 + 2 * k])))
        return float(np.sum(unpack(th).nll(x, e))) + pen

    rng = np.random.default_rng(seed)
    best = None
    for s in range(starts):
        th0 = np.r_[math.log(15.0 + 15.0 * s), np.zeros(k), -2.0 + s, np.zeros(k), math.log(40.0)]
        if s:
            th0 = th0 + rng.normal(0, 0.1, th0.shape)
        res = optimize.minimize(objective, th0, method='L-BFGS-B')
        if best is None or res.fun < best.fun:
            best = res
    return unpack(best.x)
