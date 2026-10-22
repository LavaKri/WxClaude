"""The help page: one Markdown file per language in ``wxclaude/help`` (English as fallback),
turned into an HTML file in the temporary folder for the browser."""

import html
import tempfile
from importlib import resources
from pathlib import Path

from markdown_it import MarkdownIt

from wxclaude.core.errors import HelpError

FALLBACK_LANGUAGE = "en"

_PARSER = MarkdownIt("commonmark")
_PAGE = (
    '<!DOCTYPE html>\n<html lang="{language}">\n<head>\n<meta charset="utf-8">\n'
    "<title>{title}</title>\n</head>\n<body>\n{body}</body>\n</html>\n"
)


def help_source(language: str) -> Path | None:
    """The Markdown help of ``language``, else the English one; None if neither exists."""
    folder = resources.files("wxclaude").joinpath("help")
    for name in (language, FALLBACK_LANGUAGE):
        path = Path(str(folder.joinpath(f"{name}.md")))
        if path.is_file():
            return path
    return None


def render_help(markdown: str, language: str) -> str:
    """The HTML page for ``markdown``; its title is the first level 1 heading."""
    title = next(
        (line[2:].strip() for line in markdown.splitlines() if line.startswith("# ")), "WxClaude"
    )
    body = _PARSER.render(markdown)
    return _PAGE.format(language=html.escape(language), title=html.escape(title), body=body)


def write_help_page(language: str) -> Path:
    """Write the help page of ``language`` in the temporary folder and return its path.

    Raises ``HelpError`` when there is no help text or the page cannot be written.
    """
    source = help_source(language)
    if source is None:
        raise HelpError("The help page is missing.")
    page_language = source.stem
    try:
        text = source.read_text(encoding="utf-8")
        folder = Path(tempfile.gettempdir()) / "wxclaude-help"
        folder.mkdir(exist_ok=True)
        page = folder / f"{page_language}.html"
        page.write_text(render_help(text, page_language), encoding="utf-8")
    except OSError as error:
        raise HelpError(str(error)) from error
    return page
