"""The one ``--settings`` argument of a launch, merged from the parts that put something in it.

The CLI takes ``--settings`` twice without error but only the last one counts (measured, CLI
2.1.286: the ``env`` and the hooks of the first are lost), so what a launch gives is merged here,
once.
"""

import copy
import json


def _merge_into(target: dict[str, object], source: dict[str, object]) -> None:
    for key, value in source.items():
        current = target.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            _merge_into(current, value)
        elif isinstance(current, list) and isinstance(value, list):
            current.extend(copy.deepcopy(item) for item in value if item not in current)
        else:
            target[key] = copy.deepcopy(value)


def merge_settings(*parts: dict[str, object]) -> dict[str, object]:
    """The parts merged key by key: objects are merged, lists are joined (an entry once), any
    other value of a later part replaces that of an earlier one. The parts are not changed."""
    merged: dict[str, object] = {}
    for part in parts:
        _merge_into(merged, part)
    return merged


def settings_arguments(*parts: dict[str, object]) -> list[str]:
    """``--settings`` and the merged JSON; nothing at all when the parts are empty."""
    merged = merge_settings(*parts)
    return ["--settings", json.dumps(merged)] if merged else []
