"""Translation support (gettext). Message ids are English; French is the default language."""

import gettext
from pathlib import Path

DEFAULT_LANGUAGE = "fr"
DOMAIN = "wxclaude"
LOCALE_DIR = Path(__file__).resolve().parent.parent / "locale"


class _Catalog:
    """Holds the active translation so that ``_`` always uses the current language."""

    translation: gettext.NullTranslations = gettext.NullTranslations()


def install(language: str = DEFAULT_LANGUAGE) -> None:
    """Activate the catalog of ``language``; fall back to English message ids if missing."""
    _Catalog.translation = gettext.translation(
        DOMAIN, localedir=LOCALE_DIR, languages=[language], fallback=True
    )


def _(message: str) -> str:
    """Translate ``message`` with the active catalog."""
    return _Catalog.translation.gettext(message)


def ngettext(singular: str, plural: str, count: int) -> str:
    """Translate ``singular`` or ``plural`` with the active catalog, as ``count`` says."""
    return _Catalog.translation.ngettext(singular, plural, count)


def N_(message: str) -> str:  # noqa: N802 - conventional gettext marker name
    """Mark ``message`` for extraction without translating it now; translate later with ``_``."""
    return message
