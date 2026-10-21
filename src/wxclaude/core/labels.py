"""Labels of the controls: the visible text carries an access key, the accessible name does not."""

import re

_ACCESS_KEY = re.compile(r"&(&?)")


def accessible_name(label: str) -> str:
    """The label without its access key marker: ``&Tools`` gives ``Tools``.

    A doubled ``&&`` is a literal ampersand and stays one (``Q&&A`` gives ``Q&A``); a lone ``&`` at
    the end of the text marks nothing and is dropped.
    """
    return _ACCESS_KEY.sub(r"\1", label)
