# Accessibility

Accessibility is a requirement, verified manually with NVDA and JAWS at each milestone (not
verified yet for the current interface).

The general rules (keyboard only, accessible names, initial focus, label before its control, no
unexpected focus change, native controls first, no colour alone, greyed rather than hidden,
information in the text of a line) are in `working-rules.md`, section "Accessible interfaces". What
follows is specific to WxClaude.

- Where the focus and the caret go in every case (a dialog closes, the conversation is loaded,
  refreshed or searched, an answer ends...) is in `focus.md`.
- Announcements (workspace opened, no conversation, new conversation, resume, refresh, rename,
  branch, export, agent updated, the line of a search result, the progress of Claude, permission
  questions and answers, the end of a turn, errors) go to the status bar and, depending on
  Preferences > Screen reader, to a UI Automation notification raised by a hidden one-pixel
  window. The list of the available announcements is `Announce` in `core/announcements.py`. No
  MSAA, no vendor-specific API.
- The permission question puts the focus on the read-only description of the request, so a
  screen reader reads what Claude wants to do and a stray Enter does nothing.
- The lists that show a state (the tools of the Workspace settings) follow the rule of the text of
  a line.
- Shortcuts are shown in the menus and in the labels of the send buttons; their key names are
  English (`Ctrl+Shift+O`) because wx menus need them that way.
