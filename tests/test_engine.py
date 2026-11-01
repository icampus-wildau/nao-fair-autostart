from __future__ import unicode_literals

import unittest

from nao_fair_autostart.engine import AutostartEngine


def armed_document():
    return {
        "armed": True,
        "volume": 40,
        "speech_speed": 90,
        "tts_language": "German",
        "replacements": [],
        "triggers": {
            "front_head": {"action": "toggle_conversation", "enabled": True},
            "middle_head": {"action": "speak", "phrase": "Hallo", "enabled": True},
            "rear_head": {"action": "stop_and_clear", "enabled": True},
            "left_hand": {"action": None, "enabled": True},
            "right_hand": {"action": "stop_conversation", "enabled": True},
            "left_bumper": {"action": "motion", "motion": "wave_left", "enabled": True},
            "right_bumper": {"action": "motion", "motion": "wave_right", "enabled": True},
        },
    }


class EngineTest(unittest.TestCase):
    def test_boot_with_the_switch_on_handles_presses_and_turns_life_off(self):
        engine = AutostartEngine()
        effects = engine.load(armed_document())
        self.assertEqual(effects, ["apply_audio", "disable_life"])
        self.assertIsNone(engine.press("front_head"))
        self.assertEqual(engine.press("middle_head"), ("speak", "Hallo"))
        self.assertEqual(engine.press("right_hand"), ("stop_speech",))
        self.assertEqual(engine.press("left_bumper"), ("motion", "wave_left"))

    def test_a_missing_assignment_stays_quiet(self):
        engine = AutostartEngine(timeout=20)
        self.assertIsNone(engine.press("middle_head"))
        self.assertEqual(engine.tick(100), [])

    def test_a_lease_suppresses_and_expiry_cuts_speech_then_handles_again(self):
        engine = AutostartEngine(timeout=20)
        engine.load(armed_document())
        self.assertEqual(engine.hold(1, 10), ["stop_all"])
        self.assertIsNone(engine.press("middle_head"))
        self.assertEqual(engine.hold(2, 11), [])
        self.assertEqual(engine.tick(30), [])
        effects = engine.tick(31)
        self.assertEqual(effects, ["stop_all", "apply_audio", "disable_life"])
        self.assertEqual(engine.press("middle_head"), ("speak", "Hallo"))

    def test_an_explicit_release_resumes_immediately(self):
        engine = AutostartEngine(timeout=20)
        engine.load(armed_document())
        engine.hold(1, 5)
        effects = engine.release(5)
        self.assertEqual(effects, ["stop_all", "apply_audio", "disable_life"])
        self.assertFalse(engine.suppressed)

    def test_the_switch_off_does_not_touch_life_when_the_lease_ends(self):
        engine = AutostartEngine()
        document = armed_document()
        document["armed"] = False
        self.assertEqual(engine.load(document), [])
        engine.hold(1, 0)
        self.assertEqual(engine.release(1), ["stop_all"])
        self.assertFalse(engine.handling)

    def test_a_new_assignment_while_connected_does_not_apply_audio(self):
        engine = AutostartEngine()
        engine.load(armed_document())
        engine.hold(1, 0)
        quieter = armed_document()
        quieter["volume"] = 10
        self.assertEqual(engine.load(quieter), [])
        self.assertEqual(engine.assignment["volume"], 10)


if __name__ == "__main__":
    unittest.main()
