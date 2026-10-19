"""Reader of the session files written by the Claude Code CLI.

``<config>/projects/<folder>/<session-id>.jsonl`` holds one JSON object per line. Only the prompts
and the answers are turned into messages; tools, tool results, thinking and usage are kept as
details of the answer they belong to. See ``docs/claude-cli.md``.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from wxclaude.core.agents import Agent
from wxclaude.core.errors import SessionReadError
from wxclaude.core.messages import Message, Role, ToolUse, Usage

_NOISE_ANSWER = "No response requested."
_NOISE_PROMPT = "continue"


@dataclass(slots=True)
class Session:
    """What a session file holds."""

    messages: list[Message] = field(default_factory=list)
    title: str = ""
    last_model: str | None = None
    last_effort: str | None = None
    last_permission_mode: str | None = None
    usage: Usage = field(default_factory=Usage)

    @property
    def last_agent(self) -> Agent:
        """The model, effort and permission mode of the last answer; what is unknown is unset.

        It may be the alternative agent: it is only used for a conversation WxClaude knows
        nothing about.
        """
        return Agent.from_dict(
            {
                "model": self.last_model,
                "effort": self.last_effort,
                "permission_mode": self.last_permission_mode,
            }
        )


def _blocks(content: object) -> list[dict[str, object]]:
    """The content of a message as a list of blocks (a plain string is one text block)."""
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if isinstance(content, list):
        return [block for block in content if isinstance(block, dict)]
    return []


def _result_text(content: object) -> str:
    """The text of a ``tool_result`` content (a string or a list of text blocks)."""
    return "\n".join(str(block.get("text", "")) for block in _blocks(content))


def _usage(raw: object) -> Usage | None:
    if not isinstance(raw, dict):
        return None

    def count(key: str) -> int:
        value = raw.get(key)
        return value if isinstance(value, int) else 0

    return Usage(
        count("input_tokens"),
        count("output_tokens"),
        count("cache_creation_input_tokens"),
        count("cache_read_input_tokens"),
    )


class _Builder:
    """Turns the entries one after the other into a ``Session``."""

    def __init__(self) -> None:
        self.session = Session()
        self._ai_title = ""
        self._custom_title = ""
        self._tools: dict[str, ToolUse] = {}
        self._pending_tools: list[ToolUse] = []
        self._pending_thinking: list[str] = []

    def add(self, entry: dict[str, object]) -> None:
        kind = entry.get("type")
        if kind == "custom-title" and isinstance(entry.get("customTitle"), str):
            self._custom_title = str(entry["customTitle"])
        elif kind == "ai-title" and isinstance(entry.get("aiTitle"), str):
            self._ai_title = str(entry["aiTitle"])
        elif kind in ("user", "assistant") and not entry.get("isSidechain"):
            message = entry.get("message")
            if isinstance(message, dict):
                if kind == "user":
                    self._add_user(entry, message)
                else:
                    self._add_assistant(entry, message)
        mode = entry.get("permissionMode")
        if isinstance(mode, str):
            self.session.last_permission_mode = mode

    def finish(self) -> Session:
        self._attach_pending_to_last_answer()
        self.session.title = self._custom_title or self._ai_title
        return self.session

    def _add_user(self, entry: dict[str, object], message: dict[str, object]) -> None:
        texts: list[str] = []
        for block in _blocks(message.get("content")):
            if block.get("type") == "tool_result":
                tool = self._tools.get(str(block.get("tool_use_id")))
                if tool is not None:
                    tool.result = _result_text(block.get("content"))
                    tool.is_error = bool(block.get("is_error"))
            elif block.get("type") == "text":
                texts.append(str(block.get("text", "")))
        text = "\n".join(texts).strip()
        if entry.get("isMeta") or not text:
            return
        self._attach_pending_to_last_answer()
        self.session.messages.append(
            Message(
                id=str(entry.get("uuid") or len(self.session.messages)),
                role=Role.USER,
                text=text,
                hidden=text.lower() == _NOISE_PROMPT,
            )
        )

    def _add_assistant(self, entry: dict[str, object], message: dict[str, object]) -> None:
        model = message.get("model")
        model = model if isinstance(model, str) and model != "<synthetic>" else None
        effort = entry.get("effort")
        usage = _usage(message.get("usage"))
        texts: list[str] = []
        for block in _blocks(message.get("content")):
            kind = block.get("type")
            if kind == "text":
                texts.append(str(block.get("text", "")))
            elif kind == "thinking":
                self._pending_thinking.append(str(block.get("thinking", "")))
            elif kind == "tool_use":
                raw_input = block.get("input")
                tool = ToolUse(
                    str(block.get("id", "")),
                    str(block.get("name", "")),
                    raw_input if isinstance(raw_input, dict) else {},
                )
                self._tools[tool.id] = tool
                self._pending_tools.append(tool)
        if model is not None:
            self.session.last_model = model
            if isinstance(effort, str):
                self.session.last_effort = effort
        text = "\n".join(texts).strip()
        if not text:
            return
        previous = self.session.messages[-1] if self.session.messages else None
        if (
            previous is not None
            and previous.role is Role.ASSISTANT
            and previous.text == text
            and previous.model == model
        ):
            return  # the CLI sometimes writes the same entry twice
        answer = Message(
            id=str(entry.get("uuid") or len(self.session.messages)),
            role=Role.ASSISTANT,
            text=text,
            model=model,
            effort=effort if isinstance(effort, str) and model is not None else None,
            hidden=text == _NOISE_ANSWER,
            tools=self._pending_tools,
            thinking=self._pending_thinking,
            usage=usage,
        )
        self._pending_tools = []
        self._pending_thinking = []
        if usage is not None:
            self._count(usage)
        self.session.messages.append(answer)

    def _count(self, usage: Usage) -> None:
        total = self.session.usage
        total.input_tokens += usage.input_tokens
        total.output_tokens += usage.output_tokens
        total.cache_creation_input_tokens += usage.cache_creation_input_tokens
        total.cache_read_input_tokens += usage.cache_read_input_tokens

    def _attach_pending_to_last_answer(self) -> None:
        """Tools and thinking that came after the last text of a turn belong to that answer."""
        messages = self.session.messages
        if messages and messages[-1].role is Role.ASSISTANT:
            messages[-1].tools.extend(self._pending_tools)
            messages[-1].thinking.extend(self._pending_thinking)
        self._pending_tools = []
        self._pending_thinking = []


def read_session(path: Path) -> Session:
    """Read a session file.

    Lines that are not valid JSON objects (for example the line the CLI is writing at this very
    moment) are ignored. Raises ``SessionReadError`` if the file cannot be read.
    """
    builder = _Builder()
    try:
        with path.open(encoding="utf-8", errors="replace") as lines:
            for line in lines:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(entry, dict):
                    builder.add(entry)
    except OSError as error:
        raise SessionReadError(f"Cannot read the session file {path}: {error}") from error
    return builder.finish()
