# Accessibility

Accessibility is a requirement, verified manually with NVDA and JAWS at each milestone (not
verified yet for the current interface).

The general rules (keyboard only, accessible names, initial focus, label before its control, no
unexpected focus change, native controls first, no colour alone, greyed rather than hidden,
information in the text of a line) are in `working-rules.md`, section "Accessible interfaces". What
follows is specific to WxClaude. The accessible name of a control is derived from its label
(`core/labels.py`), except for the few controls whose name is shorter or different (the
explanation field of the permission question, the shortcut list, the unnamed read-only fields).

- Where the focus and the caret go in every case (a dialog closes, the conversation is loaded,
  refreshed or searched, an answer ends...) is in `focus.md`.
- Announcements are grouped in categories (progress of Claude, step in progress, end of an answer, question of
  permission, answer to a permission, movement to a heading, no more heading, search, refresh) and
  the user chooses a destination per category in Preferences > Screen reader: none, a message
  (a UI Automation notification raised by a hidden one-pixel window, written in the status bar too),
  the line concerned, or a sound (Message.wav for the end of an answer, Permission.wav for a question of
  permission; two WAV files in `wxclaude/sounds`). The status bar is only written for a message:
  some screen readers read its changes by themselves, which would say what the user turned off.
  The list of the announcements and their categories is `Announce` in `core/announcements.py`.
  Fixed announcements (no conversation in the workspace) are always a message. What the user asked
  for by an action (open a workspace, new conversation, resume, rename, copy, export, settings
  saved) is not announced: the interface shows it. A failure of Claude is in the status bar and a
  dialog, which the screen reader reads. No MSAA, no vendor-specific API.
- The permission question puts the focus on the read-only description of the request, so a
  screen reader reads what Claude wants to do and a stray Enter does nothing.
- The lists that show a state (the tools of the Workspace settings) follow the rule of the text of
  a line.
- Shortcuts are shown in the menus and in the labels of the send buttons; their key names are
  English (`Ctrl+Shift+O`) because wx menus need them that way.
