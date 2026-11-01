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
ACK_SEQ = "NAOFair/Autostart/AckSeq"
LEASE_COMMAND = "NAOFair/Autostart/LeaseCommand"
LEASE_SEQ = "NAOFair/Autostart/LeaseSeq"
LEASE_ACK_SEQ = "NAOFair/Autostart/LeaseAckSeq"

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


def action_for(binding):
    """Return the autostart action for one trigger, or None when it is inert."""
    if not isinstance(binding, dict) or not binding.get("enabled", True):
        return None
    action = binding.get("action")
    if action == "speak":
        phrase = text_of(binding.get("phrase") or u"")
        if not phrase.strip():
            return None
        return ("speak", phrase)
    if action in ("stop_speech", "stop_conversation"):
        return ("stop_speech",)
    if action == "motion" and binding.get("motion") in MOTIONS:
        return ("motion", binding.get("motion"))
    if action == "stop_motion":
        return ("stop_motion",)
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
