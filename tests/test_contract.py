from __future__ import unicode_literals

import json
import os
import tempfile
import unittest

from nao_fair_autostart.contract import (
    ACK_SEQ,
    ASSIGNMENT,
    action_for,
    fold_phrase,
    parse_assignment,
    read_assignment,
    write_assignment,
)


def document(**overrides):
    body = {
        "armed": True,
        "volume": 70,
        "speech_speed": 100,
        "tts_language": "German",
        "replacements": [["Wildau", "Vill-dau"]],
        "triggers": {
            sensor: {"action": None, "phrase": "", "motion": None, "enabled": True}
            for sensor in (
                "front_head",
                "middle_head",
                "rear_head",
                "left_hand",
                "right_hand",
                "left_bumper",
                "right_bumper",
            )
        },
    }
    body.update(overrides)
    return body


class AssignmentTest(unittest.TestCase):
    def test_keys_are_the_naoqi_names_the_app_writes(self):
        self.assertEqual(ASSIGNMENT, "NAOFair/Autostart/Assignment")
        self.assertEqual(ACK_SEQ, "NAOFair/Autostart/AckSeq")

    def test_missing_switch_is_rejected_and_a_file_round_trips(self):
        with self.assertRaises(ValueError):
            parse_assignment(json.dumps({"armed": "yes"}))
        directory = tempfile.mkdtemp()
        path = os.path.join(directory, "assignment.json")
        write_assignment(path, document())
        self.assertTrue(read_assignment(path)["armed"])
        self.assertEqual(read_assignment(path)["replacements"], [["Wildau", "Vill-dau"]])

    def test_conversation_actions_and_speech(self):
        self.assertIsNone(action_for({"action": "start_conversation", "enabled": True}))
        self.assertIsNone(action_for({"action": "toggle_conversation", "enabled": True}))
        self.assertIsNone(action_for({"action": "stop_and_clear", "enabled": True}))
        self.assertEqual(action_for({"action": "stop_conversation", "enabled": True}), ("stop_speech",))
        self.assertEqual(
            action_for({"action": "speak", "phrase": "Hallo", "enabled": True}),
            ("speak", "Hallo", "plain", None),
        )
        self.assertEqual(
            action_for({"action": "speak", "phrase": "Hallo", "enabled": True, "delivery": "motion", "motion": "nod"}),
            ("speak", "Hallo", "motion", "nod"),
        )
        self.assertEqual(
            action_for({"action": "dialog_next", "enabled": True}),
            ("dialog_next", True),
        )
        self.assertEqual(
            action_for({"action": "dialog_next", "enabled": True, "yield_next": False}),
            ("dialog_next", False),
        )
        self.assertEqual(
            action_for({"action": "dialog_reset", "enabled": True, "phrase": " Nochmal "}),
            ("dialog_reset", u" Nochmal "),
        )
        self.assertIsNone(action_for({"action": "speak", "phrase": "  ", "enabled": True}))
        self.assertIsNone(action_for({"action": "speak", "phrase": "Hallo", "enabled": False}))
        self.assertEqual(action_for({"action": "motion", "motion": "nod", "enabled": True}), ("motion", "nod"))

    def test_phrase_folding_replaces_whole_words_after_punctuation(self):
        folded = fold_phrase(u"„Wildau“ ist wildauer.", [["Wildau", "Vill-dau"]])
        self.assertEqual(folded, u'"Vill-dau" ist wildauer.')


if __name__ == "__main__":
    unittest.main()
