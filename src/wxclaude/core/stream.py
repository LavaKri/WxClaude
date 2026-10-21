"""Reading the ``stream-json`` output of ``claude -p``: one JSON object per line.

``parse_stream_line`` turns a line into zero or more events. Lines of a kind that is not used
(``prompt_suggestion``, unknown types) give no event. See ``docs/claude-cli.md``.
"""

import json

from wxclaude.core.errors import StreamParseError
from wxclaude.core.events import (
    AssistantText,
    PermissionDenied,
    PermissionRequest,
    RateLimit,
    RateWindow,
    RunEvent,
    SessionInit,
    Thinking,
    ToolResult,
    ToolUsed,
    TurnResult,
)
from wxclaude.core.messages import Usage


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _number(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def _usage(raw: object) -> Usage | None:
    if not isinstance(raw, dict):
        return None
    return Usage(
        _int(raw.get("input_tokens")) or 0,
        _int(raw.get("output_tokens")) or 0,
        _int(raw.get("cache_creation_input_tokens")) or 0,
        _int(raw.get("cache_read_input_tokens")) or 0,
    )


def _system(entry: dict[str, object]) -> list[RunEvent]:
    subtype = entry.get("subtype")
    if subtype == "init":
        return [
            SessionInit(
                _text(entry.get("session_id")),
                _text(entry.get("model")),
                _text(entry.get("permissionMode")),
            )
        ]
    if subtype == "thinking_tokens":
        return [Thinking(_int(entry.get("estimated_tokens")))]
    if subtype == "permission_denied":
        return [PermissionDenied(_text(entry.get("tool_name")), _text(entry.get("message")))]
    return []


def _assistant(entry: dict[str, object]) -> list[RunEvent]:
    message = entry.get("message")
    if not isinstance(message, dict):
        return []
    model = message.get("model")
    model_name = model if isinstance(model, str) and model != "<synthetic>" else None
    events: list[RunEvent] = []
    content = message.get("content")
    for block in content if isinstance(content, list) else []:
        if not isinstance(block, dict):
            continue
        kind = block.get("type")
        if kind == "text" and _text(block.get("text")).strip():
            events.append(AssistantText(_text(block.get("text")), model_name))
        elif kind == "thinking":
            events.append(Thinking())
        elif kind == "tool_use":
            raw_input = block.get("input")
            events.append(
                ToolUsed(
                    _text(block.get("id")),
                    _text(block.get("name")),
                    raw_input if isinstance(raw_input, dict) else {},
                )
            )
    return events


def _user(entry: dict[str, object]) -> list[RunEvent]:
    message = entry.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    return [
        ToolResult(_text(block.get("tool_use_id")), bool(block.get("is_error")))
        for block in (content if isinstance(content, list) else [])
        if isinstance(block, dict) and block.get("type") == "tool_result"
    ]


def _suggested_rule(suggestions: object) -> str:
    """The rule to allow that the CLI proposes (``Bash(touch x)``, ``Edit``), '' if none."""
    for suggestion in suggestions if isinstance(suggestions, list) else []:
        if not isinstance(suggestion, dict) or suggestion.get("type") != "addRules":
            continue
        if suggestion.get("behavior") != "allow":
            continue
        rules = suggestion.get("rules")
        for rule in rules if isinstance(rules, list) else []:
            if isinstance(rule, dict) and _text(rule.get("toolName")):
                content = _text(rule.get("ruleContent"))
                name = _text(rule.get("toolName"))
                return f"{name}({content})" if content else name
    return ""


def _control_request(entry: dict[str, object]) -> list[RunEvent]:
    request = entry.get("request")
    if not isinstance(request, dict) or request.get("subtype") != "can_use_tool":
        return []
    raw_input = request.get("input")
    return [
        PermissionRequest(
            request_id=_text(entry.get("request_id")),
            tool_name=_text(request.get("tool_name")),
            tool_use_id=_text(request.get("tool_use_id")),
            input=raw_input if isinstance(raw_input, dict) else {},
            description=_text(request.get("description")),
            blocked_path=_text(request.get("blocked_path")),
            suggested_rule=_suggested_rule(request.get("permission_suggestions")),
        )
    ]


def _rate_limit(entry: dict[str, object]) -> list[RunEvent]:
    info = entry.get("rate_limit_info")
    if not isinstance(info, dict):
        return []
    raw_windows = info.get("unifiedWindows")
    limit_type = _text(info.get("rateLimitType"))
    windows = tuple(
        RateWindow(name, _number(raw.get("utilization")), _int(raw.get("resetsAt")))
        for name, raw in (raw_windows.items() if isinstance(raw_windows, dict) else [])
        if isinstance(raw, dict)
    )
    if not windows and limit_type:
        windows = (RateWindow(limit_type, None, _int(info.get("resetsAt"))),)
    return [RateLimit(_text(info.get("status")), limit_type, windows)]


def _result(entry: dict[str, object]) -> list[RunEvent]:
    subtype = _text(entry.get("subtype"))
    return [
        TurnResult(
            is_error=bool(entry.get("is_error")) or subtype.startswith("error"),
            subtype=subtype,
            text=_text(entry.get("result")),
            usage=_usage(entry.get("usage")),
            duration_ms=_int(entry.get("duration_ms")),
            cost_usd=_number(entry.get("total_cost_usd")),
            num_turns=_int(entry.get("num_turns")),
        )
    ]


_PARSERS = {
    "system": _system,
    "assistant": _assistant,
    "user": _user,
    "control_request": _control_request,
    "rate_limit_event": _rate_limit,
    "result": _result,
}


def parse_stream_line(line: str) -> list[RunEvent]:
    """The events on ``line``; raises ``StreamParseError`` if it is not a JSON object."""
    try:
        entry = json.loads(line)
    except json.JSONDecodeError as error:
        raise StreamParseError(f"Not a JSON line: {line[:200]!r}") from error
    if not isinstance(entry, dict):
        raise StreamParseError(f"Not a JSON object: {line[:200]!r}")
    parser = _PARSERS.get(str(entry.get("type")))
    return parser(entry) if parser is not None else []
