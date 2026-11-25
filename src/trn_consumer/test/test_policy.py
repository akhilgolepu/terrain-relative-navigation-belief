"""Tests for the consumer policy."""
from trn_consumer.policy import AGING, DO_NOT_PUBLISH, Policy, STRONG, UNCERTAIN


def test_actions_per_state():
    p = Policy()
    assert p.step(0.0, STRONG, (1, 2, 4, 4), 'ok').action == 'NORMAL'
    assert p.step(1.0, UNCERTAIN, (1, 2, 4, 4), 'ok').action == 'FLAG_DEGRADED'
    assert p.step(2.0, AGING, (1, 2, 400, 400), 'ok').action == 'REQUEST_FIX_SLOW'
    assert p.step(3.0, DO_NOT_PUBLISH, (9, 9, 1e4, 1e4), 'ok').action == 'HOLD_FALLBACK'


def test_hold_uses_last_good_state_not_aging_or_bad_pose():
    p = Policy()
    p.step(0.0, STRONG, (10.0, 20.0, 4.0, 4.0), 'ok')
    p.step(5.0, UNCERTAIN, (11.0, 21.0, 9.0, 9.0), 'ok')
    p.step(9.0, AGING, (30.0, 40.0, 900.0, 900.0), 'aging')
    d = p.step(20.0, DO_NOT_PUBLISH, (99.0, 99.0, 1e5, 1e5), 'sigma too big')
    assert d.held and d.use_pose == (11.0, 21.0, 9.0, 9.0)
    assert '15 s old' in d.text and d.changed
    assert not p.step(23.0, DO_NOT_PUBLISH, (99.0, 99.0, 1e5, 1e5), 'x').changed


def test_hold_before_any_good_state_and_unknown_validity():
    p = Policy()
    d = p.step(0.0, DO_NOT_PUBLISH, (0, 0, 1, 1), 'no fix yet')
    assert d.held and d.use_pose is None and 'none' in d.text
    assert p.step(1.0, 7, (0, 0, 1, 1), '?').action == 'HOLD_FALLBACK'
