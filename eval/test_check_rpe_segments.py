"""Tests for check_rpe_segments.py helpers on synthetic poses."""
import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from check_rpe_segments import step_series, window_report


def straight_line(n=200, dt=0.05, speed=1.0):
    t = np.arange(n) * dt
    xyz = np.stack([t * speed, np.zeros(n), np.zeros(n)], axis=1)
    quat = np.tile([0.0, 0.0, 0.0, 1.0], (n, 1))
    return t, xyz, quat


def test_position_jump_found_in_window_and_above_whole_run_percentile():
    t, xyz, quat = straight_line()
    xyz[100:] += [0.0, 0.3, 0.0]  # 0.3 m sideways jump between pose 99 and 100
    rep = window_report(t, step_series(t, xyz, quat), t0=4.0, t1=6.0)
    assert rep["win_max_step_m"] == pytest.approx(np.hypot(0.05, 0.3))
    assert rep["win_max_step_m_at"] == pytest.approx(t[99])
    assert rep["whole_median_step_m"] == pytest.approx(0.05)
    assert rep["n_poses_in_window"] == 41


def test_time_gap_and_rotation_jump():
    t, xyz, quat = straight_line()
    t[150:] += 0.4  # 0.4 s gap after pose 149
    quat[50:] = Rotation.from_euler("z", 10, degrees=True).as_quat()  # 10 degree yaw jump at pose 50
    s = step_series(t, xyz, quat)
    rep = window_report(t, s, t0=0.0, t1=t[-1])
    assert rep["win_max_dt_s"] == pytest.approx(0.45)
    assert rep["win_max_dt_s_at"] == pytest.approx(t[149])
    assert rep["win_max_rot_deg"] == pytest.approx(10.0)
    assert rep["win_max_rot_deg_at"] == pytest.approx(t[49])
    assert rep["whole_n_gaps"] == 1 and rep["whole_gap_total_s"] == pytest.approx(0.45)


def test_window_without_steps_gives_nan():
    t, xyz, quat = straight_line()
    rep = window_report(t, step_series(t, xyz, quat), t0=100.0, t1=101.0)
    assert rep["n_poses_in_window"] == 0 and np.isnan(rep["win_max_step_m"])


def test_first_step_reported():
    t, xyz, quat = straight_line()
    xyz[1:] += [0.0, 0.2, 0.0]  # 0.2 m sideways jump on the very first step
    rep = window_report(t, step_series(t, xyz, quat), t0=50.0, t1=60.0)
    assert rep["first_step_at"] == pytest.approx(t[0])
    assert rep["first_step_step_m"] == pytest.approx(np.hypot(0.05, 0.2))
    assert rep["first_step_speed_mps"] == pytest.approx(np.hypot(0.05, 0.2) / 0.05)
    assert rep["first_step_rot_deg"] == pytest.approx(0.0)
