"""A fake ``claude -p`` for the tests: same arguments, same ``stream-json`` input and output.

The first line of stdin is the user message (``{"type": "user", "message": {...}}``). The scenario
comes from the environment variable ``FAKE_CLAUDE`` (default ``ok``):

- ``ok``: init, thinking, a tool call and its result, the answer ``Echo: <prompt>``, the result;
- ``denied``: like ``ok`` with a permission denial before the answer;
- ``permission``: like ``ok`` but the tool call needs a permission: a ``control_request`` is sent
  and the ``control_response`` read on stdin decides (allow: the tool runs; deny: its message is
  the tool result), unless ``.claude/settings.local.json`` already allows ``Bash(touch fake.txt)``.
  With ``--settings`` (a PermissionRequest hook of type http) the question is a POST to the URL of
  the hook and the response decides, with the same results;
- ``question``: like ``ok`` but the tool call is ``AskUserQuestion``: a ``control_request`` with two
  questions is sent and the tool result is what the CLI says of the ``answers`` read back
  (``Your questions have been answered: "<question>"="<label>"``, or a plain denial message);
- ``error``: a result with ``is_error`` and exit code 1;
- ``crash``: nothing on stdout, a message on stderr, exit code 2;
- ``garbage``: a line that is not JSON, then like ``ok``;
- ``slow``: init, then waits (to be interrupted);
- ``rename_fails``: ``/rename`` answers with an error (``-p "/rename <name>"``, no stdin).
- ``/usage`` (``-p "/usage"``, no stdin) answers the gauges as text; ``usage_fails`` answers with an
  error, ``usage_garbage`` with a text without gauges, ``usage_slow`` waits 60 seconds.

``--name <name>`` and ``/rename <name>`` append a ``custom-title`` entry to the session file.
``--resume <a> --fork-session --session-id <b>`` first copies the history of ``a`` into the
session ``b`` (without its title), like the CLI.
Every message costs 0.001 and the ``result`` reports the total of the session, which is also
written to the session file as a ``cost-state`` entry, like the CLI.

After the result the fake waits for the end of stdin, as the real CLI does, so a runner that does
not close stdin hangs the test. ``FAKE_CLAUDE_LOG`` (a file) receives the arguments and the prompt
as JSON, and ``<log>.responses`` the control responses read. When ``CLAUDE_CONFIG_DIR`` is set the
session file is written there like the real CLI does.
"""

import json
import os
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

RULE = "Bash(touch fake.txt)"


def emit(entry: dict[str, object]) -> None:
    print(json.dumps(entry), flush=True)


def option(name: str) -> str:
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else ""


def session_total(session_id: str) -> float:
    """What the session already cost: the last ``cost-state`` entry of its file (0 if none)."""
    config = os.environ.get("CLAUDE_CONFIG_DIR")
    found = next(Path(config, "projects").glob(f"*/{session_id}.jsonl"), None) if config else None
    if found is None:
        return 0.0
    total = 0.0
    for line in found.read_text(encoding="utf-8").splitlines():
        entry = json.loads(line) if line.strip() else {}
        if entry.get("type") == "cost-state":
            total = entry["totalCostUSD"]
    return float(total)


def write_session(
    session_id: str, prompt: str, answer: str, model: str, effort: str, total: float
) -> None:
    config = os.environ.get("CLAUDE_CONFIG_DIR")
    if not config:
        return
    folder = Path(config) / "projects" / "fake"
    folder.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC).isoformat()
    entries: list[dict[str, object]] = [
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
    entries.append({"type": "cost-state", "sessionId": session_id, "totalCostUSD": total})
    with (folder / f"{session_id}.jsonl").open("a", encoding="utf-8") as file:
        for entry in entries:
            file.write(json.dumps(entry) + "\n")


def fork(source_id: str, session_id: str) -> None:
    """Copy the history of ``source_id`` into the new session ``session_id`` (not its title)."""
    config = os.environ.get("CLAUDE_CONFIG_DIR")
    if not config:
        return
    found = next(Path(config, "projects").glob(f"*/{source_id}.jsonl"), None)
    if found is None:
        return
    lines = [
        line
        for line in found.read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line).get("type") != "custom-title"
    ]
    folder = Path(config) / "projects" / "fake"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{session_id}.jsonl").write_text(
        "".join(f"{line}\n" for line in lines), encoding="utf-8"
    )


def prepare_session() -> str:
    """The session of the message: a branch first copies its history, a name is written."""
    session_id = option("--session-id") or option("--resume")
    if "--fork-session" in sys.argv:
        fork(option("--resume"), session_id)
    if option("--name"):
        write_title(session_id, option("--name"))
    return session_id


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


def ask_permission_by_hook(log: str | None) -> tuple[bool, str]:
    """Like the CLI with a PermissionRequest hook of type http: POST the question and wait.

    The URL is read from ``--settings``. An empty response means no decision: the tool is denied
    as in any ``-p`` run. The decision read is written to ``<log>.responses``.
    """
    settings = json.loads(option("--settings"))
    url = settings["hooks"]["PermissionRequest"][0]["hooks"][0]["url"]
    body = {
        "hook_event_name": "PermissionRequest",
        "permission_mode": option("--permission-mode"),
        "tool_name": "Bash",
        "tool_input": {"command": "touch fake.txt", "description": "Create fake.txt"},
        "permission_suggestions": [
            {
                "type": "addRules",
                "rules": [{"toolName": "Bash", "ruleContent": "touch fake.txt"}],
                "behavior": "allow",
                "destination": "localSettings",
            }
        ],
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        reply = json.loads(response.read())
    if log:
        with Path(log + ".responses").open("a", encoding="utf-8") as file:
            file.write(json.dumps(reply) + "\n")
    decision = reply.get("hookSpecificOutput", {}).get("decision", {})
    if decision.get("behavior") == "allow":
        return True, "ran"
    return False, str(decision.get("message", "you haven't granted it yet"))


def ask_permission(log: str | None) -> tuple[bool, str]:
    """Send the permission question and read the answer: (allowed, tool result text)."""
    if "--settings" in sys.argv:
        return ask_permission_by_hook(log)
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


QUESTIONS = [
    {
        "question": "Which database?",
        "header": "Database",
        "options": [
            {"label": "SQLite", "description": "A file"},
            {"label": "Postgres", "description": "A server"},
        ],
        "multiSelect": False,
    },
    {
        "question": "Which extras?",
        "header": "Extras",
        "options": [{"label": "Cache", "description": ""}, {"label": "Queue", "description": ""}],
        "multiSelect": True,
    },
]


def ask_question(log: str | None) -> tuple[bool, str]:
    """Send a structured question (stdio channel): (answered, the tool result of the CLI)."""
    emit(
        {
            "type": "control_request",
            "request_id": "req-q",
            "request": {
                "subtype": "can_use_tool",
                "tool_name": "AskUserQuestion",
                "input": {"questions": QUESTIONS},
                "tool_use_id": "t1",
            },
        }
    )
    line = sys.stdin.buffer.readline().decode("utf-8")
    if log:
        with Path(log + ".responses").open("a", encoding="utf-8") as file:
            file.write(line)
    body = json.loads(line)["response"]["response"]
    if body["behavior"] != "allow":
        return False, str(body.get("message", ""))
    answers = body.get("updatedInput", {}).get("answers", {})
    said = ", ".join(f'"{question}"="{label}"' for question, label in answers.items())
    return True, f"Your questions have been answered: {said}"


def write_title(session_id: str, name: str) -> None:
    """Append a ``custom-title`` entry to the session file, like ``--name`` and ``/rename``."""
    config = os.environ.get("CLAUDE_CONFIG_DIR")
    if not config:
        return
    folder = Path(config) / "projects" / "fake"
    folder.mkdir(parents=True, exist_ok=True)
    entry = {"type": "custom-title", "customTitle": name, "sessionId": session_id}
    with (folder / f"{session_id}.jsonl").open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry) + "\n")


def prompt_argument() -> str:
    """The prompt given after ``-p`` ('' if there is none: it then comes through stdin)."""
    if "-p" not in sys.argv:
        return ""
    index = sys.argv.index("-p") + 1
    return sys.argv[index] if index < len(sys.argv) else ""


def rename_command() -> str | None:
    """The new name when the prompt is ``/rename <name>`` (given after ``-p``), else None."""
    prompt = prompt_argument()
    return prompt.removeprefix("/rename ") if prompt.startswith("/rename ") else None


def rename(name: str) -> int:
    """Answer ``/rename <name>`` like the CLI: write the title, say so, no model involved."""
    log = os.environ.get("FAKE_CLAUDE_LOG")
    if log:
        Path(log).write_text(json.dumps({"arguments": sys.argv[1:]}), encoding="utf-8")
    if os.environ.get("FAKE_CLAUDE") == "rename_fails":
        print(json.dumps({"type": "result", "is_error": True, "result": "No such session"}))
        return 1
    write_title(option("--resume"), name)
    result = f"Session renamed to: {name}"
    print(json.dumps({"type": "result", "is_error": False, "result": result}))
    return 0


def usage() -> int:
    """Answer ``/usage`` like the CLI: the gauges as text, at once, no model, no session file."""
    log = os.environ.get("FAKE_CLAUDE_LOG")
    if log:
        Path(log).write_text(json.dumps({"arguments": sys.argv[1:]}), encoding="utf-8")
    scenario = os.environ.get("FAKE_CLAUDE", "ok")
    if scenario == "usage_slow":
        time.sleep(60)
    if scenario == "usage_fails":
        print(json.dumps({"type": "result", "is_error": True, "result": "No access"}))
        return 1
    text = "Nothing to see here."
    if scenario != "usage_garbage":
        text = (
            "Current session: 96% used · resets Oct 23, 1:50pm (Europe/Paris)\n"
            "Current week (all models): 67% used · resets Oct 26, 1am (Europe/Paris)\n"
        )
    print(json.dumps({"type": "result", "is_error": False, "result": text}))
    return 0


def local_command() -> int | None:
    """Run the command given as the prompt (``/rename``, ``/usage``), else None."""
    renamed = rename_command()
    if renamed is not None:
        return rename(renamed)
    if prompt_argument() == "/usage":
        return usage()
    return None


def main() -> int:
    local = local_command()
    if local is not None:
        return local
    first_line = sys.stdin.buffer.readline().decode("utf-8")
    prompt = json.loads(first_line)["message"]["content"]
    scenario = os.environ.get("FAKE_CLAUDE", "ok")
    log = os.environ.get("FAKE_CLAUDE_LOG")
    if log:
        Path(log).write_text(
            json.dumps({"arguments": sys.argv[1:], "prompt": prompt, "cwd": str(Path.cwd())}),
            encoding="utf-8",
        )
    session_id = prepare_session()
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
    if scenario == "question":
        allowed, tool_result = ask_question(log)
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
    total = round(session_total(session_id) + 0.001, 6)
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
            "total_cost_usd": total,
            "num_turns": 1,
            "usage": {"input_tokens": 3, "output_tokens": 4},
        }
    )
    if not failed:
        write_session(session_id, prompt, answer, model, option("--effort"), total)
    sys.stdin.buffer.read()  # like the real CLI: ends when its input is closed
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
