from __future__ import unicode_literals

import unittest

from nao_fair_autostart.gestures import plan


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


if __name__ == "__main__":
    unittest.main()
