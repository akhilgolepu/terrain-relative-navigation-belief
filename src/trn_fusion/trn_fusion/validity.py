"""
Validity state machine for NavBelief: STRONG, AGING, UNCERTAIN, DO_NOT_PUBLISH plus a reason.

Thresholds come from fusion_frozen.json (written down before any result):
  DO_NOT_PUBLISH  no fix fused yet, or s > dnp_sigma_m
  AGING           s > aging_sigma_m
  UNCERTAIN       the last fused fix had P(wrong) > strong_fix_max_p_wrong
  STRONG          otherwise
where s is the 1-sigma length of the major axis of the fused position covariance. The state is
an output summary only; the fusion itself never looks at it.
"""
from __future__ import annotations

import numpy as np

STRONG, AGING, UNCERTAIN, DO_NOT_PUBLISH = 0, 1, 2, 3   # NavBelief constants
NAMES = {STRONG: 'STRONG', AGING: 'AGING', UNCERTAIN: 'UNCERTAIN',
         DO_NOT_PUBLISH: 'DO_NOT_PUBLISH'}


def major_sigma(cov: np.ndarray) -> float:
    """Return sqrt of the largest eigenvalue of a 2x2 covariance [m]."""
    return float(np.sqrt(max(np.linalg.eigvalsh(np.asarray(cov, float)[:2, :2]))))


def state(cov: np.ndarray, fix_age_s: float | None, last_fix_p_wrong: float | None,
          cfg: dict) -> tuple[int, str]:
    """Return (validity constant, short reason) for the current belief."""
    s = major_sigma(cov)
    if fix_age_s is None:
        return DO_NOT_PUBLISH, f'no fix fused yet; 1-sigma {s:.0f} m'
    if s > cfg['dnp_sigma_m']:
        return DO_NOT_PUBLISH, (f'1-sigma {s:.0f} m > {cfg["dnp_sigma_m"]:.0f} m; '
                                f'last fix {fix_age_s:.0f} s ago')
    if s > cfg['aging_sigma_m']:
        return AGING, (f'1-sigma {s:.0f} m > {cfg["aging_sigma_m"]:.0f} m; '
                       f'last fix {fix_age_s:.0f} s ago')
    if last_fix_p_wrong is not None and last_fix_p_wrong > cfg['strong_fix_max_p_wrong']:
        return UNCERTAIN, (f'last fix P(wrong) {last_fix_p_wrong:.2f} > '
                           f'{cfg["strong_fix_max_p_wrong"]:.2f}; 1-sigma {s:.0f} m')
    return STRONG, (f'1-sigma {s:.0f} m; last fix {fix_age_s:.0f} s ago, '
                    f'P(wrong) {last_fix_p_wrong:.2f}')
