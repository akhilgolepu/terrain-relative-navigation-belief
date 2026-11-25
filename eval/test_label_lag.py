"""label_lag.py recovers a known timing lag and map shift from synthetic accepted fixes."""
import numpy as np
import pytest

import label_lag


def _rows(lag, shift, leg_speeds, flight="10", n=10):
    """Two straight legs, one speed each, with a 60 s turn between (frames across it are skipped).

    fix = label - d with d = shift + speed*lag*u, i.e. label - fix = d.
    """
    rows, times, t, pos = [], {}, 0.0, np.zeros(2)
    k = 0
    for u, sp in zip([np.array([0.38, -0.92]), np.array([-0.38, 0.92])], leg_speeds):
        t += 60.0
        for _ in range(n):
            name = f"{flight}_{k:04d}.JPG"
            d = np.asarray(shift) + sp * lag * u
            fix = pos - d
            rows.append({"split": "tune", "flight": flight, "image": name, "status": "fix",
                         "true_e": pos[0], "true_n": pos[1], "err_e": fix[0] - pos[0], "err_n": fix[1] - pos[1]})
            times[name] = t
            t += 3.0
            pos = pos + u * sp * 3.0
            k += 1
    return rows, times


def test_recovers_lag_and_shift():
    rows, times = _rows(-0.9, (7.0, -2.0), (15.0, 25.0))
    s = label_lag.samples(rows, times)
    f = label_lag.fit(s)
    assert f["m2_lag_s"] == pytest.approx(-0.9, abs=1e-6)
    assert (f["m2_shift_e_m"], f["m2_shift_n_m"]) == pytest.approx((7.0, -2.0), abs=1e-6)
    assert f["m2_resid_rms_m"] < 1e-6


def test_along_track_lag_through_origin_without_shift():
    rows, times = _rows(-1.2, (0.0, 0.0), (15.0, 25.0))
    f = label_lag.fit(label_lag.samples(rows, times))
    assert f["lag_s"] == pytest.approx(-1.2, abs=1e-6) and f["lag_rms_m"] < 1e-6
    s = label_lag.samples(rows, times)
    assert np.allclose(label_lag.corrected_errors(s, f["lag_s"]), 0.0, atol=1e-6)
