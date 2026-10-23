"""Turn the Markdown help text into the simple HTML page the application shows.

    .venv\\Scripts\\python.exe MakeHelp\\make_help.py [source.md] [language]

The defaults are ``Aide.md`` (next to this script) and ``fr``. The page is written in
``src/wxclaude/help/<language>.html``, which the application opens in the browser (F1): plain
HTML, no style, no script; the title is the first level 1 heading. Run it again after every edit
of the text, once per language.
"""

import html
import sys
from pathlib import Path

from markdown_it import MarkdownIt

HERE = Path(__file__).resolve().parent
HELP_FOLDER = HERE.parent / "src" / "wxclaude" / "help"
DEFAULT_SOURCE = HERE / "Aide.md"
DEFAULT_LANGUAGE = "fr"

_PARSER = MarkdownIt("commonmark")
_PAGE = (
    '<!DOCTYPE html>\n<html lang="{language}">\n<head>\n<meta charset="utf-8">\n'
    "<title>{title}</title>\n</head>\n<body>\n{body}</body>\n</html>\n"
)


def render_page(markdown: str, language: str) -> str:
    """The HTML page for ``markdown``; its title is the first level 1 heading."""
    title = next(
        (line[2:].strip() for line in markdown.splitlines() if line.startswith("# ")), "WxClaude"
    )
    body = _PARSER.render(markdown)
    return _PAGE.format(language=html.escape(language), title=html.escape(title), body=body)


def make_help(source: Path, language: str, folder: Path = HELP_FOLDER) -> Path:
    """Write the page of ``source`` as ``<language>.html`` in ``folder`` and return its path."""
    page = folder / f"{language}.html"
    folder.mkdir(parents=True, exist_ok=True)
    page.write_text(render_page(source.read_text(encoding="utf-8"), language), encoding="utf-8")
    return page


def main(arguments: list[str]) -> int:
    source = Path(arguments[0]) if arguments else DEFAULT_SOURCE
    language = arguments[1] if len(arguments) > 1 else DEFAULT_LANGUAGE
    if not source.is_file():
        print(f"Source not found: {source}", file=sys.stderr)
        return 1
    print(make_help(source, language))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
