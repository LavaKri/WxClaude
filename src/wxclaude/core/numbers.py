"""How a number of tokens is written, so that it reads and is heard easily.

Up to 999999 the number is written as it is. Above, it is rounded (half up): ``1,5 million`` (1.0 to
9.9 million), ``721 millions`` (10 to 999 millions), ``1,2 milliard`` (1.0 to 9.9 billions) and
``12 milliards``. The decimal mark and the plural belong to the language (the catalog). Only whole
numbers are used, so that the rounding is exact.
"""

from wxclaude.i18n import _, ngettext

_MILLION = 1_000_000
_BILLION = 1_000_000_000


def _tenths(count: int, unit: int) -> int:
    """``count`` in tenths of ``unit``, rounded half up (15 is 1.5)."""
    return (count + unit // 20) // (unit // 10)


def _whole(count: int, unit: int) -> int:
    """``count`` in whole ``unit``, rounded half up."""
    return (count + unit // 2) // unit


def _decimal(tenths: int) -> str:
    """15 as ``1.5``, with the decimal mark of the language (``1,5`` in French)."""
    return f"{tenths // 10}{_('.')}{tenths % 10}"


def _million(value: str, number: int) -> str:
    # In English the word does not change; in French it is plural from 2 (``1,5 million``).
    return ngettext("{value} million", "{value} million", number).format(value=value)


def _billion(value: str, number: int) -> str:
    return ngettext("{value} billion", "{value} billion", number).format(value=value)


def format_tokens(count: int) -> str:
    """``count`` tokens written short: exact below a million, rounded above."""
    if count < _MILLION:
        return str(count)
    tenths = _tenths(count, _MILLION)
    if tenths < 100:  # 1.0 to 9.9 millions
        return _million(_decimal(tenths), tenths // 10)
    millions = _whole(count, _MILLION)
    if millions < 1000:  # 10 to 999 millions (9.96 millions is 10 millions)
        return _million(str(millions), millions)
    tenths = _tenths(count, _BILLION)  # 999.6 millions is 1.0 billion
    if tenths < 100:
        return _billion(_decimal(tenths), tenths // 10)
    billions = _whole(count, _BILLION)
    return _billion(str(billions), billions)
