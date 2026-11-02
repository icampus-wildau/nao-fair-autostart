"""How the active dialog moves. No robot and no clock.

The same rules live in nao_fair.dialog. This copy stays on Python 2.7.
"""

from __future__ import print_function


def step(dialog, position, action):
    """Return the line to start, or None when the press says nothing."""
    if not dialog or action not in ("dialog_next", "dialog_repeat", "dialog_previous"):
        return None
    lines = [line for line in dialog.get("lines") or [] if line.get("speaker", "nao") == "nao"]
    if not lines:
        return None
    index = _index(dialog, position)
    wrap = bool(dialog.get("wrap"))
    if action == "dialog_repeat":
        if index is None:
            return None
        return lines[index]
    if action == "dialog_next":
        if index is None:
            return lines[0]
        if index + 1 < len(lines):
            return lines[index + 1]
        if wrap:
            return lines[0]
        return None
    if index is None or (index == 0 and not wrap):
        return None
    if index == 0:
        return lines[-1]
    return lines[index - 1]


def position_for(dialog_id, line_id, previous):
    seq = 1
    if previous and previous.get("seq"):
        seq = int(previous["seq"]) + 1
    return {"dialog_id": dialog_id, "line_id": line_id, "seq": seq}


def reconcile(old_line_ids, new_line_ids, position, active_id):
    if not position or not active_id or position.get("dialog_id") != active_id:
        return None
    line_id = position.get("line_id")
    if line_id in new_line_ids:
        return position
    if not old_line_ids or line_id not in old_line_ids:
        return None
    index = old_line_ids.index(line_id)
    earlier = list(old_line_ids[:index])
    earlier.reverse()
    for line in earlier:
        if line in new_line_ids:
            return {"dialog_id": active_id, "line_id": line, "seq": position.get("seq") or 1}
    return None


def active_dialog(dialogs, active_id):
    if not active_id:
        return None
    for dialog in dialogs or []:
        if dialog.get("id") == active_id:
            return dialog
    return None


def _index(dialog, position):
    if not position or position.get("dialog_id") != dialog.get("id"):
        return None
    line_id = position.get("line_id")
    for index, line in enumerate(line for line in dialog.get("lines") or [] if line.get("speaker", "nao") == "nao"):
        if line.get("id") == line_id:
            return index
    return None
