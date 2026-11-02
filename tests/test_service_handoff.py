import threading
import unittest
from types import SimpleNamespace

from nao_fair_autostart.contract import LEASE_ACK_SEQ
from nao_fair_autostart.service import Service


class SpeakTest(unittest.TestCase):
    def test_speak_uses_qi_async_and_keeps_the_future(self):
        class Speech:
            def __init__(self):
                self.calls = []
                self.future = object()

            def stopAll(self):
                self.calls.append("stop")

            def say(self, text, _async=False):
                self.calls.append((text, _async))
                return self.future

        speech = Speech()
        services = {"ALTextToSpeech": speech}
        session = SimpleNamespace(service=lambda name: services.get(name, object()))
        service = Service(session, "unused")
        service.engine.assignment = {"replacements": []}

        service._speak("Hallo")
        service._speech_worker.join(1)

        self.assertEqual(speech.calls, [("Hallo", True)])
        self.assertIs(service._speech_call, speech.future)

    def test_the_same_speak_action_does_not_queue_and_a_different_one_does(self):
        started = threading.Event()
        release = threading.Event()

        class Future:
            def wait(self):
                release.wait(2)

        class Speech:
            def __init__(self):
                self.calls = []

            def stopAll(self):
                release.set()

            def say(self, text, _async=False):
                self.calls.append(text)
                started.set()
                return Future()

        speech = Speech()
        session = SimpleNamespace(service=lambda name: speech)
        service = Service(session, "unused")
        service.engine.assignment = {"replacements": []}

        service._speak("Hallo")
        self.assertTrue(started.wait(1))
        service._speak("Hallo")
        service._speak("Tschüss")
        self.assertEqual(speech.calls, ["Hallo"])
        self.assertEqual([item[1] for item in service._speech_queue], ["Tschüss"])
        release.set()
        service._speech_worker.join(1)
        self.assertEqual(speech.calls, ["Hallo", "Tschüss"])
        self.assertEqual(service._speech_queue, [])


def test_lease_ack_waits_until_motion_worker_has_stopped():
    started = threading.Event()
    finish = threading.Event()
    acknowledged = threading.Event()

    class Memory:
        def getData(self, key):
            return "hold"

        def raiseEvent(self, key, value):
            if key == LEASE_ACK_SEQ:
                acknowledged.set()

    class Motion:
        def stopMove(self):
            pass

    class Speech:
        def stopAll(self):
            pass

    services = {"ALMemory": Memory(), "ALMotion": Motion(), "ALTextToSpeech": Speech()}
    session = SimpleNamespace(service=lambda name: services.get(name, object()))
    service = Service(session, "unused")
    def motion():
        started.set()
        finish.wait(2)
    worker = threading.Thread(target=motion)
    worker.start()
    assert started.wait(1)
    service._worker = worker
    lease = threading.Thread(target=service._on_lease, args=(1,))
    lease.start()
    assert not acknowledged.wait(0.05)
    finish.set()
    lease.join(1)
    worker.join(1)
    assert acknowledged.is_set()
