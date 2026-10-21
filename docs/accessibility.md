# Accessibility

Accessibility is a requirement, verified manually with NVDA and JAWS at each milestone (not
verified yet for the current interface).

- Everything is usable from the keyboard; every control has an accessible name and every dialog a
  defined initial focus.
- A label is created right before its control so that screen readers pair them.
- No unexpected focus change. Where the focus and the caret go in every case (a dialog closes, the
  conversation is loaded, refreshed or searched, an answer ends...) is in `focus.md`.
- Native controls first. Read-only fields are multi-line text fields, which the Tab key reaches.
- Information is never given by colour alone.
- Items that cannot be used are greyed rather than hidden or silent.
- Announcements (workspace opened, no conversation, new conversation, resume, refresh, rename,
  branch, export, agent updated, the line of a search result, the progress of Claude, permission
  questions and answers, the end of a turn, errors) go to the status bar and, depending on
  Preferences > Screen reader, to a UI Automation notification raised by a hidden one-pixel
  window. The list of the available announcements is `Announce` in `core/announcements.py`. No
  MSAA, no vendor-specific API.
- The permission question puts the focus on the read-only description of the request, so a
  screen reader reads what Claude wants to do and a stray Enter does nothing.
- Lists that show a state (the tools of the Workspace settings) put the information in the text of
  the line, separated by commas, and leave out what has no value; nothing depends on columns.
- Shortcuts are shown in the menus and in the labels of the send buttons; their key names are
  English (`Ctrl+Shift+O`) because wx menus need them that way.
