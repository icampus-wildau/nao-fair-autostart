import threading
from types import SimpleNamespace

from nao_fair_autostart.contract import LEASE_ACK_SEQ
from nao_fair_autostart.service import Service


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
