"""A fake ``claude -p`` for the tests: same arguments, same ``stream-json`` input and output.

The first line of stdin is the user message (``{"type": "user", "message": {...}}``). The scenario
comes from the environment variable ``FAKE_CLAUDE`` (default ``ok``):

- ``ok``: init, thinking, a tool call and its result, the answer ``Echo: <prompt>``, the result;
- ``denied``: like ``ok`` with a permission denial before the answer;
- ``permission``: like ``ok`` but the tool call needs a permission: a ``control_request`` is sent
  and the ``control_response`` read on stdin decides (allow: the tool runs; deny: its message is
  the tool result), unless ``.claude/settings.local.json`` already allows ``Bash(touch fake.txt)``;
- ``error``: a result with ``is_error`` and exit code 1;
- ``crash``: nothing on stdout, a message on stderr, exit code 2;
- ``garbage``: a line that is not JSON, then like ``ok``;
- ``slow``: init, then waits (to be interrupted).

After the result the fake waits for the end of stdin, as the real CLI does, so a runner that does
not close stdin hangs the test. ``FAKE_CLAUDE_LOG`` (a file) receives the arguments and the prompt
as JSON, and ``<log>.responses`` the control responses read. When ``CLAUDE_CONFIG_DIR`` is set the
session file is written there like the real CLI does.
"""

import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

RULE = "Bash(touch fake.txt)"


def emit(entry: dict[str, object]) -> None:
    print(json.dumps(entry), flush=True)


def option(name: str) -> str:
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else ""


def write_session(session_id: str, prompt: str, answer: str, model: str, effort: str) -> None:
    config = os.environ.get("CLAUDE_CONFIG_DIR")
    if not config:
        return
    folder = Path(config) / "projects" / "fake"
    folder.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC).isoformat()
    entries = [
        {
            "type": "user",
            "uuid": f"u-{time.time_ns()}",
            "cwd": str(Path.cwd()),
            "permissionMode": option("--permission-mode"),
            "timestamp": now,
            "message": {"role": "user", "content": prompt},
        },
        {
            "type": "assistant",
            "uuid": f"t-{time.time_ns()}",
            "effort": effort,
            "timestamp": now,
            "message": {
                "role": "assistant",
                "model": model,
                "content": [
                    {
                        "type": "tool_use",
                        "id": "t1",
                        "name": "Read",
                        "input": {"file_path": "n.txt"},
                    }
                ],
            },
        },
        {
            "type": "user",
            "uuid": f"r-{time.time_ns()}",
            "timestamp": now,
            "message": {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "x"}],
            },
        },
        {
            "type": "assistant",
            "uuid": f"a-{time.time_ns()}",
            "effort": effort,
            "timestamp": now,
            "message": {
                "role": "assistant",
                "model": model,
                "content": [{"type": "text", "text": answer}],
            },
        },
    ]
    with (folder / f"{session_id}.jsonl").open("a", encoding="utf-8") as file:
        for entry in entries:
            file.write(json.dumps(entry) + "\n")


def rule_allowed() -> bool:
    """Does the personal settings file of the working folder allow the rule (like the CLI)?"""
    path = Path(".claude") / "settings.local.json"
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return False  # like the CLI, a broken file is skipped
    permissions = data.get("permissions", {}) if isinstance(data, dict) else {}
    return RULE in permissions.get("allow", [])


def ask_permission(log: str | None) -> tuple[bool, str]:
    """Send the permission question and read the answer: (allowed, tool result text)."""
    emit(
        {
            "type": "control_request",
            "request_id": "req-1",
            "request": {
                "subtype": "can_use_tool",
                "tool_name": "Bash",
                "input": {"command": "touch fake.txt", "description": "Create fake.txt"},
                "description": "Create fake.txt",
                "tool_use_id": "t1",
                "blocked_path": "fake.txt",
                "permission_suggestions": [
                    {
                        "type": "addRules",
                        "rules": [{"toolName": "Bash", "ruleContent": "touch fake.txt"}],
                        "behavior": "allow",
                        "destination": "localSettings",
                    }
                ],
            },
        }
    )
    line = sys.stdin.buffer.readline().decode("utf-8")
    if log:
        with Path(log + ".responses").open("a", encoding="utf-8") as file:
            file.write(line)
    body = json.loads(line)["response"]["response"]
    if body["behavior"] == "allow":
        return True, "ran"
    return False, str(body.get("message", ""))


def main() -> int:
    first_line = sys.stdin.buffer.readline().decode("utf-8")
    prompt = json.loads(first_line)["message"]["content"]
    scenario = os.environ.get("FAKE_CLAUDE", "ok")
    log = os.environ.get("FAKE_CLAUDE_LOG")
    if log:
        Path(log).write_text(
            json.dumps({"arguments": sys.argv[1:], "prompt": prompt, "cwd": str(Path.cwd())}),
            encoding="utf-8",
        )
    session_id = option("--session-id") or option("--resume")
    model = "claude-" + option("--model") + "-fake"
    if scenario == "crash":
        print("fake claude: not logged in", file=sys.stderr, flush=True)
        return 2
    if scenario == "garbage":
        print("this is not json", flush=True)
    emit(
        {
            "type": "system",
            "subtype": "init",
            "session_id": session_id,
            "model": model,
            "permissionMode": option("--permission-mode"),
        }
    )
    if scenario == "slow":
        time.sleep(60)
        return 0
    emit({"type": "system", "subtype": "thinking_tokens", "estimated_tokens": 12})
    emit(
        {
            "type": "assistant",
            "message": {"model": model, "content": [{"type": "thinking", "thinking": ""}]},
        }
    )
    emit(
        {
            "type": "assistant",
            "message": {
                "model": model,
                "content": [{"type": "tool_use", "id": "t1", "name": "Read", "input": {}}],
            },
        }
    )
    tool_result, tool_error = "x", False
    if scenario == "permission" and not rule_allowed():
        allowed, tool_result = ask_permission(log)
        tool_error = not allowed
    if scenario == "denied":
        emit(
            {
                "type": "system",
                "subtype": "permission_denied",
                "tool_name": "Bash",
                "tool_use_id": "t2",
                "message": "Bash needs permission",
            }
        )
    emit(
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "t1",
                        "is_error": tool_error,
                        "content": tool_result,
                    }
                ]
            },
        }
    )
    answer = f"Echo: {prompt}"
    emit(
        {
            "type": "assistant",
            "message": {"model": model, "content": [{"type": "text", "text": answer}]},
        }
    )
    emit(
        {
            "type": "rate_limit_event",
            "rate_limit_info": {
                "status": "allowed",
                "rateLimitType": "five_hour",
                "resetsAt": 1,
                "unifiedWindows": {"five_hour": {"utilization": 0.5, "resetsAt": 1}},
            },
        }
    )
    failed = scenario == "error"
    emit(
        {
            "type": "result",
            "subtype": "error_max_turns" if failed else "success",
            "is_error": failed,
            "result": "Too many turns" if failed else answer,
            "duration_ms": 10,
            "total_cost_usd": 0.001,
            "num_turns": 1,
            "usage": {"input_tokens": 3, "output_tokens": 4},
        }
    )
    if not failed:
        write_session(session_id, prompt, answer, model, option("--effort"))
    sys.stdin.buffer.read()  # like the real CLI: ends when its input is closed
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
