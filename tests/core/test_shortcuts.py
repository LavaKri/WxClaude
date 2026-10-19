import pytest

from wxclaude.core.shortcuts import (
    INTERRUPT_COMMAND,
    NEW_CONVERSATION_COMMAND,
    OPEN_WORKSPACE_COMMAND,
    SEND_ALTERNATIVE_COMMAND,
    SEND_COMMAND,
    ShortcutProblem,
    check_shortcut,
    normalize_shortcut,
)

pytestmark = pytest.mark.unit

DEFAULTS = {
    OPEN_WORKSPACE_COMMAND.id: "Ctrl+O",
    NEW_CONVERSATION_COMMAND.id: "Ctrl+N",
    INTERRUPT_COMMAND.id: "Ctrl+Shift+I",
    SEND_COMMAND.id: "Ctrl+Enter",
    SEND_ALTERNATIVE_COMMAND.id: "Shift+Enter",
}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("ctrl + shift + o", "Ctrl+Shift+O"),
        ("shift+ctrl+o", "Ctrl+Shift+O"),
        ("f2", "F2"),
        ("alt+down", "Alt+Down"),
        ("", ""),
        ("Ctrl+", None),
        ("Ctrl+Ctrl+O", None),
        ("Hyper+O", None),
        ("Ctrl+F13", None),
    ],
)
def test_normalize_shortcut(text: str, expected: str | None) -> None:
    assert normalize_shortcut(text) == expected


def test_a_free_shortcut_is_accepted() -> None:
    assert check_shortcut(INTERRUPT_COMMAND, "Ctrl+K", DEFAULTS).problem is None


def test_no_shortcut_is_accepted() -> None:
    assert check_shortcut(INTERRUPT_COMMAND, "", DEFAULTS).problem is None


def test_a_plain_letter_is_refused() -> None:
    assert check_shortcut(INTERRUPT_COMMAND, "K", DEFAULTS).problem is ShortcutProblem.RESERVED


def test_a_plain_enter_is_refused_because_it_adds_a_line_break() -> None:
    assert check_shortcut(INTERRUPT_COMMAND, "Enter", DEFAULTS).problem is ShortcutProblem.RESERVED


def test_enter_with_a_modifier_is_accepted() -> None:
    assert check_shortcut(INTERRUPT_COMMAND, "Alt+Enter", DEFAULTS).problem is None


def test_the_send_shortcuts_are_known_to_the_conflict_check() -> None:
    check = check_shortcut(INTERRUPT_COMMAND, "Ctrl+Enter", DEFAULTS)
    assert check.problem is ShortcutProblem.TAKEN
    assert check.other == SEND_COMMAND
    assert check_shortcut(INTERRUPT_COMMAND, "Shift+Enter", DEFAULTS).other == (
        SEND_ALTERNATIVE_COMMAND
    )


@pytest.mark.parametrize("key", ["Tab", "Esc", "Insert"])
def test_navigation_keys_are_refused(key: str) -> None:
    check = check_shortcut(INTERRUPT_COMMAND, f"Ctrl+{key}", DEFAULTS)
    assert check.problem in (ShortcutProblem.RESERVED, ShortcutProblem.FIXED)


def test_a_standard_shortcut_is_refused() -> None:
    assert check_shortcut(INTERRUPT_COMMAND, "Ctrl+Q", DEFAULTS).problem is ShortcutProblem.FIXED


def test_a_shortcut_of_another_command_is_refused() -> None:
    check = check_shortcut(INTERRUPT_COMMAND, "Ctrl+N", DEFAULTS)
    assert check.problem is ShortcutProblem.TAKEN
    assert check.other == NEW_CONVERSATION_COMMAND


def test_keeping_its_own_shortcut_is_accepted() -> None:
    assert check_shortcut(INTERRUPT_COMMAND, "Ctrl+Shift+I", DEFAULTS).problem is None
