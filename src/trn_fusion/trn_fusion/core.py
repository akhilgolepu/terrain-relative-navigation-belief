"""
Fusion core: GTSAM iSAM2 over 2-D positions, odometry factors and gated, thinned mixture fixes.

One Point2 variable per odometry step (east, north [m], region ENU frame). Factors:
  prior        N(prior position, prior_sigma^2 I) on the first variable
  odometry     between consecutive variables, the measured increment u, noise step_sigma(u)
  fix          max-mixture factor (fix_factor.py), only if (a) at least thinning interval_s has
               passed since the last fused fix and (b) the chi-square gate passes:
               d2 = nu^T (P_pred + sigma_in^2 I)^-1 nu <= threshold, nu = fix - predicted position
No bias state. The belief (mean, covariance, fix age, validity) is read after every update.
Used identically by eval/eval_fusion.py and the ROS node (belief_node.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field
import time

import gtsam
import numpy as np

from . import validity
from .config import FROZEN, load_config  # noqa: F401  (re-exported)
from .fix_factor import FixModel, inlier_selected, mixture_factor
from .odometry_sim import step_sigma


@dataclass
class Belief:
    """Belief after an update."""

    t: float
    mean: np.ndarray
    cov: np.ndarray
    fix_age_s: float | None
    validity: int
    reason: str


@dataclass
class Counters:
    """What happened to the candidate fixes."""

    candidates: int = 0
    thinned: int = 0
    gated: int = 0
    fused: int = 0
    update_s: list = field(default_factory=list)


class FusionCore:
    """Incremental fusion of SYNTHETIC odometry and terrain fixes (see module docstring)."""

    def __init__(self, cfg: dict | None = None, fix_model: FixModel | None = None,
                 b: float = 0.0, use_fixes: bool = True):
        """Set up iSAM2; b is the random-walk drift coefficient of the odometry [m]."""
        self.cfg = cfg or load_config()
        self.fixes = fix_model or FixModel()
        self.b = b
        self.a = self.cfg['synthetic_odometry']['floor_a_m']
        self.use_fixes = use_fixes
        p = gtsam.ISAM2Params()
        p.setRelinearizeThreshold(0.01)
        p.relinearizeSkip = 1
        self.isam = gtsam.ISAM2(p)
        self.k = -1
        self.t = None
        self.last_fused_t: float | None = None
        self.last_fix_p_wrong: float | None = None
        self.fused: list[dict] = []
        self.count = Counters()

    @staticmethod
    def key(k: int) -> int:
        """Return the GTSAM key of position k."""
        return gtsam.symbol('x', k)

    def _update(self, graph: gtsam.NonlinearFactorGraph, values: gtsam.Values) -> None:
        t0 = time.perf_counter()
        self.isam.update(graph, values)
        self.count.update_s.append(time.perf_counter() - t0)

    def start(self, t: float, prior: np.ndarray, sigma: float) -> Belief:
        """Create the first variable at the prior position."""
        self.k, self.t = 0, t
        g, v = gtsam.NonlinearFactorGraph(), gtsam.Values()
        g.add(gtsam.PriorFactorPoint2(self.key(0), np.asarray(prior, float),
                                      gtsam.noiseModel.Isotropic.Sigma(2, sigma)))
        v.insert(self.key(0), np.asarray(prior, float))
        self._update(g, v)
        return self.belief()

    def odometry(self, t: float, u: np.ndarray) -> Belief:
        """Add the next position, linked to the previous one by the odometry increment u."""
        u = np.asarray(u, float)
        prev = self.isam.calculateEstimatePoint2(self.key(self.k))
        self.k += 1
        self.t = t
        g, v = gtsam.NonlinearFactorGraph(), gtsam.Values()
        noise = gtsam.noiseModel.Isotropic.Sigma(2, step_sigma(u, self.b, self.a))
        g.add(gtsam.BetweenFactorPoint2(self.key(self.k - 1), self.key(self.k), u, noise))
        v.insert(self.key(self.k), prev + u)
        self._update(g, v)
        return self.belief()

    def fix(self, t: float, z: np.ndarray, log_ratio: float) -> str:
        """Offer a fix for the current position; return 'fused', 'thinned', 'gated' or 'off'."""
        if not self.use_fixes:
            return 'off'
        self.count.candidates += 1
        interval = self.cfg['thinning']['interval_s']
        if self.last_fused_t is not None and t - self.last_fused_t < interval - 1e-9:
            self.count.thinned += 1
            return 'thinned'
        sigma_in, w, sigma_out, p_wrong = self.fixes.params(log_ratio)
        sigma_in *= self.cfg.get('fix_inflation', 1.0)
        key = self.key(self.k)
        mean = self.isam.calculateEstimatePoint2(key)
        cov = self.isam.marginalCovariance(key)
        nu = np.asarray(z, float) - mean
        d2 = float(nu @ np.linalg.solve(cov + sigma_in ** 2 * np.eye(2), nu))
        if self.gate_rejects(nu, cov, d2, sigma_in, w, sigma_out):
            self.count.gated += 1
            return 'gated'
        g = gtsam.NonlinearFactorGraph()
        g.add(mixture_factor(key, z, sigma_in, w, sigma_out))
        self._update(g, gtsam.Values())
        self.count.fused += 1
        self.last_fused_t, self.last_fix_p_wrong = t, p_wrong
        self.fused.append({'k': self.k, 't': t, 'z': np.asarray(z, float), 'sigma_in': sigma_in,
                           'w': w, 'sigma_out': sigma_out, 'p_wrong': p_wrong, 'd2': d2})
        return 'fused'

    def gate_rejects(self, nu, cov, d2_in: float, sigma_in: float, w: float,
                     sigma_out: float) -> bool:
        """
        Apply the configured gate (cfg['gate_mode']).

        'chi2_inlier' (week 6): d2 under the inlier model above the chi-square threshold.
        'off': never reject (the mixture alone handles outliers).
        'mixture_pvalue': p = (1 - w) exp(-d2_in / 2) + w exp(-d2_out / 2), the probability of an
        innovation at least this large under the predicted inlier/outlier mixture (2-D);
        reject if p < 1 - chi2_gate.probability.
        """
        mode = self.cfg.get('gate_mode', 'chi2_inlier')
        if mode == 'off':
            return False
        if mode == 'chi2_inlier':
            return d2_in > self.cfg['chi2_gate']['threshold']
        if mode == 'mixture_pvalue':
            d2_out = float(nu @ np.linalg.solve(cov + sigma_out ** 2 * np.eye(2), nu))
            p = (1 - w) * np.exp(-d2_in / 2) + w * np.exp(-d2_out / 2)
            return p < 1 - self.cfg['chi2_gate']['probability']
        raise ValueError(f'unknown gate_mode {mode}')

    def belief(self) -> Belief:
        """Read the current mean, covariance, fix age, validity and reason."""
        key = self.key(self.k)
        mean = self.isam.calculateEstimatePoint2(key)
        cov = self.isam.marginalCovariance(key)
        age = None if self.last_fused_t is None else self.t - self.last_fused_t
        v, reason = validity.state(cov, age, self.last_fix_p_wrong, self.cfg['validity'])
        return Belief(self.t, mean, cov, age, v, reason)

    def outlier_share(self) -> float:
        """Return the share of fused fixes the final estimate explains with the outlier part."""
        if not self.fused:
            return float('nan')
        est = self.isam.calculateEstimate()
        out = [not inlier_selected(est.atPoint2(self.key(f['k'])), f['z'], f['sigma_in'], f['w'],
                                   f['sigma_out']) for f in self.fused]
        return float(np.mean(out))
