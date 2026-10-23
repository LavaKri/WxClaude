"""The help page: one HTML file per language in ``wxclaude/help`` (``fr.html``, ``en.html``),
English as fallback. The files are made from the Markdown text of ``MakeHelp/`` by
``MakeHelp/make_help.py``; the application opens them as they are."""

from importlib import resources
from pathlib import Path

from wxclaude.core.errors import HelpError

FALLBACK_LANGUAGE = "en"


def help_page(language: str, folder: Path | None = None) -> Path:
    """The HTML help page of ``language``, else the English one (in ``folder``, by default the
    help folder of the package).

    Raises ``HelpError`` when neither exists.
    """
    where = folder or Path(str(resources.files("wxclaude").joinpath("help")))
    for name in (language, FALLBACK_LANGUAGE):
        path = where / f"{name}.html"
        if path.is_file():
            return path
    raise HelpError("The help page is missing.")
