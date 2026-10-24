"""The dialog for the structured questions of Claude: one list of check boxes per question."""

from collections.abc import Sequence

import wx

from wxclaude.core.claude.questions import Question
from wxclaude.core.labels import accessible_name
from wxclaude.i18n import _

_MAX_ROWS = 5  # a list shows at most this many choices before it scrolls


def _plain(text: str) -> str:
    """``text`` for a label: a lone ``&`` would be taken for an access key."""
    return text.replace("&", "&&")


class _Field:
    """What the user fills for one question: a list of choices and a text of their own."""

    def __init__(
        self, question: Question, choices: wx.CheckListBox | None, own: wx.TextCtrl
    ) -> None:
        self.question = question
        self.choices = choices
        self.own = own

    def answer(self) -> list[str]:
        """The labels chosen, or the user's own text (which replaces them); empty if none."""
        own = str(self.own.GetValue()).strip()
        if own:
            return [own]
        if self.choices is None:
            return []
        picked = self.choices.GetCheckedItems()
        return [self.question.options[index].label for index in picked]


class QuestionDialog(wx.Dialog):
    """Claude's questions, each with its choices as a list of check boxes (Space checks, and the
    screen reader says so; when only one answer is allowed, checking a line unchecks the others)
    and a field for an answer of one's own. *Send* needs an answer to every question; *Deny* and
    Esc refuse.

    The first list has the initial focus. Nothing is chosen at first: a stray Enter sends nothing.
    """

    def __init__(self, parent: wx.Window, questions: Sequence[Question]) -> None:
        super().__init__(
            parent, title=_("Claude asks you"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        self._fields: list[_Field] = []
        self._answer = wx.ID_NO
        sizer = wx.BoxSizer(wx.VERTICAL)
        for question in questions:
            self._add_question(sizer, question)
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        send = wx.Button(self, wx.ID_OK, _("&Send"))
        buttons.Add(send, 0, wx.RIGHT, 6)
        buttons.Add(wx.Button(self, wx.ID_NO, _("&Deny")), 0)
        sizer.Add(buttons, 0, wx.ALL, 8)
        self.SetSizerAndFit(sizer)
        send.SetDefault()
        self.SetEscapeId(wx.ID_NO)
        self.Bind(wx.EVT_BUTTON, self._on_button)
        (self._first_control(self._fields[0]) if self._fields else send).SetFocus()

    @property
    def answers(self) -> dict[str, list[str]]:
        """The answers by text of question (what was filled in)."""
        return {field.question.text: field.answer() for field in self._fields}

    @property
    def sent(self) -> bool:
        """Did the user send the answers (else the questions were refused)?"""
        return bool(self._answer == wx.ID_OK)

    def _add_question(self, sizer: wx.BoxSizer, question: Question) -> None:
        # Each label is created right before its control so that screen readers pair them.
        title = _("{header}: {question}").format(header=question.header, question=question.text)
        text = title if question.header else question.text
        choices: wx.CheckListBox | None = None
        if question.options:
            sizer.Add(wx.StaticText(self, label=_plain(text)), 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
            lines = [_option_line(option.label, option.description) for option in question.options]
            name = accessible_name(text)
            choices = wx.CheckListBox(self, choices=lines, name=name)
            if not question.multi_select:
                choices.Bind(wx.EVT_CHECKLISTBOX, self._keep_one_checked)
            choices.SetMinSize(
                wx.Size(choices.GetCharWidth() * 60, choices.GetCharHeight() * _rows(lines))
            )
            sizer.Add(choices, 0, wx.EXPAND | wx.ALL, 8)
        own_label = _("Your own answer, if none of the choices fits") if choices else text
        sizer.Add(wx.StaticText(self, label=_plain(own_label)), 0, wx.LEFT | wx.RIGHT, 8)
        own = wx.TextCtrl(self, name=accessible_name(own_label))
        sizer.Add(own, 0, wx.EXPAND | wx.ALL, 8)
        self._fields.append(_Field(question, choices, own))

    @staticmethod
    def _keep_one_checked(event: wx.CommandEvent) -> None:
        """A question with a single answer: the line just checked is the only one that stays."""
        box = event.GetEventObject()
        if not isinstance(box, wx.CheckListBox):
            return
        index = event.GetInt()
        if box.IsChecked(index):
            for other in box.GetCheckedItems():
                if other != index:
                    box.Check(other, False)

    @staticmethod
    def _first_control(field: _Field) -> wx.Window:
        return field.choices if field.choices is not None else field.own

    def _unanswered(self) -> _Field | None:
        return next((field for field in self._fields if not field.answer()), None)

    def _on_button(self, event: wx.CommandEvent) -> None:
        identifier = event.GetId()
        if identifier == wx.ID_OK:
            missing = self._unanswered()
            if missing is not None:
                wx.MessageBox(_("Answer every question first."), _("Claude asks you"), wx.OK, self)
                self._first_control(missing).SetFocus()
                return
        if identifier in (wx.ID_OK, wx.ID_NO):
            self._answer = identifier
            self.EndModal(identifier)
        else:
            event.Skip()


def _option_line(label: str, description: str) -> str:
    return (
        _("{label}: {description}").format(label=label, description=description)
        if description
        else label
    )


def _rows(lines: list[str]) -> int:
    return min(len(lines), _MAX_ROWS) + 1
