# Accessibility

Accessibility is a requirement, verified manually with NVDA and JAWS at each milestone (not
verified yet for the current interface).

- Everything is usable from the keyboard; every control has an accessible name and every dialog a
  defined initial focus.
- A label is created right before its control so that screen readers pair them.
- No unexpected focus change; the conversation view never takes the focus by itself. At startup the
  focus is on the prompt if there is a conversation, otherwise on the conversation view. Loading
  a conversation by itself (startup, workspace change) does not move the focus; the menu item
  "Resume a conversation" puts it on the conversation view, to read the history.
- Native controls first. Read-only fields are multi-line text fields, which the Tab key reaches.
- Information is never given by colour alone.
- Items that cannot be used are greyed rather than hidden or silent.
- Announcements (workspace opened, new conversation, rename, branch, export, agent updated) go to
  the status bar and, depending on Options > Screen reader, to a UI Automation notification raised
  by a hidden one-pixel window. No MSAA, no vendor-specific API.
- Shortcuts are shown in the menus and in the labels of the send buttons; their key names are
  English (`Ctrl+Shift+O`) because wx menus need them that way.
