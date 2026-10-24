"""Labels of the controls: the visible text carries an access key, the accessible name does not."""

import re

_ACCESS_KEY = re.compile(r"&(&?)")


def accessible_name(label: str) -> str:
    """The label without its access key marker: ``&Tools`` gives ``Tools``.

    A doubled ``&&`` is a literal ampersand and stays one (``Q&&A`` gives ``Q&A``); a lone ``&`` at
    the end of the text marks nothing and is dropped.
    """
    return _ACCESS_KEY.sub(r"\1", label)


def shorten(text: str, limit: int) -> str:
    """``text`` cut to ``limit`` characters at most, with ``…`` as the last one when it was cut."""
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
