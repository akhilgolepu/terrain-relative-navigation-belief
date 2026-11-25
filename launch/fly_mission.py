#!/usr/bin/env python3
"""Upload and fly a square waypoint mission on PX4 SITL over MAVLink.

Week 1 tool: gives a repeatable simulated flight to record with `ros2 bag record`.
Connects to PX4's offboard/API MAVLink link (SITL sends it to UDP 14540), so
QGroundControl can stay connected on 14550 and show the flight live.

Mission: takeoff at home, fly a square of side `--side` metres at `--alt` metres
above home, then return to launch (PX4 lands and disarms on its own).

Success: PX4 reports "Mission finished", or the vehicle has landed and disarmed after
the mission started. Hitting `--timeout` before either is a failure.
With `--record-bag DIR`, the script runs `ros2 bag record` on PX4's /fmu/out topics from
just before arming until RECORD_TAIL_S after disarm (needs ROS 2 and px4_msgs sourced).

Simulation only. Run with system Python (pymavlink): /usr/bin/python3 launch/fly_mission.py
"""
from __future__ import annotations

import argparse
import math
import shutil
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from pymavlink import mavutil

RECORD_TAIL_S = 5.0  # keep recording this long after disarm
BAG_TOPIC_REGEX = "/fmu/out/.*"
EARTH_M_PER_DEG_LAT = 111_320.0  # metres per degree of latitude (spherical approximation)
INT32_UNSET = 2**31 - 1  # MAVLink "not used" value for integer x/y (MISSION_ITEM_INT)
NAN = math.nan           # MAVLink "not used" value for float params; PX4 main rejects 0 in unsupported slots


@dataclass(frozen=True)
class MissionItem:
    command: int
    lat_deg: float
    lon_deg: float
    alt_m: float  # relative to home
    params: tuple[float, float, float, float] = (NAN, NAN, NAN, NAN)  # param1..param4
    has_position: bool = True  # False: coordinate-free item (sent in MAV_FRAME_MISSION, x/y/z unset)


def offset_to_latlon(lat0_deg: float, lon0_deg: float, north_m: float, east_m: float) -> tuple[float, float]:
    """Shift a WGS84 point by a small north/east offset (flat-earth approximation, fine for < 1 km)."""
    dlat = north_m / EARTH_M_PER_DEG_LAT
    dlon = east_m / (EARTH_M_PER_DEG_LAT * math.cos(math.radians(lat0_deg)))
    return lat0_deg + dlat, lon0_deg + dlon


def build_square_mission(home_lat: float, home_lon: float, side_m: float, alt_m: float) -> list[MissionItem]:
    """Takeoff at home, four corners of a square (north then east), then return to launch."""
    items = [MissionItem(mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, home_lat, home_lon, alt_m)]
    for north, east in [(side_m, 0.0), (side_m, side_m), (0.0, side_m), (0.0, 0.0)]:
        lat, lon = offset_to_latlon(home_lat, home_lon, north, east)
        # param1 hold 0 s, param2 acceptance radius 0 (= PX4 default); param3/4 unused
        items.append(MissionItem(mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, lat, lon, alt_m, params=(0.0, 0.0, NAN, NAN)))
    items.append(MissionItem(mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH, NAN, NAN, NAN, has_position=False))
    return items


def encode_item(item: MissionItem) -> tuple[int, int, int, float]:
    """MAVLink frame, x, y, z for MISSION_ITEM_INT; coordinate-free items get the 'not used' values."""
    if not item.has_position:
        return mavutil.mavlink.MAV_FRAME_MISSION, INT32_UNSET, INT32_UNSET, NAN
    return (mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
            int(round(item.lat_deg * 1e7)), int(round(item.lon_deg * 1e7)), item.alt_m)


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def start_heartbeat(conn: mavutil.mavfile, stop: threading.Event) -> None:
    """Send a GCS heartbeat at 1 Hz so PX4 sees an active ground-station link."""
    def run() -> None:
        while not stop.is_set():
            conn.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_GCS, mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, 0)
            stop.wait(1.0)
    threading.Thread(target=run, daemon=True).start()


def wait_home(conn: mavutil.mavfile, timeout_s: float) -> tuple[float, float]:
    """Ask for HOME_POSITION until PX4 answers; return (lat, lon) in degrees."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        conn.mav.command_long_send(conn.target_system, conn.target_component,
                                   mavutil.mavlink.MAV_CMD_REQUEST_MESSAGE, 0,
                                   mavutil.mavlink.MAVLINK_MSG_ID_HOME_POSITION, 0, 0, 0, 0, 0, 0)
        msg = conn.recv_match(type="HOME_POSITION", blocking=True, timeout=2)
        if msg is not None:
            return msg.latitude / 1e7, msg.longitude / 1e7
    raise TimeoutError("no HOME_POSITION from PX4")


def upload_mission(conn: mavutil.mavfile, items: list[MissionItem], timeout_s: float) -> None:
    """MAVLink mission upload: COUNT, answer each MISSION_REQUEST(_INT), wait for ACK."""
    conn.mav.mission_count_send(conn.target_system, conn.target_component, len(items),
                                mavutil.mavlink.MAV_MISSION_TYPE_MISSION)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        msg = conn.recv_match(type=["MISSION_REQUEST_INT", "MISSION_REQUEST", "MISSION_ACK"], blocking=True, timeout=2)
        if msg is None:
            continue
        if msg.get_type() == "MISSION_ACK":
            if msg.type != mavutil.mavlink.MAV_MISSION_ACCEPTED:
                raise RuntimeError(f"mission rejected, MAV_MISSION_RESULT={msg.type}")
            return
        item = items[msg.seq]
        frame, x, y, z = encode_item(item)
        conn.mav.mission_item_int_send(
            conn.target_system, conn.target_component, msg.seq, frame, item.command,
            0, 1,  # current, autocontinue
            *item.params, x, y, z,
            mavutil.mavlink.MAV_MISSION_TYPE_MISSION)
    raise TimeoutError("mission upload did not finish")


def send_command(conn: mavutil.mavfile, command: int, *params: float) -> int:
    """COMMAND_LONG and return the MAV_RESULT from its COMMAND_ACK (-1 if none)."""
    p = list(params) + [0.0] * (7 - len(params))
    conn.mav.command_long_send(conn.target_system, conn.target_component, command, 0, *p)
    ack = conn.recv_match(type="COMMAND_ACK", blocking=True, timeout=3,
                          condition=f"COMMAND_ACK.command=={command}")
    return -1 if ack is None else ack.result


def arm_when_ready(conn: mavutil.mavfile, timeout_s: float) -> None:
    """Retry arming every 2 s until PX4 accepts (pre-flight checks can take a few seconds)."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        result = send_command(conn, mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 1)
        if result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
            return
        log(f"arm not accepted yet (MAV_RESULT={result}), retrying")
        time.sleep(2)
    raise TimeoutError("vehicle did not arm")


@dataclass
class MissionTracker:
    """End-of-flight logic, kept free of MAVLink I/O so it can be unit-tested.

    Not relying on MISSION_ITEM_REACHED for the last waypoint: PX4 main skipped it
    (reported 0,1,2,3,5) on 2026-11-11.
    """
    started: bool = False
    armed: bool = False
    armed_since_start: bool = False
    on_ground: bool | None = None
    mission_finished: bool = False
    reached: set[int] = field(default_factory=set)

    def on_armed(self, armed: bool) -> None:
        self.armed = armed
        if self.started and armed:
            self.armed_since_start = True

    def on_landed_state(self, on_ground: bool) -> None:
        self.on_ground = on_ground

    def on_statustext(self, text: str) -> None:
        if self.started and "mission finished" in text.lower():
            self.mission_finished = True

    @property
    def flight_over(self) -> bool:
        """Armed after the mission started, now disarmed."""
        return self.armed_since_start and not self.armed

    @property
    def landed_and_disarmed(self) -> bool:
        return self.flight_over and self.on_ground is True

    @property
    def success(self) -> bool:
        return self.mission_finished or self.landed_and_disarmed

    def reason(self) -> str:
        parts = (["PX4 reported mission finished"] if self.mission_finished else []) + \
                (["landed and disarmed"] if self.landed_and_disarmed else [])
        return "; ".join(parts) or "neither mission finished nor landed+disarmed"

    def completion_message(self) -> str:
        """Final line for a successful run; a distinct warning if PX4 finished but never disarmed."""
        if self.mission_finished and not self.flight_over:
            return ("MISSION FINISHED, NOT DISARMED (warning): PX4 reported mission finished, "
                    "but the vehicle did not disarm before the timeout")
        return f"MISSION COMPLETE: {self.reason()}"


def request_landed_state(conn: mavutil.mavfile, rate_hz: float = 2.0) -> None:
    """Ask PX4 to stream EXTENDED_SYS_STATE (landed state) on this link."""
    result = send_command(conn, mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
                          mavutil.mavlink.MAVLINK_MSG_ID_EXTENDED_SYS_STATE, 1e6 / rate_hz)
    if result != mavutil.mavlink.MAV_RESULT_ACCEPTED:
        log(f"warning: EXTENDED_SYS_STATE interval not accepted (MAV_RESULT={result})")


def monitor_flight(conn: mavutil.mavfile, tracker: MissionTracker, timeout_s: float) -> bool:
    """Feed PX4 messages to the tracker until the flight is over. Returns False on timeout."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if tracker.flight_over:
            return True
        msg = conn.recv_match(type=["MISSION_ITEM_REACHED", "HEARTBEAT", "STATUSTEXT", "EXTENDED_SYS_STATE"],
                              blocking=True, timeout=2)
        if msg is None or msg.get_srcSystem() != conn.target_system:
            continue
        kind = msg.get_type()
        if kind == "MISSION_ITEM_REACHED" and msg.seq not in tracker.reached:
            tracker.reached.add(msg.seq)
            log(f"reached mission item {msg.seq}")
        elif kind == "STATUSTEXT":
            log(f"PX4: {msg.text}")
            tracker.on_statustext(msg.text)
        elif kind == "EXTENDED_SYS_STATE":
            tracker.on_landed_state(msg.landed_state == mavutil.mavlink.MAV_LANDED_STATE_ON_GROUND)
        elif kind == "HEARTBEAT" and msg.type != mavutil.mavlink.MAV_TYPE_GCS:
            tracker.on_armed(bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED))
    return False


class BagRecorder:
    """Runs `ros2 bag record` as a child process; stopped with SIGINT so the bag closes cleanly."""

    def __init__(self, out_dir: Path) -> None:
        self.out_dir = out_dir
        self.log_path = out_dir.parent / f"{out_dir.name}_record.log"
        self.proc: subprocess.Popen | None = None

    def start(self, timeout_s: float = 30.0) -> None:
        if shutil.which("ros2") is None:
            raise RuntimeError("ros2 not on PATH: source /opt/ros/jazzy/setup.bash and ~/ws_deps/install/setup.bash")
        if self.out_dir.exists():
            raise RuntimeError(f"{self.out_dir} already exists; ros2 bag will not overwrite it")
        self.proc = subprocess.Popen(["ros2", "bag", "record", "-e", BAG_TOPIC_REGEX, "-o", str(self.out_dir)],
                                     stdout=self.log_path.open("w"), stderr=subprocess.STDOUT)
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(f"ros2 bag record exited early, see {self.log_path}")
            if "Recording..." in self.log_path.read_text():
                log(f"recording {BAG_TOPIC_REGEX} to {self.out_dir}")
                return
            time.sleep(0.5)
        raise TimeoutError(f"ros2 bag record did not start, see {self.log_path}")

    def stop(self, timeout_s: float = 30.0) -> None:
        if self.proc is None or self.proc.poll() is not None:
            return
        self.proc.send_signal(signal.SIGINT)
        try:
            self.proc.wait(timeout=timeout_s)
            log(f"recording stopped (exit {self.proc.returncode})")
        except subprocess.TimeoutExpired:
            log(f"warning: ros2 bag record did not stop within {timeout_s:.0f} s")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", default="udpin:0.0.0.0:14540", help="MAVLink connection (PX4 SITL API link)")
    ap.add_argument("--alt", type=float, default=20.0, help="flight altitude above home [m]")
    ap.add_argument("--side", type=float, default=80.0, help="square side length [m]")
    ap.add_argument("--timeout", type=float, default=600.0, help="max mission time [s]")
    ap.add_argument("--record-bag", type=Path, help="record /fmu/out topics to this new bag directory")
    args = ap.parse_args()

    conn = mavutil.mavlink_connection(args.url, source_system=245)
    log(f"waiting for PX4 heartbeat on {args.url}")
    conn.wait_heartbeat(timeout=60)
    log(f"PX4 system {conn.target_system} component {conn.target_component}")
    stop = threading.Event()
    start_heartbeat(conn, stop)
    recorder = BagRecorder(args.record_bag.expanduser()) if args.record_bag else None
    tracker = MissionTracker()
    try:
        home_lat, home_lon = wait_home(conn, timeout_s=60)
        log(f"home {home_lat:.7f}, {home_lon:.7f} (WGS84)")
        items = build_square_mission(home_lat, home_lon, args.side, args.alt)
        upload_mission(conn, items, timeout_s=30)
        log(f"mission uploaded: {len(items)} items (takeoff, 4 waypoints, RTL)")
        request_landed_state(conn)
        if recorder:
            recorder.start()
        arm_when_ready(conn, timeout_s=90)
        log("armed")
        result = send_command(conn, mavutil.mavlink.MAV_CMD_MISSION_START, 0, len(items) - 1)
        if result != mavutil.mavlink.MAV_RESULT_ACCEPTED:
            raise RuntimeError(f"MISSION_START not accepted (MAV_RESULT={result})")
        tracker.started = True
        log("mission started")
        if monitor_flight(conn, tracker, timeout_s=args.timeout):
            log(f"disarmed; recording {RECORD_TAIL_S:.0f} s more" if recorder else "disarmed")
            time.sleep(RECORD_TAIL_S if recorder else 0)
        elif not tracker.success:
            raise TimeoutError(f"flight not over in {args.timeout:.0f} s (reached items: {sorted(tracker.reached)})")
        if not tracker.success:
            raise RuntimeError(f"flight ended without success: {tracker.reason()}")
        log(tracker.completion_message())
        return 0
    except (TimeoutError, RuntimeError) as err:
        log(f"MISSION FAILED: {err}")
        return 1
    finally:
        stop.set()
        if recorder:
            recorder.stop()


if __name__ == "__main__":
    sys.exit(main())
