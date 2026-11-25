#!/usr/bin/env python3
"""Summarise a PX4 SITL flight from a ROS 2 bag of /fmu/out topics.

Week 1 check that a recorded mission actually flew: arm/disarm, takeoff/landing,
flight modes, peak altitude and horizontal extent. Reads PX4's own state topics, so
this describes what the simulated autopilot reported (simulation, not real flight).

Usage (system Python, ROS + ~/ws_deps sourced for px4_msgs):
    python3 eval/check_flight_bag.py ~/data/bags/week1_flight eval/results/week1_flight_check.json
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

LOCAL_POS = "/fmu/out/vehicle_local_position_v1"
LAND = "/fmu/out/vehicle_land_detected"
STATUS = "/fmu/out/vehicle_status_v5"
ARMED = 2  # VehicleStatus.ARMING_STATE_ARMED
NAV_NAMES = {3: "AUTO_MISSION", 4: "AUTO_LOITER", 5: "AUTO_RTL", 17: "AUTO_TAKEOFF", 18: "AUTO_LAND"}


def read_topics(bag_dir: str, topics: set[str]) -> tuple[dict[str, list[tuple[float, object]]], float, float]:
    """Return {topic: [(t_rel_s, msg), ...]}, bag start time and duration in seconds (receive time)."""
    reader = rosbag2_py.SequentialReader()
    reader.open(rosbag2_py.StorageOptions(uri=bag_dir, storage_id="mcap"), rosbag2_py.ConverterOptions("cdr", "cdr"))
    meta = reader.get_metadata()
    t0 = meta.starting_time.nanoseconds / 1e9
    types = {t.name: t.type for t in reader.get_all_topics_and_types()}
    msg_cls = {t: get_message(types[t]) for t in topics if t in types}
    reader.set_filter(rosbag2_py.StorageFilter(topics=list(msg_cls)))
    out: dict[str, list[tuple[float, object]]] = {t: [] for t in msg_cls}
    while reader.has_next():
        topic, data, t_ns = reader.read_next()
        out[topic].append((t_ns / 1e9 - t0, deserialize_message(data, msg_cls[topic])))
    return out, t0, meta.duration.nanoseconds / 1e9


def transitions(samples: list[tuple[float, object]], key) -> list[tuple[float, object]]:
    """Times at which key(msg) changes value, starting with the first value."""
    result: list[tuple[float, object]] = []
    for t, msg in samples:
        value = key(msg)
        if not result or result[-1][1] != value:
            result.append((t, value))
    return result


def summarise(data: dict[str, list[tuple[float, object]]], duration_s: float) -> dict:
    landed = transitions(data[LAND], lambda m: bool(m.landed))
    armed = transitions(data[STATUS], lambda m: m.arming_state == ARMED)
    modes = transitions(data[STATUS], lambda m: NAV_NAMES.get(m.nav_state, f"nav_state_{m.nav_state}"))
    valid = [m for _, m in data[LOCAL_POS] if m.xy_valid and m.z_valid]
    takeoffs = [t for t, v in landed if v is False]
    landings = [t for t, v in landed[1:] if v is True]
    return {
        "frame": "PX4 local NED, origin = EKF reference point (home); altitude = -z",
        "bag_duration_s": round(duration_s, 2),
        "armed_transitions_s": [[round(t, 2), v] for t, v in armed],
        "landed_transitions_s": [[round(t, 2), v] for t, v in landed],
        "nav_mode_sequence": [[round(t, 2), v] for t, v in modes],
        "airborne_s": round(landings[-1] - takeoffs[0], 2) if takeoffs and landings else None,
        "max_altitude_m": round(max(-m.z for m in valid), 2),
        "max_horizontal_distance_m": round(max(math.hypot(m.x, m.y) for m in valid), 2),
        "final_horizontal_distance_m": round(math.hypot(valid[-1].x, valid[-1].y), 2),
        "ended_landed_and_disarmed": bool(landed and landed[-1][1] is True and armed and armed[-1][1] is False),
    }


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    bag_dir, out_path = sys.argv[1], Path(sys.argv[2])
    data, _, duration = read_topics(bag_dir, {LOCAL_POS, LAND, STATUS})
    summary = {"bag": str(Path(bag_dir).expanduser()), **summarise(data, duration)}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
