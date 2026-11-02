import unittest
from types import SimpleNamespace

from nao_fair_autostart.service import Service
from nao_fair_autostart.touch import TouchClassifier


class TouchTest(unittest.TestCase):
    def test_tap_waits_unless_double_tap_is_unarmed(self):
        touch = TouchClassifier()
        self.assertIsNone(touch.down("head", 0))
        touch.up("head", 0.1)
        self.assertEqual(touch.tick(0.49), [])
        self.assertEqual(touch.tick(0.5), [("head", "tap")])

        touch = TouchClassifier()
        touch.down("head", 0)
        touch.up("head", 0.1)
        self.assertIsNone(touch.down("head", 0.14))
        self.assertEqual(touch.tick(0.5), [("head", "tap")])

        touch = TouchClassifier()
        touch.down("head", 0)
        touch.up("head", 0.1)
        self.assertEqual(touch.down("head", 0.2), "double_tap")
        touch.up("head", 0.3)
        self.assertEqual(touch.tick(1), [])

        touch = TouchClassifier()
        touch.down("head", 0)
        self.assertEqual(touch.tick(0.6), [("head", "long_press")])
        touch.up("head", 0.8)
        self.assertEqual(touch.tick(2), [])

        touch = TouchClassifier()
        touch.down("head", 0)
        self.assertEqual(touch.up("head", 0.1, False), "tap")
        self.assertEqual(touch.tick(1), [])
        self.assertIsNone(touch.down("head", 0.14))
        self.assertIsNone(touch.up("head", 0.145))
        self.assertEqual(touch.tick(1), [])
        self.assertIsNone(touch.down("head", 0.16))
        self.assertEqual(touch.up("head", 0.2, False), "tap")

        touch = TouchClassifier()
        touch.down("head", 0)
        touch.up("head", 0.1)
        touch.down("hand", 0)
        touch.up("hand", 0.1)
        self.assertEqual(touch.flush(0.12, lambda sensor: sensor == "hand"), [("head", "tap")])
        self.assertIsNone(touch.down("head", 0.14))
        self.assertIsNone(touch.up("head", 0.145))
        self.assertEqual(touch.tick(0.5), [("hand", "tap")])
        self.assertEqual(touch.tick(1), [])

        touch = TouchClassifier()
        touch.down("head", 0)
        touch.up("head", 0.1)
        self.assertEqual(touch.flush(0.2, lambda sensor: False), [("head", "tap")])
        self.assertIsNone(touch.down("head", 0.21))
        self.assertEqual(touch.up("head", 0.22, False), "tap")

    def test_release_runs_immediately_when_the_saved_double_tap_has_no_action(self):
        session = SimpleNamespace(service=lambda name: object())
        service = Service(session, "unused")
        service.engine.assignment = {
            "triggers": {"head": {"double_tap": {"enabled": True, "action": None}}}
        }
        seen = []
        service._run_gesture = lambda sensor, gesture: seen.append((sensor, gesture))
        service.now = lambda: 10

        pressed = service._pressed("head")
        pressed(1)
        pressed(0)

        self.assertEqual(seen, [("head", "tap")])
        self.assertFalse(service._double_tap_armed("hand"))
        service.engine.assignment["triggers"]["hand"] = {
            "double_tap": {"enabled": True, "action": "wave"}
        }
        self.assertTrue(service._double_tap_armed("hand"))
        service.engine.assignment["triggers"]["hand"]["double_tap"]["enabled"] = False
        self.assertFalse(service._double_tap_armed("hand"))
