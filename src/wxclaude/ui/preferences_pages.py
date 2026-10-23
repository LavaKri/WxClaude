"""The pages of the Preferences dialog, one class per topic.

Each page builds its controls from the settings and writes the chosen values back with ``apply``.
A page that can refuse OK says why with ``validate``.
"""

from dataclasses import dataclass
from pathlib import Path

import wx

from wxclaude.core.claude.permission_channel import CHANNEL_KINDS, HOOK, STDIO
from wxclaude.core.config.settings import HOOK_TIMEOUT_MINUTES, SUPPORTED_LANGUAGES, Settings
from wxclaude.core.labels import accessible_name
from wxclaude.core.speech.screen_reader import available_outputs, default_output, output_named
from wxclaude.i18n import N_, _
from wxclaude.presenters.announcements_presenter import AnnouncementsPresenter, sorted_categories
from wxclaude.ui.agent_panel import AgentPanel, permission_levels_lines
from wxclaude.ui.fields import read_only_field

# Names of the languages, each in its own language (never translated).
_LANGUAGE_NAMES = {"fr": "Français", "en": "English"}
# Names of the ways Claude's permission questions reach WxClaude (message ids).
_CHANNEL_NAMES = {STDIO: N_("Stdio protocol"), HOOK: N_("HTTP hook")}


@dataclass(frozen=True, slots=True)
class PageProblem:
    """Why a page refuses OK: the message to show and the control to give the focus to."""

    message: str
    control: wx.Window


class PreferencesPage(wx.Panel):
    """What the dialog needs of a page: it applies its values and may refuse OK."""

    def apply(self, settings: Settings) -> None:
        """Store the values chosen in the page into ``settings``."""
        raise NotImplementedError

    def validate(self) -> PageProblem | None:
        """The problem that stops OK, None when the page is fine."""
        return None


class GeneralPage(PreferencesPage):
    """The language and what happens at startup."""

    def __init__(self, parent: wx.Window, settings: Settings) -> None:
        super().__init__(parent)
        # The label is created right before its control so that screen readers pair them.
        text = _("&Language")
        label = wx.StaticText(self, label=text)
        self.language = wx.Choice(
            self,
            choices=[_LANGUAGE_NAMES[code] for code in SUPPORTED_LANGUAGES],
            name=accessible_name(text),
        )
        self.language.SetSelection(SUPPORTED_LANGUAGES.index(settings.language))
        note = wx.StaticText(self, label=_("The language change applies at the next start."))
        self.reopen_last = wx.CheckBox(self, label=_("At startup, &open the last workspace"))
        self.reopen_last.SetValue(settings.reopen_last)
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        row.Add(self.language, 0)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(row, 0, wx.ALL, 6)
        sizer.Add(note, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
        sizer.Add(self.reopen_last, 0, wx.ALL, 6)
        self.SetSizer(sizer)

    def apply(self, settings: Settings) -> None:
        settings.language = SUPPORTED_LANGUAGES[self.language.GetSelection()]
        settings.reopen_last = self.reopen_last.GetValue()


class ClaudePage(PreferencesPage):
    """Where the claude program is (found in the PATH, or chosen by hand) and how it asks."""

    def __init__(self, parent: wx.Window, settings: Settings) -> None:
        super().__init__(parent)
        self.auto_search = wx.CheckBox(self, label=_("&Automatic search for claude-p"))
        self.auto_search.SetValue(settings.claude_auto_search)
        path_text = _("&Path of claude-p")
        path_label = wx.StaticText(self, label=path_text)
        self.path = wx.TextCtrl(self, value=settings.claude_path, name=accessible_name(path_text))
        self.browse = wx.Button(self, label=_("&Select…"))
        self.auto_search.Bind(wx.EVT_CHECKBOX, lambda _event: self._update_path())
        self.browse.Bind(wx.EVT_BUTTON, lambda _event: self._on_browse())
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(self.path, 1, wx.EXPAND | wx.RIGHT, 6)
        row.Add(self.browse, 0)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.auto_search, 0, wx.ALL, 8)
        sizer.Add(path_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        sizer.Add(row, 0, wx.EXPAND | wx.ALL, 8)
        self._add_channel_controls(sizer, settings)
        self.SetSizer(sizer)
        self._update_path()
        self._update_minutes()

    def _add_channel_controls(self, sizer: wx.BoxSizer, settings: Settings) -> None:
        """The type of interface with Claude Code (how its permission questions reach WxClaude)."""
        channel_text = _("Interface &type")
        channel_label = wx.StaticText(self, label=channel_text)
        self.channel = wx.Choice(
            self,
            choices=[_(_CHANNEL_NAMES[kind]) for kind in CHANNEL_KINDS],
            name=accessible_name(channel_text),
        )
        self.channel.SetSelection(CHANNEL_KINDS.index(settings.permission_channel))
        self.channel.Bind(wx.EVT_CHOICE, lambda _event: self._update_minutes())
        minutes_text = _("&Wait for your answer, in minutes (HTTP hook)")
        minutes_label = wx.StaticText(self, label=minutes_text)
        self.minutes = wx.SpinCtrl(
            self,
            min=HOOK_TIMEOUT_MINUTES.start,
            max=HOOK_TIMEOUT_MINUTES.stop - 1,
            initial=settings.hook_timeout_minutes,
            name=accessible_name(minutes_text),
        )
        sizer.Add(channel_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        sizer.Add(self.channel, 0, wx.ALL, 8)
        sizer.Add(minutes_label, 0, wx.LEFT | wx.RIGHT, 8)
        sizer.Add(self.minutes, 0, wx.ALL, 8)

    def _update_path(self) -> None:
        """The path is only used (and editable) without the automatic search."""
        manual = not self.auto_search.GetValue()
        self.path.Enable(manual)
        self.browse.Enable(manual)

    def _update_minutes(self) -> None:
        """The waiting time only exists with the HTTP hook."""
        self.minutes.Enable(CHANNEL_KINDS[self.channel.GetSelection()] == HOOK)

    def _on_browse(self) -> None:
        current = Path(self.path.GetValue())
        with wx.FileDialog(
            self,
            _("Select the claude executable"),
            defaultDir=str(current.parent) if current.parent.is_dir() else "",
            wildcard=_("Programs (*.exe;*.cmd;*.bat)|*.exe;*.cmd;*.bat|All files (*.*)|*.*"),
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dialog:
            if dialog.ShowModal() == wx.ID_OK:
                self.path.SetValue(dialog.GetPath())

    def validate(self) -> PageProblem | None:
        """A manual path must be a file."""
        if self.auto_search.GetValue():
            return None
        path = self.path.GetValue().strip()
        if not path:
            return PageProblem(
                _("Give the path of claude-p, or turn the automatic search on."), self.path
            )
        if not Path(path).is_file():
            return PageProblem(_("The file {path} does not exist.").format(path=path), self.path)
        return None

    def apply(self, settings: Settings) -> None:
        settings.claude_auto_search = self.auto_search.GetValue()
        settings.claude_path = self.path.GetValue().strip()
        settings.permission_channel = CHANNEL_KINDS[self.channel.GetSelection()]
        settings.hook_timeout_minutes = self.minutes.GetValue()


class WorkspacePage(PreferencesPage):
    """What concerns the conversations and the files of a workspace."""

    def __init__(self, parent: wx.Window, settings: Settings) -> None:
        super().__init__(parent)
        self.hide_system_messages = wx.CheckBox(self, label=_("&Hide the system messages"))
        self.hide_system_messages.SetValue(settings.hide_system_messages)
        self.local_tools_only = wx.CheckBox(
            self, label=_("Change the tools only in the &local file, which is not versioned")
        )
        self.local_tools_only.SetValue(settings.local_tools_only)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.hide_system_messages, 0, wx.ALL, 6)
        sizer.Add(self.local_tools_only, 0, wx.ALL, 6)
        self.SetSizer(sizer)

    def apply(self, settings: Settings) -> None:
        settings.hide_system_messages = self.hide_system_messages.GetValue()
        settings.local_tools_only = self.local_tools_only.GetValue()


class AgentPage(PreferencesPage):
    """The agent of a new conversation and the alternative agent."""

    def __init__(self, parent: wx.Window, settings: Settings) -> None:
        super().__init__(parent)
        self._agents = [settings.default_agent, settings.alternative_agent]
        self._unset_labels = [None, _("(same as the conversation)")]
        self._agent_index = 0

        agent_text = _("&Agent")
        list_label = wx.StaticText(self, label=agent_text)
        self.agent_list = wx.ListBox(
            self,
            choices=[_("Agent of a new conversation"), _("Alternative agent")],
            name=accessible_name(agent_text),
        )
        self.agent_list.SetMinSize(wx.Size(-1, self.agent_list.GetCharHeight() * 2 + 12))
        self.agent_list.SetSelection(0)
        self.agent_list.Bind(wx.EVT_LISTBOX, self._on_agent_chosen)
        self.agent_panel = AgentPanel(self, self._agents[0], self._unset_labels[0])

        levels_label = wx.StaticText(self, label=_("Implications of the permission &levels"))
        levels = read_only_field(self, 8, wrap=False)
        levels.SetValue(
            "\n".join(permission_levels_lines())
            + "\n\n"
            + _(
                "Cache: when the alternative agent changes the model, the conversation cache is "
                "lost and the next message is slower and costs more."
            )
        )

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(list_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        sizer.Add(self.agent_list, 0, wx.EXPAND | wx.ALL, 8)
        sizer.Add(self.agent_panel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 2)
        sizer.Add(levels_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        sizer.Add(levels, 1, wx.EXPAND | wx.ALL, 8)
        self.SetSizer(sizer)

    def _on_agent_chosen(self, _event: wx.CommandEvent) -> None:
        index = self.agent_list.GetSelection()
        if index < 0 or index == self._agent_index:
            return
        self._agents[self._agent_index] = self.agent_panel.agent
        self._agent_index = index
        self.agent_panel.set_agent(self._agents[index], self._unset_labels[index])

    def apply(self, settings: Settings) -> None:
        self._agents[self._agent_index] = self.agent_panel.agent
        settings.default_agent, settings.alternative_agent = self._agents


class ScreenReaderPage(PreferencesPage):
    """How the announcements are made, and where each category of announcements goes (the
    logic is in ``presenters/announcements_presenter.py``)."""

    def __init__(self, parent: wx.Window, settings: Settings) -> None:
        super().__init__(parent)
        self._outputs = available_outputs()
        announce_text = _("&Announcements")
        label = wx.StaticText(self, label=announce_text)
        self.output_choice = wx.Choice(
            self,
            choices=[_(output.label) for output in self._outputs],
            name=accessible_name(announce_text),
        )
        current = output_named(settings.screen_reader_output) or default_output()
        self.output_choice.SetSelection(self._outputs.index(current))

        list_text = _("Announcement &categories")
        list_label = wx.StaticText(self, label=list_text)
        self.category_list = wx.ListCtrl(
            self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL, name=accessible_name(list_text)
        )
        self.category_list.AppendColumn(_("Category"), width=260)
        self.category_list.AppendColumn(_("Destination"), width=200)
        for category in sorted_categories():
            self.category_list.Append((_(category.label), ""))
        destination_text = _("&Destination of the selected category")
        destination_label = wx.StaticText(self, label=destination_text)
        self.destination_choice = wx.Choice(self, name=accessible_name(destination_text))
        self.default_button = wx.Button(self, label=_("De&fault value"))

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        sizer.Add(self.output_choice, 0, wx.EXPAND | wx.ALL, 8)
        sizer.Add(list_label, 0, wx.LEFT | wx.RIGHT, 8)
        sizer.Add(self.category_list, 1, wx.EXPAND | wx.ALL, 8)
        sizer.Add(destination_label, 0, wx.LEFT | wx.RIGHT, 8)
        sizer.Add(self.destination_choice, 0, wx.EXPAND | wx.ALL, 8)
        sizer.Add(self.default_button, 0, wx.ALL, 8)
        self.SetSizer(sizer)

        self.presenter = AnnouncementsPresenter(self, settings)
        self.category_list.Bind(
            wx.EVT_LIST_ITEM_SELECTED,
            lambda _event: self.presenter.select(self.category_list.GetFirstSelected()),
        )
        self.destination_choice.Bind(
            wx.EVT_CHOICE,
            lambda _event: self.presenter.choose(self.destination_choice.GetSelection()),
        )
        self.default_button.Bind(wx.EVT_BUTTON, lambda _event: self.presenter.restore_default())
        self.category_list.Select(0)

    def show_destinations(self, labels: list[str]) -> None:
        for index, text in enumerate(labels):
            self.category_list.SetItem(index, 1, text)

    def show_choices(self, labels: list[str], selected: int) -> None:
        self.destination_choice.Set(labels)
        self.destination_choice.SetSelection(selected)

    def apply(self, settings: Settings) -> None:
        self.presenter.apply(settings)
        settings.screen_reader_output = self._outputs[self.output_choice.GetSelection()].id
