"""Dialog showing the task list of the current conversation."""

import wx

from wxclaude.core.claude.tasks import TaskList
from wxclaude.core.list_spec import ListSpec
from wxclaude.i18n import _
from wxclaude.ui.list_dialog import ListDialog


class TasksDialog(ListDialog):
    """The tasks of Claude, one per line (number, subject, state, what blocks it), and the
    description of the selected one. A task file that could not be read is said in the list."""

    def __init__(self, parent: wx.Window, tasks: TaskList) -> None:
        lines = [tasks.line(task) for task in tasks.tasks]
        descriptions = [task.description for task in tasks.tasks]
        if tasks.unreadable:
            lines.append(
                _("Unreadable task files: {names}").format(names=", ".join(tasks.unreadable))
            )
            descriptions.append("")
        if not lines:
            lines, descriptions = [_("No task in this conversation yet.")], [""]
        super().__init__(
            parent,
            ListSpec(
                _("Task list"),
                list_label=_("&Tasks"),
                lines=lines,
                details=descriptions,
                details_label=_("&Description"),
            ),
        )
