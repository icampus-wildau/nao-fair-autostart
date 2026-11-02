from __future__ import unicode_literals

import unittest

from nao_fair_autostart.gestures import plan, play


class GesturePlanTest(unittest.TestCase):
    def test_wave_nod_and_sit_match_the_laptop_motions(self):
        left = plan("wave_left")
        self.assertEqual(left["joints"][0], "LShoulderPitch")
        self.assertEqual(left["keyframes"][4], [-1.0, 1.0, -1.0, 1.0, -1.0, 1.0])
        right = plan("wave_right")
        self.assertLess(right["keyframes"][1][0], 0)
        nod = plan("nod")
        self.assertTrue(nod["relative"])
        self.assertEqual(nod["joints"], ["HeadPitch"])
        self.assertEqual(plan("sit"), {"kind": "posture", "name": "Sit", "release": True})
        self.assertFalse(plan("stand")["release"])


class _Motion(object):
    """ALMotion double: rejects a target outside the limits it reports."""

    def __init__(self, rest, limits):
        self.rest = list(rest)
        self.limits = limits
        self.commands = []

    def getAngles(self, names, use_sensors):
        del names, use_sensors
        return list(self.rest)

    def getLimits(self, name):
        low, high = self.limits[name]
        return [[low, high, 1.0, 1.0]]

    def setStiffnesses(self, chain, stiffness):
        self.commands.append(("stiff", chain, stiffness))

    def angleInterpolation(self, names, angles, times, is_absolute):
        del times, is_absolute
        for name, series in zip(names, angles):
            low, high = self.limits[name]
            for angle in series:
                if angle < low or angle > high:
                    raise RuntimeError("angle out of range: %s %s" % (name, angle))
        self.commands.append(("move", names, angles))


class GesturePlayTest(unittest.TestCase):
    def test_return_uses_the_pose_captured_at_the_start(self):
        limits = {
            "HeadPitch": (-0.67, 0.51),
        }
        motion = _Motion([0.05], limits)

        play(motion, None, "nod", lambda: False)

        self.assertEqual(
            [item[0] for item in motion.commands],
            ["stiff", "move", "move", "stiff"],
        )
        self.assertEqual(motion.commands[1][2], [[-0.05, 0.25, 0.05]])
        self.assertEqual(motion.commands[2][2], [[0.05]])
        self.assertEqual(motion.commands[-1], ("stiff", "Head", 0.0))

    def test_return_clamps_a_sensor_angle_the_robot_would_reject(self):
        # A limp elbow often reads past the command limit. angleInterpolation
        # then rejects the whole return, and the arm stays at the end of the wave.
        limits = {
            "LShoulderPitch": (-2.0857, 2.0857),
            "LShoulderRoll": (-0.3142, 1.3265),
            "LElbowYaw": (-2.0857, 2.0857),
            "LElbowRoll": (-1.5446, -0.0349),
            "LWristYaw": (-1.8238, 1.8238),
            "LHand": (0.0, 1.0),
        }
        rest = [0.4, 0.1, -0.4, -0.01, 0.2, 0.05]
        motion = _Motion(rest, limits)

        play(motion, None, "wave_left", lambda: False)

        moves = [item for item in motion.commands if item[0] == "move"]
        self.assertEqual(len(moves), 2)
        returned = [series[0] for series in moves[1][2]]
        self.assertAlmostEqual(returned[3], -0.0349)
        for index, angle in enumerate(rest):
            if index == 3:
                continue
            self.assertAlmostEqual(returned[index], angle)
        self.assertEqual(motion.commands[-1][0], "stiff")
        self.assertEqual(motion.commands[-1][2], 0.0)


if __name__ == "__main__":
    unittest.main()
