"""Test TerrainFix filling (needs the built trn_msgs; skipped otherwise)."""
import math

import numpy as np
import pytest

try:   # needs the built trn_msgs; a module-level importorskip skipped every test in this folder
    import trn_msgs.msg  # noqa: F401
    from trn_matcher.frames import Frame
    from trn_matcher.interface import MatchResult, Prior, SearchSpace
    from trn_matcher.matcher_node import fix_message
    HAVE_MSGS = True
except ImportError:
    HAVE_MSGS = False

pytestmark = pytest.mark.skipif(not HAVE_MSGS, reason='trn_msgs not built/sourced')


def _frame():
    return Frame('hebei_huailai', '10', '10_0001.JPG', None, None,
                 Prior(1.0, 2.0, 50.0, 123.6), np.array([0.0, 0.0]))


def test_fix_message_with_fix():
    res = MatchResult(10.0, 20.0, 1.1, -2.0, 0.4, None)
    diag = {'peak': 0.4, 'ratio': 1.3, 'overlap_valid_frac': 0.97, 'gate_pass': True}
    m = fix_message(res, diag, _frame(), SearchSpace(window_m=150.0), 1.5)
    assert m.has_fix and (m.east, m.north, m.scale, m.rot_deg) == (10.0, 20.0, 1.1, -2.0)
    assert m.header.frame_id == 'enu_hebei_huailai' and m.source == '10/10_0001.JPG'
    assert (m.peak, m.peak_ratio, m.overlap_valid_frac) == (0.4, 1.3, 0.97)
    assert m.search_window_m == 150.0 and m.reason == '' and m.gate_pass


def test_fix_message_without_fix_keeps_diagnostics():
    diag = {'peak': 0.1, 'ratio': 1.01, 'reason': 'ratio below ratio_min'}
    m = fix_message(None, diag, _frame(), SearchSpace(), 1.0)
    assert not m.has_fix and math.isnan(m.east) and math.isnan(m.north)
    assert m.peak == 0.1 and m.reason == 'ratio below ratio_min'
