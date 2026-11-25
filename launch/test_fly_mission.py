"""Tests for the mission geometry in fly_mission.py (no simulator needed)."""
import math

import pytest
from pymavlink import mavutil

from fly_mission import (EARTH_M_PER_DEG_LAT, INT32_UNSET, MissionTracker, build_square_mission, encode_item,
                         offset_to_latlon)

HOME = (47.397971, 8.546164)  # PX4 SITL default home


def test_offset_north_moves_latitude_only():
    lat, lon = offset_to_latlon(*HOME, north_m=100.0, east_m=0.0)
    assert lat - HOME[0] == pytest.approx(100.0 / EARTH_M_PER_DEG_LAT)
    assert lon == HOME[1]


def test_offset_east_scales_with_latitude():
    lat, lon = offset_to_latlon(*HOME, north_m=0.0, east_m=100.0)
    east_m = (lon - HOME[1]) * EARTH_M_PER_DEG_LAT * math.cos(math.radians(HOME[0]))
    assert lat == HOME[0]
    assert east_m == pytest.approx(100.0)


def test_square_mission_structure():
    items = build_square_mission(*HOME, side_m=80.0, alt_m=20.0)
    commands = [i.command for i in items]
    assert commands[0] == mavutil.mavlink.MAV_CMD_NAV_TAKEOFF
    assert commands[1:5] == [mavutil.mavlink.MAV_CMD_NAV_WAYPOINT] * 4
    assert commands[-1] == mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH
    assert all(i.alt_m == 20.0 for i in items[:5])
    # last corner closes the square back over home
    assert (items[4].lat_deg, items[4].lon_deg) == pytest.approx(HOME)


def test_rtl_is_sent_without_coordinates():
    # PX4 main rejects RTL with x=0 (MAV_MISSION_INVALID_PARAM5_X); it takes no params.
    rtl = build_square_mission(*HOME, side_m=80.0, alt_m=20.0)[-1]
    frame, x, y, z = encode_item(rtl)
    assert frame == mavutil.mavlink.MAV_FRAME_MISSION
    assert x == INT32_UNSET and y == INT32_UNSET
    assert math.isnan(z)
    assert all(math.isnan(p) for p in rtl.params)


def test_waypoint_encodes_lat_lon_as_int():
    wp = build_square_mission(*HOME, side_m=80.0, alt_m=20.0)[4]
    frame, x, y, z = encode_item(wp)
    assert frame == mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT
    assert (x, y) == (round(HOME[0] * 1e7), round(HOME[1] * 1e7))
    assert z == 20.0


def started_tracker() -> MissionTracker:
    t = MissionTracker()
    t.on_armed(False)  # disarmed on the ground before start must not count
    t.on_landed_state(True)
    t.started = True
    t.on_armed(True)
    t.on_landed_state(False)
    return t


def test_disarm_before_start_is_not_flight_over():
    t = MissionTracker()
    t.on_armed(False)
    t.on_landed_state(True)
    assert not t.flight_over and not t.success


def test_success_on_landed_and_disarmed_after_start():
    t = started_tracker()
    t.on_landed_state(True)
    t.on_armed(False)
    assert t.flight_over and t.landed_and_disarmed and t.success
    assert t.reason() == "landed and disarmed"


def test_success_on_px4_mission_finished_text():
    # The last-waypoint MISSION_ITEM_REACHED may never arrive (PX4 sent 0,1,2,3,5 on 2026-11-11).
    t = started_tracker()
    t.reached.update({0, 1, 2, 3, 5})
    t.on_statustext("Mission finished, loitering")
    assert t.success and not t.flight_over


def test_mission_finished_before_start_is_ignored():
    t = MissionTracker()
    t.on_statustext("Mission finished, loitering")
    assert not t.success


def test_disarm_in_air_is_not_success():
    # flight over (disarmed) but landed state still airborne and no "mission finished": failure path
    t = started_tracker()
    t.on_armed(False)
    assert t.flight_over and not t.success
    assert t.reason() == "neither mission finished nor landed+disarmed"


def test_mission_finished_without_disarm_prints_distinct_warning():
    # Timeout path where PX4 said "Mission finished" but the vehicle never disarmed.
    t = started_tracker()
    t.on_statustext("Mission finished, loitering")
    assert t.success and not t.flight_over
    msg = t.completion_message()
    assert msg.startswith("MISSION FINISHED, NOT DISARMED (warning)")
    assert "MISSION COMPLETE" not in msg


def test_normal_completion_message():
    t = started_tracker()
    t.on_statustext("Mission finished, loitering")
    t.on_landed_state(True)
    t.on_armed(False)
    assert t.completion_message() == "MISSION COMPLETE: PX4 reported mission finished; landed and disarmed"
