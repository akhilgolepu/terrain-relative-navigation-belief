"""
Absolute-fix factor from the week 5 calibrated mixture (max-mixture form) and its parameters.

A fix z is either an inlier, z ~ N(x, sigma_in^2 I) with probability 1 - w, or an outlier,
z ~ N(x, sigma_out^2 I) with probability w (sigma_in and w from the fix's peak ratio, through
the frozen calibration model). Least-squares solvers cannot hold a sum of Gaussians, so the
factor uses the max-mixture approximation (Olson and Agarwal, 2012): at every linearisation it
takes the component with the lower cost,
    cost_i = |z - x|^2 / (2 sigma_i^2) - ln(weight_i) + ln(2 pi sigma_i^2),
and returns the residual [ (x - z) / sigma_i , sqrt(2 (K_i - K_min)) ] where K_i is the constant
part of cost_i. The extra constant entry keeps the costs of the two components comparable.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import sys

import gtsam
import numpy as np

CALIB = (Path(__file__).resolve().parents[2] / 'trn_calibration' / 'trn_calibration'
         / 'calibration_frozen.json')


def _mixture_model_class():
    """Import trn_calibration's MixtureModel (installed package or the source tree)."""
    try:
        from trn_calibration.covariance import MixtureModel
    except ImportError:
        sys.path.insert(0, str(CALIB.parents[1]))
        from trn_calibration.covariance import MixtureModel
    return MixtureModel


class FixModel:
    """Frozen week 5 'selected' model: per fix sigma_in, w, sigma_out and P(wrong)."""

    def __init__(self, calib_path: Path = CALIB):
        """Load the frozen calibration model."""
        spec = json.loads(Path(calib_path).read_text())['models']['selected']
        spec = {k: v for k, v in spec.items() if k != 'name'}
        if spec['features'] != ['log_ratio']:
            raise ValueError('fusion expects the ratio-only calibration model')
        self.model = _mixture_model_class()(**spec)

    def params(self, log_ratio: float) -> tuple[float, float, float, float]:
        """Return (sigma_in, w, sigma_out, p_wrong) for one fix."""
        x = np.array([[log_ratio]])
        sig, w, so = self.model.predict(x)
        return float(sig[0]), float(w[0]), float(so), float(self.model.p_wrong(x)[0])


def component_costs(r2: float, sigma_in: float, w: float, sigma_out: float):
    """Return ((cost_in, K_in), (cost_out, K_out)) for a squared residual r2 [m^2]."""
    k_in = -math.log(1.0 - w) + math.log(2 * math.pi * sigma_in ** 2)
    k_out = -math.log(w) + math.log(2 * math.pi * sigma_out ** 2)
    return ((r2 / (2 * sigma_in ** 2) + k_in, k_in), (r2 / (2 * sigma_out ** 2) + k_out, k_out))


def mixture_factor(key: int, z: np.ndarray, sigma_in: float, w: float,
                   sigma_out: float) -> gtsam.CustomFactor:
    """Return a GTSAM CustomFactor for one absolute 2-D fix z on Point2 variable `key`."""
    z = np.asarray(z, float)
    k_min = min(component_costs(0.0, sigma_in, w, sigma_out)[i][1] for i in (0, 1))

    def error(this: gtsam.CustomFactor, values: gtsam.Values, jac):
        x = values.atPoint2(this.keys()[0])
        d = x - z
        (c_in, k_in), (c_out, k_out) = component_costs(float(d @ d), sigma_in, w, sigma_out)
        sigma, k = (sigma_in, k_in) if c_in <= c_out else (sigma_out, k_out)
        if jac is not None:
            jac[0] = np.array([[1.0 / sigma, 0.0], [0.0, 1.0 / sigma], [0.0, 0.0]])
        return np.array([d[0] / sigma, d[1] / sigma, math.sqrt(max(2.0 * (k - k_min), 0.0))])

    return gtsam.CustomFactor(gtsam.noiseModel.Unit.Create(3), [key], error)


def inlier_selected(x: np.ndarray, z: np.ndarray, sigma_in: float, w: float,
                    sigma_out: float) -> bool:
    """Return True if the inlier component explains z better at estimate x."""
    d = np.asarray(x, float) - np.asarray(z, float)
    (c_in, _), (c_out, _) = component_costs(float(d @ d), sigma_in, w, sigma_out)
    return c_in <= c_out
