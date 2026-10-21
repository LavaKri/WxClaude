"""What a message holds without displaying it: the tools it used, its tables and its links.

The conversation view shows the text of the messages only. These details are found in the message
(tools are kept by the session reader, tables and links are found by the Markdown parser) and
shown in dialogs. Lines are counted from the first line of the text of the message, the title
excluded. See ``docs/conversation-display.md``.
"""

import json
from dataclasses import dataclass, field
from enum import StrEnum

from markdown_it import MarkdownIt
from markdown_it.token import Token

from wxclaude.core.messages import Message, ToolUse
from wxclaude.i18n import _

_PARSER = MarkdownIt("commonmark").enable("table")
_SUMMARY_KEYS = ("command", "file_path", "path", "pattern", "url", "query", "description", "prompt")
_SUMMARY_LENGTH = 80
#: Links that are opened in the browser; any other kind of address is only shown or copied.
OPENABLE_SCHEMES = ("http://", "https://", "mailto:")


class DetailAction(StrEnum):
    """What the context menu of a message can do."""

    TOOLS = "tools"
    TABLE = "table"
    LINKS = "links"
    COPY_MESSAGE = "copy_message"


@dataclass(frozen=True, slots=True)
class Table:
    """A table of a message: header cells, rows, and its lines (``end_line`` excluded)."""

    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    first_line: int
    end_line: int
    source: str

    def row_line(self, row: tuple[str, ...]) -> str:
        """A row on one line for a screen reader: ``Name: x, Size: 3`` (empty cells left out)."""
        parts: list[str] = []
        for index, cell in enumerate(row):
            if not cell:
                continue
            header = self.headers[index] if index < len(self.headers) else ""
            parts.append(_("{header}: {cell}").format(header=header, cell=cell) if header else cell)
        return ", ".join(parts) if parts else _("Empty row")


@dataclass(frozen=True, slots=True)
class Link:
    """A link of a message: its text, its address and the line it is on."""

    text: str
    url: str
    line: int

    @property
    def can_open(self) -> bool:
        """Is it safe to hand the address to the browser?"""
        return self.url.lower().startswith(OPENABLE_SCHEMES)

    def label(self) -> str:
        """The link on one line: its text then its address (just the address without a text)."""
        if not self.text or self.text == self.url:
            return self.url
        return _("{text}, {url}").format(text=self.text, url=self.url)


@dataclass(slots=True)
class MessageDetails:
    """The tools, tables and links of a message."""

    tools: list[ToolUse] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)

    def table_at(self, line: int) -> Table | None:
        """The table that holds ``line`` (a line of the text of the message)."""
        return next((t for t in self.tables if t.first_line <= line < t.end_line), None)

    def link_index_at(self, line: int) -> int:
        """The index of the first link on ``line``, 0 when there is none (the first link)."""
        return next((i for i, link in enumerate(self.links) if link.line == line), 0)

    def actions(self, line: int) -> list[DetailAction]:
        """What the context menu offers at ``line`` (-1 on the title): what the message holds,
        and always to copy it."""
        actions: list[DetailAction] = []
        if self.tools:
            actions.append(DetailAction.TOOLS)
        if self.table_at(line) is not None:
            actions.append(DetailAction.TABLE)
        if self.links:
            actions.append(DetailAction.LINKS)
        actions.append(DetailAction.COPY_MESSAGE)
        return actions


def message_details(message: Message) -> MessageDetails:
    """The details of ``message``."""
    tokens = _PARSER.parse(message.text)
    lines = message.text.split("\n")
    return MessageDetails(list(message.tools), _tables(tokens, lines), _links(tokens))


def _tables(tokens: list[Token], lines: list[str]) -> list[Table]:
    tables: list[Table] = []
    headers: list[str] = []
    rows: list[list[str]] = []
    first, end = 0, 0
    for index, token in enumerate(tokens):
        if token.type == "table_open" and token.map is not None:
            first, end = token.map
            headers, rows = [], []
        elif token.type == "tr_open":
            rows.append([])
        elif token.type in ("th_open", "td_open"):
            content = tokens[index + 1].content.strip()
            (headers if token.type == "th_open" else rows[-1]).append(content)
        elif token.type == "table_close":
            body = tuple(tuple(row) for row in rows if row)
            source = "\n".join(lines[first:end])
            tables.append(Table(tuple(headers), body, first, end, source))
    return tables


def _links(tokens: list[Token]) -> list[Link]:
    links: list[Link] = []
    for token in tokens:
        if token.type != "inline" or not token.children:
            continue
        line = token.map[0] if token.map else 0
        text: list[str] = []
        href = None
        for child in token.children:
            if child.type in ("softbreak", "hardbreak"):
                line += 1
            elif child.type == "link_open":
                href, text = str(child.attrGet("href") or ""), []
            elif child.type == "link_close" and href is not None:
                links.append(Link("".join(text).strip(), href, line))
                href = None
            elif href is not None and child.type in ("text", "code_inline"):
                text.append(child.content)
    return links


def _one_line(text: str) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= _SUMMARY_LENGTH:
        return collapsed
    return collapsed[: _SUMMARY_LENGTH - 1] + "…"


def _value_text(value: object) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def tool_line(tool: ToolUse) -> str:
    """A tool call on one line: its name, what it worked on, and that it failed if it did."""
    parts = [tool.name]
    for key in _SUMMARY_KEYS:
        if key in tool.input:
            parts.append(_one_line(_value_text(tool.input[key])))
            break
    if tool.is_error:
        parts.append(_("failed"))
    return ", ".join(part for part in parts if part)


def tool_detail(tool: ToolUse) -> str:
    """Everything known about a tool call: the name, each argument and the result."""
    lines = [_("Tool: {name}").format(name=tool.name)]
    lines.extend(f"{key}: {_value_text(value)}" for key, value in tool.input.items())
    if tool.is_error:
        lines.append(_("The tool failed."))
    if tool.result:
        lines.extend(["", _("Result:"), tool.result])
    return "\n".join(lines)
