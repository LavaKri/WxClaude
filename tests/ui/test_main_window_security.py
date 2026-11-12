"""Tests of the main window: the offer to approve a folder and the restricted launch."""

import json
from pathlib import Path

import pytest
import wx
from main_window_support import _send, _use_log

from wxclaude.presenters.security_presenter import ApprovalChoice
from wxclaude.ui.main_window import MainWindow
from wxclaude.ui.security_view import WxSecurityView

pytestmark = [pytest.mark.ui, pytest.mark.real_security]


class Offers:
    """Answers the offer to approve a folder, and records what was offered."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, choice: ApprovalChoice) -> None:
        self.offered: list[tuple[Path, bool, list[str]]] = []

        def ask(
            _view: WxSecurityView, folder: Path, used_before: bool, files: list[str]
        ) -> ApprovalChoice:
            self.offered.append((folder, used_before, files))
            return choice

        monkeypatch.setattr(WxSecurityView, "ask_approval", ask)


def open_folder(window: MainWindow, folder: Path) -> None:
    window.open_workspace(folder)
    for _ in range(3):  # the offer waits until the window shows
        wx.Yield()


def test_a_new_folder_is_offered_the_approval_once_it_is_open(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".mcp.json").write_text("{}", encoding="utf-8")
    offers = Offers(monkeypatch, ApprovalChoice.KEEP_RESTRICTED)
    open_folder(window, tmp_path)
    assert offers.offered == [(tmp_path, False, [".mcp.json"])]
    assert window._security.restricted
    assert window.GetStatusBar().GetStatusText(2) == "Folder not trusted: restricted mode."


def test_approving_the_folder_lifts_the_restriction(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    Offers(monkeypatch, ApprovalChoice.APPROVE)
    open_folder(window, tmp_path)
    assert not window._security.restricted
    assert window.GetStatusBar().GetStatusText(2) == "Folder approved: Claude uses its settings."


def test_a_message_in_a_folder_not_approved_is_sent_restricted(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = _use_log(monkeypatch, tmp_path)
    Offers(monkeypatch, ApprovalChoice.KEEP_RESTRICTED)
    open_folder(window, tmp_path)
    window._conversations.start_new("Notes")
    _send(window, "hello")
    arguments = json.loads(log.read_text(encoding="utf-8"))["arguments"]
    assert arguments[arguments.index("--setting-sources") + 1] == "user"
    assert arguments[arguments.index("--permission-mode") + 1] == "manual"


def test_a_message_in_an_approved_folder_is_sent_as_before(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = _use_log(monkeypatch, tmp_path)
    Offers(monkeypatch, ApprovalChoice.APPROVE)
    open_folder(window, tmp_path)
    window._conversations.start_new("Notes")
    _send(window, "hello")
    assert "--setting-sources" not in json.loads(log.read_text(encoding="utf-8"))["arguments"]


def test_the_same_folder_is_not_offered_again_when_it_is_opened_again(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    offers = Offers(monkeypatch, ApprovalChoice.KEEP_RESTRICTED)
    open_folder(window, tmp_path)
    open_folder(window, tmp_path)  # already the current folder: nothing to decide again
    assert len(offers.offered) == 1
