from collections.abc import Iterator

import pytest
import wx

from wxclaude.core.claude.questions import Question, QuestionOption
from wxclaude.ui.question_dialog import QuestionDialog

pytestmark = pytest.mark.ui

QUESTIONS = [
    Question(
        "Which database?",
        "Database",
        (QuestionOption("SQLite", "A file"), QuestionOption("Postgres", "A server")),
    ),
    Question(
        "Which extras?",
        "Extras",
        (QuestionOption("Cache"), QuestionOption("Queue")),
        multi_select=True,
    ),
]


@pytest.fixture
def dialog(wx_app: wx.App) -> Iterator[QuestionDialog]:
    dialog = QuestionDialog(None, QUESTIONS)
    yield dialog
    dialog.Destroy()
    wx.SafeYield()


def _fields(dialog: QuestionDialog) -> list[tuple[wx.CheckListBox, wx.TextCtrl]]:
    return [(field.choices, field.own) for field in dialog._fields]


def _check(box: wx.CheckListBox, index: int) -> None:
    """Check a line the way the user does (Space): the box tells the dialog."""
    box.Check(index)
    event = wx.CommandEvent(wx.wxEVT_CHECKLISTBOX, box.GetId())
    event.SetEventObject(box)
    event.SetInt(index)
    box.GetEventHandler().ProcessEvent(event)


def test_each_question_has_its_choices_with_their_description(dialog: QuestionDialog) -> None:
    (single, _own1), (several, _own2) = _fields(dialog)
    assert single.GetStrings() == ["SQLite: A file", "Postgres: A server"]
    assert isinstance(single, wx.CheckListBox)  # check boxes for every question
    assert isinstance(several, wx.CheckListBox)
    assert several.GetStrings() == ["Cache", "Queue"]


def test_the_first_list_has_the_focus_and_nothing_is_chosen(dialog: QuestionDialog) -> None:
    (single, _own), _second = _fields(dialog)
    assert dialog.FindFocus() is single
    assert dialog.answers == {"Which database?": [], "Which extras?": []}


def test_the_choices_are_the_answers(dialog: QuestionDialog) -> None:
    (single, _own1), (several, _own2) = _fields(dialog)
    _check(single, 1)
    several.Check(0)
    several.Check(1)
    assert dialog.answers == {"Which database?": ["Postgres"], "Which extras?": ["Cache", "Queue"]}


def test_an_answer_of_ones_own_replaces_the_choice(dialog: QuestionDialog) -> None:
    (single, own), _second = _fields(dialog)
    _check(single, 0)
    own.SetValue("  MariaDB  ")
    assert dialog.answers["Which database?"] == ["MariaDB"]


def test_send_needs_an_answer_to_every_question(
    dialog: QuestionDialog, monkeypatch: pytest.MonkeyPatch
) -> None:
    shown: list[str] = []
    monkeypatch.setattr(wx, "MessageBox", lambda message, *_a, **_k: shown.append(message))
    ended: list[int] = []
    dialog.EndModal = ended.append
    (single, _own1), (_several, _own2) = _fields(dialog)
    _check(single, 0)
    wx.PostEvent(dialog, wx.CommandEvent(wx.wxEVT_BUTTON, wx.ID_OK))
    wx.SafeYield()
    assert ended == []
    assert shown == ["Answer every question first."]
    assert dialog.FindFocus() is _fields(dialog)[1][0]  # the question left unanswered
    assert not dialog.sent


def test_send_with_every_question_answered_ends_the_dialog(dialog: QuestionDialog) -> None:
    (single, _own1), (_several, own2) = _fields(dialog)
    _check(single, 0)
    own2.SetValue("None")
    ended: list[int] = []
    dialog.EndModal = ended.append
    wx.PostEvent(dialog, wx.CommandEvent(wx.wxEVT_BUTTON, wx.ID_OK))
    wx.SafeYield()
    assert ended == [wx.ID_OK]
    assert dialog.sent


def test_deny_and_escape_refuse(dialog: QuestionDialog) -> None:
    ended: list[int] = []
    dialog.EndModal = ended.append
    wx.PostEvent(dialog, wx.CommandEvent(wx.wxEVT_BUTTON, wx.ID_NO))
    wx.SafeYield()
    assert ended == [wx.ID_NO]
    assert not dialog.sent
    assert dialog.GetEscapeId() == wx.ID_NO


def test_a_question_without_choices_only_has_the_text_field(wx_app: wx.App) -> None:
    dialog = QuestionDialog(None, [Question("Your name?", "", ())])
    (field,) = dialog._fields
    assert field.choices is None
    assert dialog.FindFocus() is field.own
    field.own.SetValue("Ada")
    assert dialog.answers == {"Your name?": ["Ada"]}
    dialog.Destroy()
    wx.SafeYield()


def test_with_one_answer_allowed_checking_a_line_unchecks_the_others(
    dialog: QuestionDialog,
) -> None:
    (single, _own), _second = _fields(dialog)
    _check(single, 0)
    _check(single, 1)
    assert list(single.GetCheckedItems()) == [1]
    assert dialog.answers["Which database?"] == ["Postgres"]
    single.Check(1, False)  # unchecking a line leaves no answer
    assert dialog.answers["Which database?"] == []


def test_with_several_answers_allowed_the_lines_stay_checked(dialog: QuestionDialog) -> None:
    _first, (several, _own) = _fields(dialog)
    _check(several, 0)
    _check(several, 1)
    assert list(several.GetCheckedItems()) == [0, 1]
