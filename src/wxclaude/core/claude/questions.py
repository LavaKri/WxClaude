"""The structured questions of Claude (the ``AskUserQuestion`` tool) and their answers.

With the stdio channel the CLI sends the tool as a permission request whose ``input`` holds
``questions``: each has a ``question``, a ``header``, ``options`` (a ``label`` and a ``description``
each) and ``multiSelect``. The answer is the same input with ``answers`` added, a dictionary from
the text of each question to the label chosen (``docs/claude-cli.md``, "Permission channels").
The hook channel never receives this tool.
"""

from dataclasses import dataclass

from wxclaude.core.claude.events import PermissionRequest

QUESTION_TOOL = "AskUserQuestion"
SEPARATOR = ", "  # between the labels chosen for a question that accepts several


@dataclass(frozen=True, slots=True)
class QuestionOption:
    """One choice offered for a question."""

    label: str
    description: str = ""


@dataclass(frozen=True, slots=True)
class Question:
    """A question of Claude with the choices it offers."""

    text: str
    header: str
    options: tuple[QuestionOption, ...]
    multi_select: bool = False


def is_question(request: PermissionRequest) -> bool:
    """Is the request a structured question (and not the permission to run a tool)?"""
    return request.tool_name == QUESTION_TOOL


def parse_questions(request: PermissionRequest) -> list[Question]:
    """The questions of ``request``; an empty list when it holds none that can be read, so that
    the caller can show it as an ordinary request."""
    raw = request.input.get("questions")
    if not isinstance(raw, list):
        return []
    questions: list[Question] = []
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("question"), str):
            return []
        options = tuple(_option(option) for option in item.get("options") or [])
        if not all(options):
            return []
        questions.append(
            Question(
                text=item["question"],
                header=str(item.get("header") or ""),
                options=tuple(option for option in options if option is not None),
                multi_select=bool(item.get("multiSelect")),
            )
        )
    return questions


def _option(raw: object) -> QuestionOption | None:
    if not isinstance(raw, dict) or not isinstance(raw.get("label"), str):
        return None
    return QuestionOption(raw["label"], str(raw.get("description") or ""))


def answered_input(request: PermissionRequest, answers: dict[str, list[str]]) -> dict[str, object]:
    """The input to give back with *allow*: the request's own, plus ``answers``.

    ``answers`` maps the text of each question to the labels chosen (or the free text the user
    wrote); several labels are joined with ``, ``.
    """
    joined = {question: SEPARATOR.join(chosen) for question, chosen in answers.items()}
    return {**request.input, "answers": joined}
