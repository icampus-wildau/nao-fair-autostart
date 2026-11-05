from nao_fair_autostart.dialog import position_for, step
import unittest


class DialogSpeakersTest(unittest.TestCase):
    def test_human_lines_do_not_change_playback(self):
        dialog = {"id": "tour", "wrap": True, "lines": [
            {"id": "intro", "speaker": "human", "text": "Hallo"},
            {"id": "a", "text": "Hallo Mensch"},
            {"id": "question", "speaker": "human", "text": "Wie geht es dir?"},
            {"id": "b", "speaker": "nao", "text": "Gut"},
            {"id": "end", "speaker": "human", "text": "Danke"},
        ]}
        a = position_for("tour", "a", None)
        b = position_for("tour", "b", a)
        assert step(dialog, None, "dialog_next")["id"] == "a"
        assert step(dialog, a, "dialog_next")["id"] == "b"
        assert step(dialog, b, "dialog_previous")["id"] == "a"
        assert step(dialog, b, "dialog_next")["id"] == "a"
        assert step(dialog, a, "dialog_repeat")["id"] == "a"
        assert step({"id": "tour", "lines": [dialog["lines"][0]]}, None, "dialog_next") is None
