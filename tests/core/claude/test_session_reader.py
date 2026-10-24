import json
from pathlib import Path

import pytest

from wxclaude.core.claude.session_reader import read_session
from wxclaude.core.config.agents import Agent
from wxclaude.core.conversation.messages import Role
from wxclaude.core.errors import SessionReadError

pytestmark = pytest.mark.unit


def _write(path: Path, entries: list[object]) -> Path:
    lines = [entry if isinstance(entry, str) else json.dumps(entry) for entry in entries]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _user(text: object, uuid: str = "u", **extra: object) -> dict[str, object]:
    return {"type": "user", "uuid": uuid, "message": {"role": "user", "content": text}, **extra}


def _assistant(
    blocks: list[dict[str, object]], uuid: str = "a", model: str = "claude-sonnet-5-5"
) -> dict[str, object]:
    usage = {"input_tokens": 3, "output_tokens": 5}
    message = {"role": "assistant", "model": model, "content": blocks, "usage": usage}
    return {"type": "assistant", "uuid": uuid, "message": message}


def _text(text: str) -> dict[str, object]:
    return {"type": "text", "text": text}


def test_prompts_and_answers_become_messages(tmp_path: Path) -> None:
    session = read_session(
        _write(tmp_path / "s.jsonl", [_user("Hello", "u1"), _assistant([_text("Hi")], "a1")])
    )
    assert [(m.role, m.text, m.model) for m in session.messages] == [
        (Role.USER, "Hello", None),
        (Role.ASSISTANT, "Hi", "claude-sonnet-5-5"),
    ]
    assert session.last_model == "claude-sonnet-5-5"
    assert (session.usage.input_tokens, session.usage.output_tokens) == (3, 5)


def test_duplicate_consecutive_answers_are_removed(tmp_path: Path) -> None:
    answer = _assistant([_text("Hi")])
    session = read_session(_write(tmp_path / "s.jsonl", [_user("Hello"), answer, answer]))
    assert len(session.messages) == 2
    assert session.usage.output_tokens == 5


def test_noise_is_hidden(tmp_path: Path) -> None:
    session = read_session(
        _write(
            tmp_path / "s.jsonl",
            [_user("continue"), _assistant([_text("No response requested.")])],
        )
    )
    assert [m.hidden for m in session.messages] == [True, True]


def test_the_summary_of_a_compaction_is_hidden(tmp_path: Path) -> None:
    summary = _user("This session is being continued...", isCompactSummary=True)
    session = read_session(
        _write(tmp_path / "s.jsonl", [_user("hello"), summary, _assistant([_text("Hi")])])
    )
    assert [m.hidden for m in session.messages] == [False, True, False]


def test_synthetic_answers_are_kept_without_model(tmp_path: Path) -> None:
    session = read_session(
        _write(
            tmp_path / "s.jsonl",
            [_user("Hello"), _assistant([_text("Limit reached")], model="<synthetic>")],
        )
    )
    assert session.messages[1].model is None
    assert session.last_model is None


def test_tools_results_and_thinking_are_kept_as_details(tmp_path: Path) -> None:
    tool: dict[str, object] = {
        "type": "tool_use",
        "id": "t1",
        "name": "Read",
        "input": {"file_path": "x"},
    }
    result = {"type": "tool_result", "tool_use_id": "t1", "content": "data", "is_error": False}
    session = read_session(
        _write(
            tmp_path / "s.jsonl",
            [
                _user("Look"),
                _assistant([{"type": "thinking", "thinking": "hmm"}], "a1"),
                _assistant([tool], "a2"),
                _user([result], "u2"),
                _assistant([_text("Done")], "a3"),
            ],
        )
    )
    assert len(session.messages) == 2
    answer = session.messages[1]
    assert answer.thinking == ["hmm"]
    assert [(t.name, t.result, t.is_error) for t in answer.tools] == [("Read", "data", False)]


def test_trailing_tools_belong_to_the_last_answer(tmp_path: Path) -> None:
    tool: dict[str, object] = {"type": "tool_use", "id": "t1", "name": "Bash", "input": {}}
    session = read_session(
        _write(tmp_path / "s.jsonl", [_user("Go"), _assistant([_text("Ok")]), _assistant([tool])])
    )
    assert [t.name for t in session.messages[1].tools] == ["Bash"]


def test_meta_and_sidechain_entries_are_ignored(tmp_path: Path) -> None:
    session = read_session(
        _write(
            tmp_path / "s.jsonl",
            [_user("meta", isMeta=True), _user("side", isSidechain=True), _user("real")],
        )
    )
    assert [m.text for m in session.messages] == ["real"]


def test_custom_title_wins_over_ai_title(tmp_path: Path) -> None:
    entries: list[object] = [
        {"type": "ai-title", "aiTitle": "Generated"},
        {"type": "custom-title", "customTitle": "Mine"},
    ]
    assert read_session(_write(tmp_path / "s.jsonl", entries)).title == "Mine"
    assert read_session(_write(tmp_path / "t.jsonl", entries[:1])).title == "Generated"


def test_last_permission_mode_and_broken_lines(tmp_path: Path) -> None:
    session = read_session(
        _write(
            tmp_path / "s.jsonl",
            [_user("a", permissionMode="plan"), "not json", '{"type": "user", "mess'],
        )
    )
    assert session.last_permission_mode == "plan"
    assert len(session.messages) == 1


def test_the_total_cost_of_the_session_is_the_last_cost_state(tmp_path: Path) -> None:
    states: list[object] = [
        {"type": "cost-state", "totalCostUSD": 0.04},
        _user("Hello"),
        {"type": "cost-state", "totalCostUSD": 0.06},
        {"type": "cost-state", "totalCostUSD": "free"},  # not a number: ignored
    ]
    assert read_session(_write(tmp_path / "s.jsonl", states)).total_cost_usd == 0.06
    assert read_session(_write(tmp_path / "t.jsonl", [_user("Hello")])).total_cost_usd is None


def test_the_totals_of_the_session_are_kept_with_their_place_in_the_history(
    tmp_path: Path,
) -> None:
    first = {"type": "cost-state", "totalCostUSD": 0.04, "totalAPIDuration": 3000}
    second = {
        "type": "cost-state",
        "totalCostUSD": 0.06,
        "totalAPIDuration": 4000,
        "totalToolDuration": 500,
        "modelUsage": {"claude-haiku-4-5": {"inputTokens": 7, "costUSD": 0.06}},
    }
    entries: list[object] = [
        _user("Hello", "u1"),
        _assistant([_text("Hi")], "a1"),
        first,
        _user("Again", "u2"),
        _assistant([_text("Yes")], "a2"),
        second,
    ]
    session = read_session(_write(tmp_path / "s.jsonl", entries))
    assert [(s.after_messages, s.cost, s.activity_ms) for s in session.cost_states] == [
        (2, 0.04, 3000),
        (4, 0.06, 4500),
    ]
    assert session.cost_states[-1].models["claude-haiku-4-5"].input_tokens == 7
    assert session.total_cost_usd == 0.06


def test_the_start_of_the_session_is_its_first_timestamp(tmp_path: Path) -> None:
    entries: list[object] = [
        {"type": "custom-title", "customTitle": "No time"},
        _user("Hello", "u1", timestamp="2026-10-21T08:00:00.000Z"),
        _user("Later", "u2", timestamp="2026-10-22T09:00:00.000Z"),
    ]
    assert read_session(_write(tmp_path / "s.jsonl", entries)).started == "2026-10-21T08:00:00.000Z"
    assert read_session(_write(tmp_path / "t.jsonl", [_user("Hi")])).started == ""


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(SessionReadError):
        read_session(tmp_path / "missing.jsonl")


def test_the_effort_of_an_answer_is_read_from_its_entry(tmp_path: Path) -> None:
    answer = _assistant([_text("Hi")])
    answer["effort"] = "high"
    synthetic = _assistant([_text("Limit")], "b", model="<synthetic>")
    synthetic["effort"] = "high"
    session = read_session(_write(tmp_path / "s.jsonl", [_user("Hello"), answer, synthetic]))
    assert [m.effort for m in session.messages] == [None, "high", None]


def test_the_last_agent_is_the_one_of_the_last_answer(tmp_path: Path) -> None:
    first = _assistant([_text("a")], "a1", model="claude-haiku-4-5")
    first["effort"] = "low"
    last = _assistant([_text("b")], "a2", model="claude-opus-5-5")
    last["effort"] = "high"
    session = read_session(
        _write(tmp_path / "s.jsonl", [_user("x", permissionMode="plan"), first, last])
    )
    assert session.last_agent == Agent(
        model="claude-opus-5-5", effort="high", permission_mode="plan"
    )
    assert read_session(_write(tmp_path / "t.jsonl", [_user("x")])).last_agent == Agent()
