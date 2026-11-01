"""NAOqi process that runs a stored trigger assignment from robot boot.

The NAO Fair app suppresses it by renewing a lease. This module does not
import qi, so the decision logic can be tested on a laptop.
"""

from __future__ import print_function

import logging
import threading
import time

from nao_fair_autostart.contract import (
    ACK_SEQ,
    ASSIGNMENT,
    ASSIGNMENT_SEQ,
    LEASE_ACK_SEQ,
    LEASE_COMMAND,
    LEASE_SEQ,
    fold_phrase,
    memory_event,
    parse_assignment,
    read_assignment,
    write_assignment,
)
from nao_fair_autostart.engine import AutostartEngine
from nao_fair_autostart.gestures import play

logger = logging.getLogger("nao_fair_autostart")

_SENSOR_IDS = (
    "front_head",
    "middle_head",
    "rear_head",
    "left_hand",
    "right_hand",
    "left_bumper",
    "right_bumper",
)


class Service(object):
    def __init__(self, session, store_path, engine=None, now=None):
        self.session = session
        self.store_path = store_path
        self.engine = engine or AutostartEngine()
        self.now = now or time.time
        self.memory = session.service("ALMemory")
        self.tts = session.service("ALTextToSpeech")
        self.motion = session.service("ALMotion")
        self.posture = session.service("ALRobotPosture")
        self.audio = session.service("ALAudioDevice")
        self.life = session.service("ALAutonomousLife")
        self._subscribers = []
        self._stop = threading.Event()
        self._motion_stop = threading.Event()
        self._worker = None
        self._lock = threading.Lock()
    def start(self):
        stored = _read_quietly(self.store_path)
        if stored is not None:
            self._apply(self.engine.load(stored))
        for sensor_id in _SENSOR_IDS:
            self._subscribe(memory_event(sensor_id), self._pressed(sensor_id))
        self._subscribe(ASSIGNMENT_SEQ, self._on_assignment)
        self._subscribe(LEASE_SEQ, self._on_lease)
        ticker = threading.Thread(target=self._tick)
        ticker.daemon = True
        ticker.start()

    def _subscribe(self, name, callback):
        subscriber = self.memory.subscriber(name)
        subscriber.signal.connect(callback)
        self._subscribers.append(subscriber)

    def _pressed(self, sensor_id):
        def callback(value):
            if not value:
                return
            action = self.engine.press(sensor_id)
            if action is not None:
                self._start_action(action)

        return callback

    def _on_assignment(self, seq):
        try:
            document = parse_assignment(self.memory.getData(ASSIGNMENT))
            write_assignment(self.store_path, document)
        except Exception:
            logger.exception("Could not store the autostart assignment")
            return
        self._raise(ACK_SEQ, int(seq))
        self._apply(self.engine.load(document))

    def _on_lease(self, seq):
        try:
            command = self.memory.getData(LEASE_COMMAND)
        except Exception:
            logger.exception("Could not read the autostart lease")
            return
        now = self.now()
        if command == "release":
            effects = self.engine.release(now)
        else:
            effects = self.engine.hold(int(seq), now)
        self._apply(effects)
        if command != "release":
            self._raise(LEASE_ACK_SEQ, int(seq))

    def _tick(self):
        while not self._stop.is_set():
            self._stop.wait(1.0)
            if self._stop.is_set():
                return
            self._apply(self.engine.tick(self.now()))

    def _apply(self, effects):
        for effect in effects:
            if effect == "stop_all":
                self._halt()
            elif effect == "apply_audio":
                self._apply_audio()
            elif effect == "disable_life":
                self._disable_life()

    def _apply_audio(self):
        document = self.engine.assignment
        if not document:
            return
        try:
            self.audio.setOutputVolume(int(document["volume"]))
            self.tts.setParameter("speed", int(document["speech_speed"]))
            self.tts.setLanguage(document["tts_language"])
        except Exception:
            logger.exception("Could not apply autostart voice settings")

    def _disable_life(self):
        try:
            self.life.setState("disabled")
        except Exception:
            logger.exception("Could not disable autonomous life")

    def _start_action(self, action):
        kind = action[0]
        if kind == "stop_speech":
            self._stop_speech()
            return
        if kind == "stop_motion":
            self._stop_motion()
            return
        if kind == "speak":
            self._speak(action[1])
            return
        if kind == "motion":
            self._move(action[1])

    def _speak(self, phrase):
        pairs = (self.engine.assignment or {}).get("replacements") or []
        text = fold_phrase(phrase, pairs)
        try:
            self.tts.stopAll()
            self.tts.post.say(text)
        except Exception:
            logger.exception("Could not speak")

    def _stop_speech(self):
        try:
            self.tts.stopAll()
        except Exception:
            logger.exception("Could not stop speech")

    def _stop_motion(self):
        self._motion_stop.set()
        try:
            self.motion.stopMove()
        except Exception:
            logger.exception("Could not stop motion")

    def _halt(self):
        self._stop_speech()
        self._stop_motion()

    def _move(self, name):
        self._motion_stop.set()
        worker = self._worker
        if worker is not None and worker.is_alive():
            worker.join(1.0)
        self._motion_stop = threading.Event()
        stop = self._motion_stop

        def run():
            try:
                play(self.motion, self.posture, name, stop.is_set)
            except Exception:
                logger.exception("Could not play %s", name)

        self._worker = threading.Thread(target=run)
        self._worker.daemon = True
        self._worker.start()

    def _raise(self, key, value):
        try:
            self.memory.raiseEvent(key, value)
        except Exception:
            logger.exception("Could not acknowledge %s", key)


def _read_quietly(path):
    try:
        return read_assignment(path)
    except Exception:
        logger.exception("Could not read %s", path)
        return None
