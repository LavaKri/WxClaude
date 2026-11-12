"""The wx side of trusting a folder: the view of ``presenters/security_presenter.py``."""

from pathlib import Path

import wx

from wxclaude.core.list_spec import ListSpec
from wxclaude.core.speech.announcements import Announce
from wxclaude.i18n import _
from wxclaude.presenters.security_presenter import AlertChoice, ApprovalChoice
from wxclaude.ui.feedback import Feedback
from wxclaude.ui.list_dialog import ListDialog


class WxSecurityView:
    """The offer to approve a folder and the alert about changed files; ``parent`` is the window
    of the dialogs."""

    def __init__(self, parent: wx.Window, feedback: Feedback) -> None:
        self._parent = parent
        self._feedback = feedback

    def ask_approval(self, folder: Path, used_before: bool, files: list[str]) -> ApprovalChoice:
        """Approve, or keep restricted (the button that has the focus)."""
        intro = (
            _("You have worked in {folder} before, and WxClaude has not checked it yet.")
            if used_before
            else _("{folder} is a folder WxClaude has not seen before.")
        ).format(folder=folder)
        found = (
            _("It holds these files that can change what Claude does:\n{files}").format(
                files="\n".join(files)
            )
            if files
            else _("It holds no file that can change what Claude does.")
        )
        message = _(
            "{intro}\n\n{found}\n\nUntil you approve it, Claude runs in restricted mode: the "
            "hooks, the settings and the servers of the project are ignored, and Claude cannot "
            "act without your permission. You can still ask Claude to read the project, then "
            "approve it later in Tools > Workspace settings, tab Security."
        ).format(intro=intro, found=found)
        style = wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION
        with wx.MessageDialog(self._parent, message, _("Approve this folder?"), style) as dialog:
            dialog.SetYesNoLabels(_("&Approve the folder"), _("&Keep restricted"))
            result = self._feedback.modal(dialog)
        return ApprovalChoice.APPROVE if result == wx.ID_YES else ApprovalChoice.KEEP_RESTRICTED

    def show_alert(self, spec: ListSpec) -> AlertChoice | None:
        """The changed files and their differences; Close (or Escape) decides nothing."""
        actions = [
            (wx.ID_YES, _("&Accept the changes")),
            (wx.ID_NO, _("&Restrict the folder")),
        ]
        with ListDialog(self._parent, spec, actions) as dialog:
            result = self._feedback.modal(dialog)
        if result == wx.ID_YES:
            return AlertChoice.ACCEPT
        if result == wx.ID_NO:
            return AlertChoice.RESTRICT
        return None

    def say(self, announce: Announce, **values: object) -> None:
        self._feedback.say(announce, **values)

    def show_error(self, message: str) -> None:
        self._feedback.show_error(message)
