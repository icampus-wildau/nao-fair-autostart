"""Keyframe plans for the motions a trigger can run without the NAO Fair app.

The angles match the laptop gestures in naoqi-control. A gesture returns to
the pose captured at the start. A sensor reading outside the joint limit is
pulled in, because ALMotion rejects the whole return otherwise. Sitting
releases body stiffness after the posture move finishes. Stopping leaves the
posture where it is.
"""

from __future__ import print_function

_ARM_JOINTS = (
    "ShoulderPitch",
    "ShoulderRoll",
    "ElbowYaw",
    "ElbowRoll",
    "WristYaw",
    "Hand",
)

# Fallback when ALMotion.getLimits is missing. Head values are the ones the
# gestures already used. Arm values are the H25 ranges; the robot's own
# limits replace these when the service can report them.
_JOINT_LIMITS = {
    "HeadPitch": (-0.67, 0.51),
    "HeadYaw": (-2.08, 2.08),
    "LShoulderPitch": (-2.0857, 2.0857),
    "LShoulderRoll": (-0.3142, 1.3265),
    "LElbowYaw": (-2.0857, 2.0857),
    "LElbowRoll": (-1.5446, -0.0349),
    "LWristYaw": (-1.8238, 1.8238),
    "LHand": (0.0, 1.0),
    "RShoulderPitch": (-2.0857, 2.0857),
    "RShoulderRoll": (-1.3265, 0.3142),
    "RElbowYaw": (-2.0857, 2.0857),
    "RElbowRoll": (0.0349, 1.5446),
    "RWristYaw": (-1.8238, 1.8238),
    "RHand": (0.0, 1.0),
}


def plan(name):
    """Return joints, keyframes, times, relative, chain, return_secs, and kind."""
    if name == "wave_left":
        return _wave("left")
    if name == "wave_right":
        return _wave("right")
    if name == "nod":
        return _head("nod", "HeadPitch", [-0.1, 0.2, 0.0], [0.3, 0.6, 1.0], 0.35)
    if name == "shake":
        return _head("shake", "HeadYaw", [0.28, -0.28, 0.18], [0.5, 0.9, 1.3], 0.3)
    if name in ("sit", "stand"):
        return {"kind": "posture", "name": "Sit" if name == "sit" else "Stand", "release": name == "sit"}
    raise ValueError("unsupported motion")


def play(motion, posture, name, stopped):
    """Block until the gesture finishes or ``stopped`` becomes true."""
    spec = plan(name)
    if spec["kind"] == "posture":
        _posture(motion, posture, spec, stopped)
        return
    names = spec["joints"]
    limits = _limits_for(motion, names)
    rest = [_clamp(joint, angle, limits) for joint, angle in zip(names, motion.getAngles(names, True))]
    if stopped():
        return
    angles = spec["keyframes"]
    if spec["relative"]:
        angles = []
        for index, joint in enumerate(names):
            origin = rest[index]
            series = spec["keyframes"][index]
            angles.append([_clamp(joint, origin + offset, limits) for offset in series])
    else:
        angles = [
            [_clamp(joint, angle, limits) for angle in series]
            for joint, series in zip(names, angles)
        ]
    motion.setStiffnesses(spec["chain"], 0.8)
    try:
        if stopped():
            return
        try:
            motion.angleInterpolation(names, angles, spec["times"], True)
        except Exception:
            if stopped():
                return
        if stopped() or not spec["return_secs"]:
            return
        motion.angleInterpolation(
            names,
            [[angle] for angle in rest],
            [[spec["return_secs"]] for _ in names],
            True,
        )
    finally:
        if not stopped():
            motion.setStiffnesses(spec["chain"], 0.0)


def _posture(motion, posture, spec, stopped):
    if stopped():
        return
    motion.setStiffnesses("Body", 1.0)
    posture.goToPosture(spec["name"], 0.5)
    if stopped() or not spec["release"]:
        return
    motion.setStiffnesses("Body", 0.0)


def _wave(side):
    chain, prefix, outward = ("LArm", "L", 1.0) if side == "left" else ("RArm", "R", -1.0)
    return {
        "kind": "animation",
        "chain": chain,
        "joints": ["%s%s" % (prefix, joint) for joint in _ARM_JOINTS],
        "keyframes": [
            [-0.3],
            [0.35 * outward],
            [-1.2 * outward],
            [-0.9 * outward],
            [-1.0, 1.0, -1.0, 1.0, -1.0, 1.0],
            [1.0],
        ],
        "times": [
            [1.0],
            [1.0],
            [1.0],
            [1.0],
            [1.4, 1.8, 2.2, 2.6, 3.0, 3.4],
            [1.0],
        ],
        "relative": False,
        "return_secs": 1.0,
    }


def _head(name, joint, offsets, times, return_secs):
    del name
    return {
        "kind": "animation",
        "chain": "Head",
        "joints": [joint],
        "keyframes": [offsets],
        "times": [times],
        "relative": True,
        "return_secs": return_secs,
    }


def _limits_for(motion, names):
    """Joint limits from the robot, or the fallback table when it cannot say."""
    getter = getattr(motion, "getLimits", None)
    limits = {}
    for name in names:
        bounds = _JOINT_LIMITS.get(name)
        if callable(getter):
            try:
                raw = getter(name)
                low, high = float(raw[0][0]), float(raw[0][1])
            except Exception:
                low = high = None
            if low is not None and high is not None and low < high:
                bounds = (low, high)
        if bounds is not None:
            limits[name] = bounds
    return limits


def _clamp(joint, angle, limits=None):
    bounds = None if limits is None else limits.get(joint)
    if bounds is None:
        bounds = _JOINT_LIMITS.get(joint)
    if bounds is None:
        return angle
    low, high = bounds
    return max(low, min(high, angle))
