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
- Announcements (workspace opened, new conversation, rename, branch, export, agent updated) go to
  the status bar and, depending on Options > Screen reader, to a UI Automation notification raised
  by a hidden one-pixel window. No MSAA, no vendor-specific API.
- Shortcuts are shown in the menus and in the labels of the send buttons; their key names are
  English (`Ctrl+Shift+O`) because wx menus need them that way.
