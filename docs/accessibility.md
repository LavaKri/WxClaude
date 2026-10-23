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
  permission, answer to a permission, movement to a heading, no more heading, search, unsuccessful search, refresh, gauge alerts) and
  the user chooses a destination per category in Preferences > Screen reader (the list is in
  alphabetical order of the labels, accents and case ignored): none, a message
  (a UI Automation notification raised by a hidden one-pixel window, a child of the panel and not of
  the status bar: the screen readers read the children of the status bar with it and added the
  last announcement to what it says, as the name of that element),
  the line concerned, a message dialog (the unsuccessful search only), or a sound (Message.wav for the end of an answer, Permission.wav for a question of
  permission; two WAV files in `wxclaude/sounds`). The status bar is only written for a message of the categories that need it (progress of Claude,
  answer to a permission, refresh, and the fixed announcements); the others are
  only said: step in progress (the step has its own field), question of permission (the dialog
  reads itself), movement to a heading, no more heading, search reached and unsuccessful search (the
  caret and the selection show them), gauge alerts (the "Ready" line shows the gauges). Some screen readers read the changes of the status bar by
  themselves, which would say twice what is already said or what the user turned off.
  The list of the announcements and their categories is `Announce` in `core/speech/announcements.py`.
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
