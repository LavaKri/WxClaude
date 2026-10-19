"""A fake ``claude -p`` for the tests: same arguments, same ``stream-json`` output.

The scenario comes from the environment variable ``FAKE_CLAUDE`` (default ``ok``):

- ``ok``: init, thinking, a tool call and its result, the answer ``Echo: <prompt>``, the result;
- ``denied``: like ``ok`` with a permission denial before the answer;
- ``error``: a result with ``is_error`` and exit code 1;
- ``crash``: nothing on stdout, a message on stderr, exit code 2;
- ``garbage``: a line that is not JSON, then like ``ok``;
- ``slow``: init, then waits (to be interrupted).

``FAKE_CLAUDE_LOG`` (a file) receives the arguments and the prompt as JSON. When
``CLAUDE_CONFIG_DIR`` is set the session file is written there like the real CLI does.
"""

import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path


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
            "cwd": os.getcwd(),
            "permissionMode": option("--permission-mode"),
            "timestamp": now,
            "message": {"role": "user", "content": prompt},
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


def main() -> int:
    prompt = sys.stdin.buffer.read().decode("utf-8")  # the prompt is sent as UTF-8
    scenario = os.environ.get("FAKE_CLAUDE", "ok")
    log = os.environ.get("FAKE_CLAUDE_LOG")
    if log:
        Path(log).write_text(
            json.dumps({"arguments": sys.argv[1:], "prompt": prompt, "cwd": os.getcwd()}),
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
                    {"type": "tool_result", "tool_use_id": "t1", "is_error": False, "content": "x"}
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
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
