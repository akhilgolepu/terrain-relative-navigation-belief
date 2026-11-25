"""
Consumer policy: what a planner does with each NavBelief validity state (software only).

  STRONG          NORMAL            use the pose as is
  UNCERTAIN       FLAG_DEGRADED     use the pose, flag navigation as degraded
  AGING           REQUEST_FIX_SLOW  use the pose, ask for a position fix and slow down
  DO_NOT_PUBLISH  HOLD_FALLBACK     ignore the pose; hold the last GOOD state (the last STRONG or
                                    UNCERTAIN belief) and publish a fallback request
The policy only decides; it never commands a vehicle.
"""
from __future__ import annotations

from dataclasses import dataclass

STRONG, AGING, UNCERTAIN, DO_NOT_PUBLISH = 0, 1, 2, 3   # NavBelief constants
ACTIONS = {STRONG: 'NORMAL', UNCERTAIN: 'FLAG_DEGRADED', AGING: 'REQUEST_FIX_SLOW',
           DO_NOT_PUBLISH: 'HOLD_FALLBACK'}
GOOD = (STRONG, UNCERTAIN)


@dataclass
class Decision:
    """One decision: the action, whether it changed, the pose to use and a log line."""

    action: str
    changed: bool
    use_pose: tuple | None       # (east, north, var_e, var_n) to act on, or None
    held: bool                   # True if use_pose is the held last good state
    text: str


class Policy:
    """Stateful policy: remembers the last good belief and the previous action."""

    def __init__(self):
        """Start with no good state and no action."""
        self.last_good: tuple | None = None
        self.last_good_t: float | None = None
        self.action: str | None = None

    def step(self, t: float, validity: int, pose: tuple, reason: str) -> Decision:
        """Return the decision for one belief (pose = (east, north, var_e, var_n))."""
        if validity not in ACTIONS:
            validity = DO_NOT_PUBLISH
        action = ACTIONS[validity]
        if validity in GOOD:
            self.last_good, self.last_good_t = pose, t
        held = validity == DO_NOT_PUBLISH
        use = self.last_good if held else pose
        changed = action != self.action
        self.action = action
        if held:
            age = 'none' if self.last_good_t is None else f'{t - self.last_good_t:.0f} s old'
            text = f'{action}: belief not publishable ({reason}); holding last good state ({age})'
        else:
            text = f'{action}: {reason}'
        return Decision(action, changed, use, held, text)
