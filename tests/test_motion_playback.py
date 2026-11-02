from __future__ import unicode_literals

import threading
import unittest
from types import SimpleNamespace

from nao_fair_autostart.service import Service


class MotionPlaybackTest(unittest.TestCase):
    def test_a_second_press_still_ends_at_the_pose_from_the_start(self):
        rest = [0.4, 0.2, -0.5, -0.8, 0.1, 0.3]
        started = threading.Event()
        release = threading.Event()
        pose = {"angles": list(rest)}
        guard = threading.Lock()

        class Motion(object):
            def getAngles(self, names, use_sensors):
                del names, use_sensors
                with guard:
                    return list(pose["angles"])

            def setStiffnesses(self, chain, stiffness):
                del chain, stiffness

            def angleInterpolation(self, names, angles, times, is_absolute):
                del names, times, is_absolute
                with guard:
                    pose["angles"] = [series[-1] for series in angles]
                if not started.is_set():
                    started.set()
                    if not release.wait(2):
                        raise RuntimeError("gesture was not released")

            def stopMove(self):
                return None

        motion = Motion()
        session = SimpleNamespace(service=lambda name: motion if name == "ALMotion" else object())
        service = Service(session, "unused")

        service._move("wave_left")
        self.assertTrue(started.wait(1))
        first = service._worker
        try:
            service._move("wave_left")
        finally:
            release.set()
        first.join(2)
        if service._worker is not first:
            service._worker.join(2)

        self.assertFalse(first.is_alive())
        self.assertEqual(pose["angles"], rest)


if __name__ == "__main__":
    unittest.main()
