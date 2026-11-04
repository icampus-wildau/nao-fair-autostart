"""NAOqi process that runs a stored trigger assignment from robot boot.

The NAO Fair app suppresses it by renewing a lease. This module does not
import qi, so the decision logic can be tested on a laptop.
"""

from __future__ import print_function

import json
import logging
import os
import threading
import time

from nao_fair_autostart.contract import basestring_type
from nao_fair_autostart.contract import (
    ACK_SEQ,
    ASSIGNMENT,
    ASSIGNMENT_SEQ,
    LEASE_ACK_SEQ,
    LEASE_COMMAND,
    LEASE_SEQ,
    POSITION,
    POSITION_SEQ,
    VERSION,
    fold_phrase,
    memory_event,
    parse_assignment,
    read_assignment,
    write_assignment,
)
from nao_fair_autostart.dialog import active_dialog, position_for, step
from nao_fair_autostart.engine import AutostartEngine
from nao_fair_autostart.gestures import play
from nao_fair_autostart.touch import TouchClassifier

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
        self._speech_call = None
        self._speech_queue = []
        self._speech_key = None
        self._speech_gen = 0
        self._speech_running = False
        self._voice = None
        self._accompanying = False
        self._lock = threading.Lock()
        self._touch = TouchClassifier()
        self._position = None
        self._idle_deadline = None
        self._writing_position = False
    def start(self):
        self._publish_version()
        self._clear_position()
        stored = _read_quietly(self.store_path)
        if stored is not None:
            self._apply(self.engine.load(stored))
        for sensor_id in _SENSOR_IDS:
            self._subscribe(memory_event(sensor_id), self._pressed(sensor_id))
        self._subscribe(ASSIGNMENT_SEQ, self._on_assignment)
        self._subscribe(LEASE_SEQ, self._on_lease)
        self._subscribe(POSITION_SEQ, self._on_position)
        ticker = threading.Thread(target=self._tick)
        ticker.daemon = True
        ticker.start()

    def _publish_version(self):
        home = os.path.dirname(self.store_path)
        path = os.path.join(home, "VERSION")
        try:
            handle = open(path)
        except IOError:
            return
        try:
            text = handle.read().strip()
        finally:
            handle.close()
        if not text:
            return
        try:
            self.memory.insertData(VERSION, text)
        except Exception:
            logger.exception("Could not publish the autostart version")

    def _subscribe(self, name, callback):
        subscriber = self.memory.subscriber(name)
        subscriber.signal.connect(callback)
        self._subscribers.append(subscriber)

    def _pressed(self, sensor_id):
        def callback(value):
            now = self.now()
            with self._lock:
                if value:
                    gesture = self._touch.down(sensor_id, now)
                else:
                    gesture = self._touch.up(sensor_id, now, self._double_tap_armed(sensor_id))
                if gesture:
                    self._run_gesture(sensor_id, gesture)

        return callback

    def _double_tap_armed(self, sensor_id):
        assignment = self.engine.assignment or {}
        triggers = assignment.get("triggers") or {}
        trigger = triggers.get(sensor_id)
        if not isinstance(trigger, dict):
            return False
        gesture = trigger.get("double_tap")
        if not isinstance(gesture, dict) or not gesture.get("enabled", True):
            return False
        return gesture.get("action") is not None

    def _run_gesture(self, sensor_id, gesture):
        action = self.engine.press(sensor_id, gesture)
        if action is None:
            return
        if action[0] == "dialog_reset":
            phrase = action[1] if len(action) > 1 else u""
            self._reset_dialog(phrase)
            return
        if action[0] in ("dialog_next", "dialog_repeat", "dialog_previous"):
            yields = action[1] if len(action) > 1 else True
            self._play_dialog(action[0], yields)
            return
        self._start_action(action, (sensor_id, gesture))

    def _play_dialog(self, action, yields=True):
        if action == "dialog_next" and yields and self._line_speaking():
            return
        assignment = self.engine.assignment or {}
        dialog = active_dialog(assignment.get("dialogs"), assignment.get("active_dialog_id"))
        line = step(dialog, self._position, action)
        if line is None or dialog is None:
            return
        text = fold_phrase(line.get("text") or u"", assignment.get("replacements"))
        if not self._speak_line(text, line.get("delivery") or "plain", line.get("motion")):
            return
        self._position = position_for(dialog.get("id"), line.get("id"), self._position)
        self._store_position()
        self._arm_idle()

    def _reset_dialog(self, phrase):
        assignment = self.engine.assignment or {}
        dialog = active_dialog(assignment.get("dialogs"), assignment.get("active_dialog_id"))
        if dialog is None:
            return
        if self._accompanying and self._line_or_phrase_speaking():
            self._release_accompanying_motion()
        self._accompanying = False
        self._stop_speech()
        self._position = None
        self._store_position()
        self._idle_deadline = None
        text = fold_phrase(phrase, assignment.get("replacements")).strip()
        if not text:
            return
        self._enqueue_speech(("announcement", time.time()), text, "plain", None, "announcement")

    def _line_speaking(self):
        return self._voice == "line" and self._call_running()

    def _line_or_phrase_speaking(self):
        return self._voice in ("line", "phrase", "announcement") and self._call_running()

    def _call_running(self):
        call = self._speech_call
        if call is None:
            return False
        for name in ("isRunning", "is_running"):
            fn = getattr(call, name, None)
            if callable(fn):
                try:
                    return bool(fn())
                except Exception:
                    return False
        finished = getattr(call, "isFinished", None)
        if callable(finished):
            try:
                return not bool(finished())
            except Exception:
                return False
        return self._voice is not None

    def _on_assignment(self, seq):
        try:
            document = parse_assignment(self.memory.getData(ASSIGNMENT))
            write_assignment(self.store_path, document)
        except Exception:
            logger.exception("Could not store the autostart assignment")
            return
        with self._lock:
            self._apply(self.engine.load(document))
            for sensor_id, gesture in self._touch.flush(self.now(), self._double_tap_armed):
                self._run_gesture(sensor_id, gesture)
        self._raise(ACK_SEQ, int(seq))

    def _on_lease(self, seq):
        try:
            command = self.memory.getData(LEASE_COMMAND)
        except Exception:
            logger.exception("Could not read the autostart lease")
            return
        with self._lock:
            now = self.now()
            if command == "release":
                effects = self.engine.release(now)
            else:
                effects = self.engine.hold(int(seq), now)
            self._apply(effects)
            if command != "release":
                worker = self._worker
                if worker is not None and worker.is_alive():
                    worker.join()
                self._raise(LEASE_ACK_SEQ, int(seq))

    def _tick(self):
        lease_at = 0
        while not self._stop.is_set():
            self._stop.wait(0.05)
            if self._stop.is_set():
                return
            now = self.now()
            with self._lock:
                for sensor_id, gesture in self._touch.tick(now):
                    self._run_gesture(sensor_id, gesture)
                self._idle_due(now)
                if now - lease_at >= 1:
                    lease_at = now
                    self._apply(self.engine.tick(now))

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

    def _start_action(self, action, key=None):
        kind = action[0]
        if kind == "stop_speech":
            self._stop_speech()
            return
        if kind == "stop_motion":
            self._stop_motion()
            return
        if kind == "speak":
            delivery = action[2] if len(action) > 2 else "plain"
            motion = action[3] if len(action) > 3 else None
            self._enqueue_speech(key or ("phrase", action[1]), action[1], delivery, motion, "phrase")
            return
        if kind == "motion":
            self._move(action[1])

    def _speak(self, phrase):
        with self._lock:
            self._enqueue_speech(("phrase", phrase), phrase)

    def _enqueue_speech(self, key, phrase, delivery="plain", motion=None, kind="phrase"):
        # The caller holds ``_lock``. The same trigger waits at most once.
        # A different trigger is spoken after the one already playing.
        # An announcement uses a fresh key, so a second reset speaks again.
        if kind != "announcement" and (key == self._speech_key or any(item[0] == key for item in self._speech_queue)):
            return
        self._speech_queue.append((key, phrase, delivery, motion, kind))
        if self._speech_running:
            return
        self._speech_running = True
        worker = threading.Thread(target=self._drain_speech)
        worker.daemon = True
        self._speech_worker = worker
        worker.start()

    def _drain_speech(self):
        while True:
            with self._lock:
                if not self._speech_queue:
                    self._speech_key = None
                    self._speech_running = False
                    if self._voice in ("phrase", "announcement"):
                        self._voice = None
                    return
                key, phrase, delivery, motion, kind = self._speech_queue.pop(0)
                self._speech_key = key
                self._voice = kind
                gen = self._speech_gen
            if delivery == "motion" and motion:
                self._accompanying = True
                self._move(motion)
            future = self._post_phrase(phrase, delivery)
            self._wait_speech(future)
            with self._lock:
                if gen != self._speech_gen:
                    continue
                if self._voice == kind:
                    self._accompanying = False

    def _post_plain(self, phrase):
        return self._post_phrase(phrase, "plain")

    def _post_phrase(self, phrase, delivery):
        pairs = (self.engine.assignment or {}).get("replacements") or []
        text = fold_phrase(phrase, pairs)
        try:
            if delivery == "animated":
                animated = self.session.service("ALAnimatedSpeech")
                self._speech_call = animated.say(text, _async=True)
            else:
                self._speech_call = self.tts.say(text, _async=True)
            return self._speech_call
        except Exception:
            logger.exception("Could not speak")
            return None

    def _wait_speech(self, future):
        if future is None:
            return
        wait = getattr(future, "wait", None)
        if not callable(wait):
            return
        try:
            wait()
        except Exception:
            logger.exception("Could not wait for speech")

    def _speak_line(self, text, delivery, motion):
        self._stop_speech()
        self._voice = "line"
        if delivery == "motion" and motion:
            self._accompanying = True
            self._stop_motion()
            worker = self._worker
            if worker is not None and worker.is_alive():
                worker.join(0.2)
            self._move(motion)
        else:
            self._accompanying = False
        try:
            if delivery == "animated":
                animated = self.session.service("ALAnimatedSpeech")
                self._speech_call = animated.say(text, _async=True)
            else:
                # session.service() returns a qi object. It has no ALProxy .post.
                # The future cancels the utterance if nothing keeps it alive.
                self._speech_call = self.tts.say(text, _async=True)
            return True
        except Exception:
            logger.exception("Could not speak")
            self._voice = None
            return False

    def _stop_speech(self):
        self._speech_gen += 1
        self._speech_queue = []
        self._speech_key = None
        self._voice = None
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

    def _release_accompanying_motion(self):
        """Cut the keyframes so the gesture can return and go limp.

        The stop flag would skip that return and leave the chain stiff.
        A Bewegung gesture does not use this; it keeps the stop flag.
        """
        try:
            self.motion.stopMove()
        except Exception:
            logger.exception("Could not stop motion")

    def _halt(self):
        self._stop_speech()
        self._stop_motion()

    def _move(self, name):
        # A second press must not cancel the gesture. Cancelling skips the
        # return, and the next one then treats the end pose as home.
        worker = self._worker
        if worker is not None and worker.is_alive():
            return
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

    def _position_path(self):
        home = os.path.dirname(self.store_path) or "."
        return os.path.join(home, "dialog-position.json")

    def _clear_position(self):
        self._position = None
        self._idle_deadline = None
        path = self._position_path()
        try:
            if os.path.isfile(path):
                os.remove(path)
        except Exception:
            logger.exception("Could not clear the dialog position")
        self._writing_position = True
        try:
            self.memory.insertData(POSITION, "")
            self.memory.raiseEvent(POSITION_SEQ, 0)
        except Exception:
            logger.exception("Could not clear the dialog position")
        finally:
            self._writing_position = False

    def _store_position(self):
        payload = "" if not self._position else json.dumps(self._position)
        seq = 0 if not self._position else int(self._position.get("seq") or 0)
        self._write_position_file(payload)
        self._writing_position = True
        try:
            self.memory.insertData(POSITION, payload)
            self.memory.raiseEvent(POSITION_SEQ, seq)
        except Exception:
            logger.exception("Could not store the dialog position")
        finally:
            self._writing_position = False

    def _write_position_file(self, payload):
        path = self._position_path()
        directory = os.path.dirname(path)
        if directory and not os.path.isdir(directory):
            os.makedirs(directory)
        temporary = path + ".tmp"
        handle = open(temporary, "wb")
        try:
            text = payload
            if not isinstance(text, bytes):
                text = text.encode("utf-8")
            handle.write(text)
        finally:
            handle.close()
        os.rename(temporary, path)

    def _on_position(self, seq):
        del seq
        if self._writing_position:
            return
        try:
            raw = self.memory.getData(POSITION)
        except Exception:
            logger.exception("Could not read the dialog position")
            return
        position = _parse_position(raw)
        with self._lock:
            current = None if not self._position else self._position.get("seq")
            incoming = None if not position else position.get("seq")
            if incoming == current:
                return
            self._position = position
            self._write_position_file("" if not position else json.dumps(position))
            if position:
                self._arm_idle()
            else:
                self._idle_deadline = None

    def _arm_idle(self):
        assignment = self.engine.assignment or {}
        dialog = active_dialog(assignment.get("dialogs"), assignment.get("active_dialog_id"))
        secs = None if not dialog else dialog.get("idle_reset_secs")
        if not secs or not self._position:
            self._idle_deadline = None
            return
        self._idle_deadline = self.now() + float(secs)

    def _idle_due(self, now):
        if self._idle_deadline is None or now < self._idle_deadline:
            return
        self._idle_deadline = None
        self._position = None
        self._store_position()

    def _raise(self, key, value):
        try:
            self.memory.raiseEvent(key, value)
        except Exception:
            logger.exception("Could not acknowledge %s", key)


def _parse_position(raw):
    if not raw:
        return None
    if not isinstance(raw, basestring_type()) and not isinstance(raw, bytes):
        return None
    try:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        data = json.loads(raw)
    except Exception:
        return None
    if not isinstance(data, dict) or not data.get("line_id"):
        return None
    return data


def _read_quietly(path):
    try:
        return read_assignment(path)
    except Exception:
        logger.exception("Could not read %s", path)
        return None
