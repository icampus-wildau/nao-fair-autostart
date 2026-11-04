import os
import tempfile
import threading
import unittest
from types import SimpleNamespace

from nao_fair_autostart.service import Service


class Future(object):
    def __init__(self, running):
        self.running = running

    def isRunning(self):
        return self.running

    def wait(self):
        return None


class Speech(object):
    def __init__(self):
        self.calls = []

    def stopAll(self):
        self.calls.append("stop")

    def say(self, text, _async=False):
        self.calls.append(text)
        return Future(True)


class Memory(object):
    def __init__(self):
        self.data = {}

    def insertData(self, key, value):
        self.data[key] = value

    def raiseEvent(self, key, value):
        return None

    def getData(self, key):
        return self.data.get(key, "")


def session(speech, memory):
    def service(name):
        if name == "ALTextToSpeech":
            return speech
        if name == "ALMemory":
            return memory
        if name == "ALMotion":
            return SimpleNamespace(stopMove=lambda: None)
        return SimpleNamespace(setState=lambda *args: None, say=speech.say, setOutputVolume=lambda n: None, setParameter=lambda *a: None, setLanguage=lambda *a: None)

    return SimpleNamespace(service=service)


class DialogPlaybackTest(unittest.TestCase):
    def setUp(self):
        self.speech = Speech()
        self.directory = tempfile.mkdtemp()
        self.service = Service(session(self.speech, Memory()), os.path.join(self.directory, "assignment.json"))
        self.service.engine.assignment = {
            "dialogs": [{
                "id": "tour",
                "lines": [
                    {"id": "a", "speaker": "nao", "text": "A"},
                    {"id": "b", "speaker": "nao", "text": "B"},
                ],
            }],
            "active_dialog_id": "tour",
            "replacements": [],
        }
        self.service._position = {"dialog_id": "tour", "line_id": "a", "seq": 1}
        self.service._speech_call = Future(True)
        self.service._voice = "line"

    def test_a_yielding_next_line_waits_and_a_cutting_one_speaks(self):
        self.service._play_dialog("dialog_next", True)
        self.assertEqual(self.speech.calls, [])
        self.service._play_dialog("dialog_next", False)
        self.assertEqual(self.speech.calls, ["stop", "B"])

    def test_yield_ends_when_the_words_end(self):
        self.service._speech_call.running = False
        self.service._play_dialog("dialog_next", True)
        self.assertEqual(self.speech.calls, ["stop", "B"])

    def test_reset_clears_the_position_and_speaks_a_plain_announcement(self):
        self.service._reset_dialog(u" Nochmal ")
        self.service._speech_worker.join(1)
        self.assertIsNone(self.service._position)
        self.assertEqual(self.speech.calls, ["stop", "Nochmal"])

    def test_a_blank_announcement_stays_silent(self):
        self.service._reset_dialog(u"   ")
        self.assertIsNone(self.service._position)
        self.assertEqual(self.speech.calls, ["stop"])

    def test_reset_without_an_active_dialog_does_nothing(self):
        self.service.engine.assignment = {"dialogs": [], "active_dialog_id": None, "replacements": []}
        self.service._reset_dialog(u"Hi")
        self.assertEqual(self.service._position["line_id"], "a")
        self.assertEqual(self.speech.calls, [])


class ReturningMotion(object):
    def __init__(self):
        self.commands = []
        self.started = threading.Event()
        self.release = threading.Event()

    def stopMove(self):
        self.commands.append("stopMove")
        self.release.set()

    def getAngles(self, names, use_sensors):
        del use_sensors
        return [0.0] * len(names)

    def getLimits(self, name):
        del name
        return [[-2.0, 2.0, 1.0, 1.0]]

    def setStiffnesses(self, chain, stiffness):
        self.commands.append(("stiff", chain, stiffness))

    def angleInterpolation(self, names, angles, times, is_absolute):
        del names, times, is_absolute
        self.commands.append(("move", angles))
        if len([item for item in self.commands if item[0] == "move"]) == 1:
            self.started.set()
            self.release.wait(2)


class ResetMotionTest(unittest.TestCase):
    def test_reset_during_a_gesture_returns_home_and_releases_stiffness(self):
        speech = Speech()
        directory = tempfile.mkdtemp()
        service = Service(session(speech, Memory()), os.path.join(directory, "assignment.json"))
        service.engine.assignment = {
            "dialogs": [{"id": "tour", "lines": [{"id": "a", "speaker": "nao", "text": "A"}]}],
            "active_dialog_id": "tour",
            "replacements": [],
        }
        motion = ReturningMotion()
        service.motion = motion
        service._accompanying = True
        service._voice = "line"
        service._speech_call = Future(True)
        service._move("nod")
        self.assertTrue(motion.started.wait(1))

        service._reset_dialog(u"")
        service._worker.join(1)

        moves = [item for item in motion.commands if item[0] == "move"]
        self.assertEqual(len(moves), 2)
        self.assertEqual(motion.commands[-1], ("stiff", "Head", 0.0))
        self.assertFalse(service._motion_stop.is_set())


if __name__ == "__main__":
    unittest.main()
