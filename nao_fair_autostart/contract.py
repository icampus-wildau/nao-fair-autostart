"""Assignment document and ALMemory names shared with the NAO Fair app.

The laptop writes these keys through NAOqi. This process stores the
assignment on disk and acknowledges the sequence it persisted.
"""

from __future__ import print_function

import json
import os
import re

ASSIGNMENT = "NAOFair/Autostart/Assignment"
ASSIGNMENT_SEQ = "NAOFair/Autostart/AssignmentSeq"
POSITION = "NAOFair/Dialog/Position"
POSITION_SEQ = "NAOFair/Dialog/PositionSeq"
ACK_SEQ = "NAOFair/Autostart/AckSeq"
LEASE_COMMAND = "NAOFair/Autostart/LeaseCommand"
LEASE_SEQ = "NAOFair/Autostart/LeaseSeq"
LEASE_ACK_SEQ = "NAOFair/Autostart/LeaseAckSeq"
VERSION = "NAOFair/Autostart/Version"
ARMED_STATE = "NAOFair/Autostart/ArmedState"

LEASE_TIMEOUT_SECS = 20.0

MOTIONS = ("wave_left", "wave_right", "nod", "shake", "sit", "stand")

_PUNCTUATION = (
    (u"\u2013", u"-"),
    (u"\u2014", u"-"),
    (u"\u201c", u'"'),
    (u"\u201d", u'"'),
    (u"\u2018", u"'"),
    (u"\u2019", u"'"),
    (u"\u2026", u"..."),
    (u"\u201e", u'"'),
)

_SENSORS = (
    "front_head",
    "middle_head",
    "rear_head",
    "left_hand",
    "right_hand",
    "left_bumper",
    "right_bumper",
)


def memory_event(sensor_id):
    return {
        "front_head": "FrontTactilTouched",
        "middle_head": "MiddleTactilTouched",
        "rear_head": "RearTactilTouched",
        "left_hand": "HandLeftBackTouched",
        "right_hand": "HandRightBackTouched",
        "left_bumper": "LeftBumperPressed",
        "right_bumper": "RightBumperPressed",
    }[sensor_id]


def parse_assignment(raw):
    """Return the assignment dict, or raise ValueError."""
    if raw is None:
        raise ValueError("assignment is empty")
    if not isinstance(raw, basestring_type()):
        raw = json.dumps(raw)
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("assignment must be an object")
    if not isinstance(data.get("armed"), bool):
        raise ValueError("armed must be a boolean")
    triggers = data.get("triggers")
    if not isinstance(triggers, dict):
        raise ValueError("triggers must be an object")
    if set(triggers) != set(_SENSORS):
        raise ValueError("triggers must contain the seven sensors")
    upgraded = {}
    for sensor_id in _SENSORS:
        upgraded[sensor_id] = upgrade_trigger(triggers[sensor_id])
    data["triggers"] = upgraded
    dialogs = data.get("dialogs", [])
    if not isinstance(dialogs, list):
        raise ValueError("dialogs must be a list")
    for dialog in dialogs:
        if not isinstance(dialog, dict) or not isinstance(dialog.get("id"), basestring_type()) or not dialog.get("id"):
            raise ValueError("dialog is invalid")
        lines = dialog.get("lines", [])
        if not isinstance(lines, list):
            raise ValueError("dialog lines must be a list")
        for line in lines:
            if not isinstance(line, dict) or not isinstance(line.get("id"), basestring_type()) or not line.get("id") or not isinstance(line.get("text"), basestring_type()):
                raise ValueError("dialog line is invalid")
        idle = dialog.get("idle_reset_secs")
        if idle is not None and (isinstance(idle, bool) or not isinstance(idle, (int, float)) or not 0 < idle <= 86400):
            raise ValueError("dialog idle timeout is invalid")
    data["dialogs"] = dialogs
    active = data.get("active_dialog_id")
    if active is not None and not isinstance(active, basestring_type()):
        raise ValueError("active dialog is invalid")
    data["active_dialog_id"] = text_of(active) if active else None
    volume = data.get("volume")
    speed = data.get("speech_speed")
    if not isinstance(volume, int) or isinstance(volume, bool) or not 0 <= volume <= 100:
        raise ValueError("volume is outside 0..100")
    if not isinstance(speed, int) or isinstance(speed, bool) or not 50 <= speed <= 400:
        raise ValueError("speech_speed is outside 50..400")
    language = data.get("tts_language")
    if not isinstance(language, basestring_type()) or not text_of(language).strip():
        raise ValueError("tts_language is empty")
    pairs = data.get("replacements")
    if not isinstance(pairs, list):
        raise ValueError("replacements must be a list")
    cleaned = []
    for pair in pairs:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError("replacement must be a pair")
        source, replacement = text_of(pair[0]), text_of(pair[1])
        if not source.strip() or not replacement.strip():
            raise ValueError("replacement is empty")
        cleaned.append([source, replacement])
    data["replacements"] = cleaned
    data["tts_language"] = text_of(language)
    return data


def upgrade_trigger(binding):
    """A flat action becomes the tap. The other gestures copy its switch."""
    if not isinstance(binding, dict):
        raise ValueError("trigger must be an object")
    if "tap" in binding or "double_tap" in binding or "long_press" in binding:
        upgraded = {}
        for name in ("tap", "double_tap", "long_press"):
            gesture = binding.get(name)
            if not isinstance(gesture, dict):
                raise ValueError("gesture must be an object")
            upgraded[name] = _gesture(gesture)
        return upgraded
    return {
        "tap": _gesture(binding),
        "double_tap": _gesture({"enabled": binding.get("enabled", True)}),
        "long_press": _gesture({"enabled": binding.get("enabled", True)}),
    }


def _gesture(binding):
    enabled = binding.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ValueError("enabled must be a boolean")
    yields = binding.get("yield_next", True)
    if not isinstance(yields, bool):
        raise ValueError("yield_next must be a boolean")
    delivery = binding.get("delivery") or "plain"
    if delivery not in ("plain", "motion", "animated"):
        raise ValueError("delivery is invalid")
    return {
        "action": binding.get("action"),
        "phrase": text_of(binding.get("phrase") or u""),
        "motion": binding.get("motion"),
        "enabled": enabled,
        "delivery": delivery,
        "yield_next": yields,
    }


def gesture_action(trigger, gesture):
    if not isinstance(trigger, dict):
        return None
    if "tap" not in trigger and "action" in trigger:
        trigger = upgrade_trigger(trigger)
    return action_for(trigger.get(gesture))


def action_for(binding):
    """Return the autostart action for one gesture, or None when it is inert."""
    if not isinstance(binding, dict) or not binding.get("enabled", True):
        return None
    action = binding.get("action")
    if action == "speak":
        phrase = text_of(binding.get("phrase") or u"")
        if not phrase.strip():
            return None
        delivery = binding.get("delivery") or "plain"
        if delivery not in ("plain", "motion", "animated"):
            delivery = "plain"
        motion = binding.get("motion") if delivery == "motion" else None
        return ("speak", phrase, delivery, motion)
    if action in ("stop_speech", "stop_conversation"):
        return ("stop_speech",)
    if action == "motion" and binding.get("motion") in MOTIONS:
        return ("motion", binding.get("motion"))
    if action == "stop_motion":
        return ("stop_motion",)
    if action == "dialog_next":
        return (action, binding.get("yield_next", True) is not False)
    if action == "dialog_reset":
        return (action, text_of(binding.get("phrase") or u""))
    if action in ("dialog_repeat", "dialog_previous"):
        return (action,)
    return None


def fold_phrase(text, pairs):
    """Punctuation folding, then whole-word replacements, in list order."""
    folded = text_of(text)
    for old, new in _PUNCTUATION:
        folded = folded.replace(old, new)
    for source, replacement in pairs or ():
        folded = _replace_word(folded, text_of(source), text_of(replacement))
    return folded


def read_assignment(path):
    if not path or not os.path.isfile(path):
        return None
    with open(path, "rb") as handle:
        raw = handle.read().decode("utf-8")
    return parse_assignment(raw)


def write_assignment(path, document):
    directory = os.path.dirname(path)
    if directory and not os.path.isdir(directory):
        os.makedirs(directory)
    payload = json.dumps(document, ensure_ascii=False, sort_keys=True)
    if not isinstance(payload, bytes):
        payload = payload.encode("utf-8")
    temporary = path + ".tmp"
    with open(temporary, "wb") as handle:
        handle.write(payload)
    os.rename(temporary, path)


def text_of(value):
    if value is None:
        return u""
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if isinstance(value, basestring_type()) and not isinstance(value, bytes):
        return value
    return u"%s" % value


def basestring_type():
    try:
        return basestring
    except NameError:
        return str


def _replace_word(text, source, replacement):
    if not source:
        return text
    pattern = u"(?<![\\w])" + re.escape(source) + u"(?![\\w])"
    return re.sub(pattern, lambda _match: replacement, text, flags=re.UNICODE)
