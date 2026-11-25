"""
ROS 2 replay node: SYNTHETIC odometry and recorded terrain-fix candidates for one flight.

Reads eval/results/week6/inputs_<flight>.csv (frozen-matcher accept-all candidates, labels used
only to generate the SYNTHETIC odometry; labels are never published) and publishes, per frame:
  odom          nav_msgs/Odometry, pose = SYNTHETIC odometry position (label path + sampled
                floor/random-walk drift, trn_fusion.odometry_sim), frame 'odom_synthetic'
  terrain_fix   trn_msgs/TerrainFix for frames with a candidate (east/north, peak_ratio,
                gate_pass), frame 'enu_<region>'
Before the first frame it publishes the first-frame prior on 'initial_prior'
(PoseWithCovarianceStamped, transient local). Stamps are dataset time (t0 + t_s), so fix ages
are in flight seconds whatever the replay speed.
ROS parameters: flight ('10'; '11' refused), drift_pct (1.0), seed (0), speed (10.0: x real
time), use_fixes (true), fix_stop_fraction (1.0: fixes stop after this fraction of the frames,
for outage scenarios), inputs_dir (repo eval/results/week6).
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

from geometry_msgs.msg import PoseWithCovarianceStamped
from nav_msgs.msg import Odometry
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile
from rclpy.time import Time
from trn_msgs.msg import TerrainFix

from .config import load_config
from .odometry_sim import drift_b, simulate

INPUTS = Path(__file__).resolve().parents[3] / 'eval' / 'results' / 'week6'
T0_NS = 1_700_000_000 * 10 ** 9   # arbitrary epoch for dataset time


def stamp(t_s: float):
    """Return a builtin_interfaces/Time for dataset time t_s."""
    return Time(nanoseconds=T0_NS + int(round(t_s * 1e9))).to_msg()


class ReplayNode(Node):
    """Publish one flight's SYNTHETIC odometry and recorded fix candidates."""

    def __init__(self):
        """Load the inputs, generate the odometry and start the timer."""
        super().__init__('trn_replay')
        p = {k: self.declare_parameter(k, v).value for k, v in {
            'flight': '10', 'drift_pct': 1.0, 'seed': 0, 'speed': 10.0, 'use_fixes': True,
            'fix_stop_fraction': 1.0, 'inputs_dir': str(INPUTS)}.items()}
        if str(p['flight']) == '11':
            raise RuntimeError('refusing flight 11 (test split)')
        cfg = load_config()
        so = cfg['synthetic_odometry']
        rows = list(csv.DictReader((Path(p['inputs_dir']) / f"inputs_{p['flight']}.csv").open()))
        self.rows = rows
        labels = np.array([[float(r['true_e']), float(r['true_n'])] for r in rows])
        level = float(p['drift_pct'])
        li = so['drift_levels_pct'].index(level) if level in so['drift_levels_pct'] else 99
        b = drift_b(level, so['reference_distance_m'])
        self.odo = simulate(labels, b, so['floor_a_m'], seed=1000 * li + int(p['seed']))
        self.t = [float(r['t_s']) for r in rows]
        self.frame = f"enu_{rows[0]['region']}"
        self.p, self.k = p, 0
        latched = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.pub_prior = self.create_publisher(PoseWithCovarianceStamped, 'initial_prior', latched)
        self.pub_odom = self.create_publisher(Odometry, 'odom', 50)
        self.pub_fix = self.create_publisher(TerrainFix, 'terrain_fix', 50)
        prior = PoseWithCovarianceStamped()
        prior.header.stamp, prior.header.frame_id = stamp(self.t[0]), self.frame
        prior.pose.pose.position.x = float(rows[0]['prior_e'])
        prior.pose.pose.position.y = float(rows[0]['prior_n'])
        prior.pose.pose.orientation.w = 1.0
        cov = [0.0] * 36
        cov[0] = cov[7] = cfg['prior']['sigma_m'] ** 2
        prior.pose.covariance = cov
        self.pub_prior.publish(prior)
        self.timer = self.create_timer(0.5, self.tick)   # first frame after 0.5 s
        self.get_logger().info(
            f"replaying flight {p['flight']}: {len(rows)} frames, SYNTHETIC odometry at "
            f"{level} % drift (seed {p['seed']}), speed x{p['speed']}, fixes {p['use_fixes']}")

    def tick(self):
        """Publish frame k (odometry, then its fix), schedule frame k + 1."""
        self.timer.cancel()
        if self.k == 0 and (self.pub_odom.get_subscription_count() == 0
                            or self.pub_fix.get_subscription_count() == 0):
            self.get_logger().info('waiting for subscribers on odom and terrain_fix')
            self.timer = self.create_timer(0.5, self.tick)
            return
        if self.k >= len(self.rows):
            self.get_logger().info('replay finished')
            return
        k, r = self.k, self.rows[self.k]
        o = Odometry()
        o.header.stamp, o.header.frame_id = stamp(self.t[k]), 'odom_synthetic'
        o.child_frame_id = 'base_link'
        o.pose.pose.position.x, o.pose.pose.position.y = (float(v) for v in self.odo[k])
        o.pose.pose.orientation.w = 1.0
        self.pub_odom.publish(o)
        fixes_on = k < float(self.p['fix_stop_fraction']) * len(self.rows)
        if self.p['use_fixes'] and fixes_on and int(r['has_fix']):
            f = TerrainFix()
            f.header.stamp, f.header.frame_id = stamp(self.t[k]), self.frame
            f.has_fix = True
            f.east, f.north = float(r['fix_e']), float(r['fix_n'])
            f.peak_ratio = math.exp(float(r['log_ratio']))
            f.gate_pass = bool(int(r['gate_pass']))
            f.source = f"{self.p['flight']}/{r['image']}"
            self.pub_fix.publish(f)
        self.k += 1
        if self.k < len(self.rows):
            dt = (self.t[self.k] - self.t[k]) / float(self.p['speed'])
            self.timer = self.create_timer(max(dt, 1e-3), self.tick)
        else:
            self.get_logger().info(f'replay finished: {len(self.rows)} frames published')


def main(args=None):
    """Run the replay until it ends or Ctrl-C."""
    rclpy.init(args=args)
    node = ReplayNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
