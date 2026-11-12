"""The tab "Environment variables" of the Workspace settings: the ``env`` key of a settings file.

The changes are made in memory on the settings files of the workspace and written when the dialog
is accepted, as for the tab Tools (``ToolSettings.save``, through the guard of the watched files).
"""

from collections.abc import Callable
from typing import Protocol

from wxclaude.core.claude.claude_settings import (
    SettingsFile,
    Source,
    ToolSettings,
    source_label,
)
from wxclaude.core.claude.env_vars import (
    FLAG_ON,
    EnvRow,
    env_rows,
    remove_env,
    set_env,
)
from wxclaude.core.errors import ClaudeSettingsError
from wxclaude.core.security.sensitive import is_credential_name
from wxclaude.i18n import _

TARGETS = (Source.SETTINGS, Source.LOCAL)


class EnvVarsView(Protocol):
    """What the presenter asks of the tab."""

    def show_targets(self, labels: list[str], selected: int) -> None:
        """The files that can be edited, and the one selected."""
        ...

    def show_rows(self, lines: list[str], selected: int) -> None:
        """The variables, one line each, and the one selected (-1: none)."""
        ...

    def show_explanation(self, text: str) -> None:
        """The read-only text that explains the selected variable."""
        ...

    def show_actions(self, toggle: str, can_toggle: bool, can_set: bool, can_remove: bool) -> None:
        """The buttons: the label of the first (*Enable* or *Disable*) and which can be used."""
        ...

    def ask_value(self, name: str, current: str) -> str | None:
        """Ask for the value of ``name`` (``current`` proposed). None: cancelled."""
        ...

    def confirm_versioned(self) -> bool:
        """Warn that the file is shared and versioned, and ask whether to change it anyway."""
        ...

    def show_error(self, message: str) -> None:
        """Tell the user that something failed."""
        ...


class EnvVarsPresenter:
    """The variables of the target file being edited."""

    def __init__(self, view: EnvVarsView, settings: ToolSettings, *, local_only: bool) -> None:
        self._view = view
        self._settings = settings
        self._targets = [Source.LOCAL] if local_only else list(TARGETS)
        self._target = self._targets[-1] if local_only else Source.SETTINGS
        self._rows: list[EnvRow] = []
        self._selected = -1
        self._versioned_confirmed = False
        view.show_targets(
            [source_label(s) for s in self._targets], self._targets.index(self._target)
        )
        self._refresh()

    @property
    def target(self) -> Source:
        """The file being edited."""
        return self._target

    def select_target(self, index: int) -> None:
        """The file at ``index`` of the targets is edited."""
        if 0 <= index < len(self._targets):
            self._target = self._targets[index]
            self._selected = -1
            self._versioned_confirmed = False
            self._refresh()

    def select(self, index: int) -> None:
        """The line at ``index`` is selected (-1: none)."""
        self._selected = index
        self._show_selection()

    def toggle(self) -> None:
        """Switch the selected flag on (the value 1) or off (the variable leaves the file)."""
        row = self._row()
        if row is None or not row.is_flag:
            return
        if row.value == FLAG_ON:
            self._change(lambda: remove_env(self._file(), row.name))
        else:
            self._change(lambda: set_env(self._file(), row.name, FLAG_ON))

    def set_value(self) -> None:
        """Ask for the value of the selected variable and keep it."""
        row = self._row()
        if row is None:
            return
        value = self._view.ask_value(row.name, row.value or "")
        if value is not None:
            self._change(lambda: set_env(self._file(), row.name, value))

    def remove(self) -> None:
        """Take the selected variable out of the file."""
        row = self._row()
        if row is not None and row.value is not None:
            self._change(lambda: remove_env(self._file(), row.name))

    # -- inside ---------------------------------------------------------------------------

    def _file(self) -> SettingsFile:
        return self._settings.files[self._target]

    def _row(self) -> EnvRow | None:
        return self._rows[self._selected] if 0 <= self._selected < len(self._rows) else None

    def _change(self, action: Callable[[], None]) -> None:
        if self._target is Source.SETTINGS and not self._versioned_confirmed:
            if not self._view.confirm_versioned():
                return
            self._versioned_confirmed = True
        try:
            action()
        except ClaudeSettingsError as error:
            self._view.show_error(str(error))
            return
        self._refresh()

    def _refresh(self) -> None:
        current = self._row()
        name = current.name if current else ""
        self._rows = env_rows(self._file())
        self._selected = next((i for i, r in enumerate(self._rows) if r.name == name), -1)
        self._view.show_rows([self._line(row) for row in self._rows], self._selected)
        self._show_selection()

    def _line(self, row: EnvRow) -> str:
        parts = [row.name, self._state(row)]
        if row.sensitive:
            parts.append(_("sensitive"))
        if row.info is not None and row.info.project_ignored:
            parts.append(_("ignored in project files"))
        return ", ".join(parts)

    def _state(self, row: EnvRow) -> str:
        if row.value is None:
            return _("not set")
        if row.is_flag and row.value == FLAG_ON:
            return _("enabled")
        if is_credential_name(row.name):
            return _("value set")  # a secret is never shown
        return _("set to {value}").format(value=row.value)

    def _show_selection(self) -> None:
        row = self._row()
        if row is None:
            self._view.show_explanation("")
            self._view.show_actions(_("Enable"), False, False, False)
            return
        text = row.explanation
        if row.info is not None and row.info.project_ignored:
            text += " " + _("A project file does not apply this variable.")
        self._view.show_explanation(text)
        toggle = _("Disable") if row.value == FLAG_ON else _("Enable")
        self._view.show_actions(toggle, row.is_flag, True, row.value is not None)
