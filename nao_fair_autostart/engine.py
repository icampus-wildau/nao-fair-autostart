"""When autostart handles a trigger, and when a connection holds it off.

Times are the robot's own clock. The laptop only bumps a sequence while it
still owns the triggers, so a skewed wall clock cannot expire the lease early.
"""

from __future__ import print_function

from nao_fair_autostart.contract import LEASE_TIMEOUT_SECS, action_for


class AutostartEngine(object):
    def __init__(self, timeout=LEASE_TIMEOUT_SECS):
        self.timeout = timeout
        self.assignment = None
        self.suppressed = False
        self.handling = False
        self.lease_seq = None
        self.lease_seen_at = None

    def load(self, document):
        self.assignment = document
        return self._sync_handling(entered=True)

    def hold(self, seq, now):
        self.lease_seq = seq
        self.lease_seen_at = now
        if self.suppressed:
            return []
        self.suppressed = True
        self.handling = False
        return ["stop_all"]

    def release(self, now):
        del now
        self.lease_seen_at = None
        self.lease_seq = None
        if not self.suppressed:
            return []
        self.suppressed = False
        return ["stop_all"] + self._sync_handling(entered=False)

    def tick(self, now):
        if not self.suppressed or self.lease_seen_at is None:
            return []
        if now - self.lease_seen_at < self.timeout:
            return []
        self.suppressed = False
        self.lease_seen_at = None
        self.lease_seq = None
        return ["stop_all"] + self._sync_handling(entered=False)

    def press(self, sensor_id):
        if not self.handling or not self.assignment:
            return None
        triggers = self.assignment.get("triggers") or {}
        return action_for(triggers.get(sensor_id))

    def _armed(self):
        return bool(self.assignment and self.assignment.get("armed"))

    def _sync_handling(self, entered):
        was = self.handling
        self.handling = self._armed() and not self.suppressed
        if not self.handling:
            return []
        effects = ["apply_audio"]
        if not was:
            effects.append("disable_life")
        elif not entered:
            effects.append("disable_life")
        return effects
