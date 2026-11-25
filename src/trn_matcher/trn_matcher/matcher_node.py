"""
ROS 2 node: replay UAV-VisLoc frames through the frozen terrain matcher, publish TerrainFix.

Minimal wrapper for week 4. Each timer tick takes the next frame of the chosen split (aerial
image, the loader's seeded prior, a map patch around it; trn_matcher.frames), runs
FeatureMatcher with the frozen settings and publishes trn_msgs/TerrainFix on 'terrain_fix'.
header.frame_id = 'enu_<region>' (the region's local ENU frame, origin in splits.json).
The label (true position) is not published: consumers must not see it.

ROS parameters
  data_root ('~/data/visloc/flights'), splits_file (repo eval/splits.json),
  split ('tune'), allow_test (false; the test split is refused unless true, Akhil's call),
  rate_hz (1.0), every (1: every k-th frame), loop (false), prior_sigma_m (50.0),
  window_m (150.0), map_m_per_px (0.5), image_px (1024), accept_all (false: publish only gate
  passes as fixes; true: every candidate, with the gate verdict in gate_pass).
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import time

import rclpy
from rclpy.node import Node
from trn_msgs.msg import TerrainFix

from .frames import footprints, prepare_frame
from .interface import as_result, SearchSpace
from .loader import LoaderConfig, VisLocDataset
from .matcher import FeatureMatcher

REPO_SPLITS = Path(__file__).resolve().parents[3] / 'eval' / 'splits.json'


def fix_message(res, diag: dict, frame, search: SearchSpace, dt: float) -> TerrainFix:
    """Fill a TerrainFix (without header stamp) from a match result and its diagnostics."""
    nan = math.nan
    m = TerrainFix()
    m.header.frame_id = f'enu_{frame.region}'
    m.has_fix = res is not None
    m.east, m.north, m.scale, m.rot_deg, m.score = res.astuple() if res else (nan,) * 5
    m.gate_pass = bool(diag.get('gate_pass', diag.get('accepted', False)))
    m.peak = float(diag.get('peak', nan))
    m.peak_ratio = float(diag.get('ratio', nan))
    m.overlap_valid_frac = float(diag.get('overlap_valid_frac', nan))
    m.prior_east, m.prior_north = frame.prior.east, frame.prior.north
    m.prior_sigma_m, m.footprint_m = frame.prior.sigma_m, frame.prior.footprint_m
    m.search_window_m = search.window_m
    m.match_time_s = dt
    m.reason = '' if res else str(diag.get('reason', 'no fix'))
    m.source = f'{frame.flight}/{frame.filename}'
    return m


class MatcherNode(Node):
    """Replay a split and publish one TerrainFix per frame."""

    def __init__(self):
        """Read parameters, load the split and start the timer."""
        super().__init__('terrain_matcher')
        p = {k: self.declare_parameter(k, v).value for k, v in {
            'data_root': str(Path.home() / 'data/visloc/flights'), 'splits_file': str(REPO_SPLITS),
            'split': 'tune', 'allow_test': False, 'rate_hz': 1.0, 'every': 1, 'loop': False,
            'prior_sigma_m': 50.0, 'window_m': 150.0, 'map_m_per_px': 0.5, 'image_px': 1024,
            'accept_all': False,
        }.items()}
        if p['split'] == 'test' and not p['allow_test']:
            raise RuntimeError('refusing the test split (set allow_test only when Akhil says so)')
        self.p = p
        splits = json.loads(Path(p['splits_file']).read_text())
        self.ds = VisLocDataset(Path(p['data_root']), splits, p['split'],
                                LoaderConfig(prior_sigma_m=p['prior_sigma_m'],
                                             image_px=p['image_px']))
        self.foot = footprints(self.ds)
        self.search = SearchSpace(window_m=p['window_m'])
        self.matcher = FeatureMatcher(accept_all=bool(p['accept_all']))
        self.frames = list(range(0, len(self.ds), max(1, int(p['every']))))
        self.k = 0
        self.pub = self.create_publisher(TerrainFix, 'terrain_fix', 10)
        self.timer = self.create_timer(1.0 / p['rate_hz'], self.tick)
        self.get_logger().info(
            f"split {p['split']}: {len(self.frames)} frames, settings "
            f'{self.matcher.settings_dict()}, publishing trn_msgs/TerrainFix on terrain_fix')

    def tick(self):
        """Match the next frame and publish the result."""
        if self.k >= len(self.frames):
            if not self.p['loop']:
                self.get_logger().info('replay finished')
                self.timer.cancel()
                return
            self.k = 0
        fr = prepare_frame(self.ds, self.frames[self.k], self.search, self.p['prior_sigma_m'],
                           self.p['map_m_per_px'], self.foot)
        self.k += 1
        t0 = time.perf_counter()
        res = as_result(self.matcher.match(fr.image, fr.patch, fr.prior, self.search))
        dt = time.perf_counter() - t0
        msg = fix_message(res, self.matcher.last_diag, fr, self.search, dt)
        msg.header.stamp = self.get_clock().now().to_msg()
        self.pub.publish(msg)
        state = (f'fix E {msg.east:.1f} N {msg.north:.1f}' if msg.has_fix
                 else f'no fix ({msg.reason})')
        self.get_logger().info(f'{msg.source}: {state}, peak {msg.peak:.3f}, '
                               f'ratio {msg.peak_ratio:.2f}, {dt:.2f} s')


def main(args=None):
    """Run the node until the replay ends or Ctrl-C."""
    rclpy.init(args=args)
    node = MatcherNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
