import json
import sys
import threading
from pathlib import Path

import pytest

from wxclaude.core.claude.events import PermissionRequest, RunEvent, ToolResult, TurnEnded
from wxclaude.core.claude.questions import (
    Question,
    QuestionOption,
    answered_input,
    is_question,
    parse_questions,
)
from wxclaude.core.claude.runner import ClaudeRunner, RunRequest
from wxclaude.core.config.agents import Agent

pytestmark = pytest.mark.unit

FAKE = Path(__file__).resolve().parents[2] / "fakes" / "fake_claude.py"
AGENT = Agent(model="haiku", effort="low", permission_mode="manual")
SESSION = "11111111-1111-4111-8111-111111111111"

INPUT = {
    "questions": [
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
            "options": [{"label": "Cache"}, {"label": "Queue", "description": ""}],
            "multiSelect": True,
        },
    ]
}


def _request(tool: str = "AskUserQuestion", **input_: object) -> PermissionRequest:
    return PermissionRequest("r1", tool, "t1", dict(input_ or INPUT), "", "", "")


def test_only_the_question_tool_is_a_question() -> None:
    assert is_question(_request())
    assert not is_question(_request("Bash", command="ls"))


def test_the_questions_and_their_options_are_read() -> None:
    first, second = parse_questions(_request())
    assert first == Question(
        "Which database?",
        "Database",
        (QuestionOption("SQLite", "A file"), QuestionOption("Postgres", "A server")),
        multi_select=False,
    )
    assert second.multi_select is True
    assert second.options == (QuestionOption("Cache", ""), QuestionOption("Queue", ""))


@pytest.mark.parametrize(
    "questions",
    [
        "not a list",
        ["not a dict"],
        [{"header": "no question text"}],
        [{"question": "q", "options": [{"description": "no label"}]}],
        [{"question": "q", "options": ["not a dict"]}],
    ],
)
def test_input_that_cannot_be_read_gives_no_question(questions: object) -> None:
    assert parse_questions(_request(questions=questions)) == []


def test_a_request_without_questions_gives_none() -> None:
    assert parse_questions(_request("AskUserQuestion", other=1)) == []


def test_a_question_without_options_is_kept_for_a_free_answer() -> None:
    (question,) = parse_questions(_request(questions=[{"question": "Name?"}]))
    assert question == Question("Name?", "", (), multi_select=False)


def test_the_answers_are_added_to_the_input_of_the_request() -> None:
    request = _request()
    result = answered_input(
        request, {"Which database?": ["SQLite"], "Which extras?": ["Cache", "Queue"]}
    )
    assert result["questions"] == INPUT["questions"]  # the questions come back unchanged
    assert result["answers"] == {"Which database?": "SQLite", "Which extras?": "Cache, Queue"}
    assert "answers" not in request.input  # the request itself is left as it was


def test_a_free_text_answer_is_given_as_it_is() -> None:
    result = answered_input(_request(), {"Which database?": ["Something else, please"]})
    assert result["answers"] == {"Which database?": "Something else, please"}


class _Answerer:
    """Answers the structured question of the fake CLI with the labels given."""

    def __init__(self, runner: ClaudeRunner, answers: dict[str, list[str]]) -> None:
        self.events: list[RunEvent] = []
        self.requests: list[PermissionRequest] = []
        self.done = threading.Event()
        self._runner = runner
        self._answers = answers

    def __call__(self, event: RunEvent) -> None:
        if isinstance(event, PermissionRequest):
            self.requests.append(event)
            self._runner.answer_questions(event, self._answers)
        self.events.append(event)
        if isinstance(event, TurnEnded):
            self.done.set()


def test_the_runner_answers_the_questions_of_the_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_CLAUDE", "question")
    log = tmp_path / "log.json"
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
    runner = ClaudeRunner([sys.executable, str(FAKE)])
    answerer = _Answerer(
        runner, {"Which database?": ["Postgres"], "Which extras?": ["Cache", "Queue"]}
    )
    runner.start(RunRequest("Hello", AGENT, SESSION, False, tmp_path), answerer)
    assert answerer.done.wait(30), "the run did not end"
    (request,) = answerer.requests
    assert is_question(request)
    assert [q.text for q in parse_questions(request)] == ["Which database?", "Which extras?"]
    result = next(e for e in answerer.events if isinstance(e, ToolResult))
    assert not result.is_error
    sent = json.loads(Path(str(log) + ".responses").read_text(encoding="utf-8"))
    body = sent["response"]["response"]
    assert body["behavior"] == "allow"
    assert body["updatedInput"]["answers"] == {
        "Which database?": "Postgres",
        "Which extras?": "Cache, Queue",
    }
    assert body["updatedInput"]["questions"] == request.input["questions"]
