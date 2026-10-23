# Changelog

Every version of WxClaude and what changed in it, newest first. The rules for versions are in
`docs/versions.md`. Format: one line per change, no jargon.

## 0.1.0 (not released yet)

First version: the application works from end to end.

- Send messages to Claude Code (`claude -p`) and read the answers in a read-only conversation view
  with headings; the session file of the CLI is the history.
- Workspaces, conversations that carry the name of their Claude Code session (`--name`, `/rename`),
  resume, refresh, search.
- Permission questions answered in a dialog, with two channels (stdio protocol, HTTP hook), "always
  allow" rules written in `.claude/settings.local.json`, and an editor of the permission rules of
  the workspace.
- Agents (model, effort, permission mode) with an alternative agent for a second send button.
- Details of a message in dialogs (tools, tables, links, copy of a message or of an exchange), task
  list, plans and usage of the subscription.
- Announcements in categories with a destination each (nothing, message, line, dialog box, two
  sounds), a step field in the status bar, and gauge alerts at the thresholds of Claude Code. The
  "Ready" line of the status bar gives the 5-hour gauge, and the week from 75 %.
- The gauges are read with `/usage` at startup and when they are out of date, without sending a
  message; meanwhile the send buttons and the usage item are greyed.
- Branch of a conversation: its first message copies the history into a new Claude Code
  session, the original is left as it is. Delete a conversation: what Claude Code keeps of it
  goes to the Recycle Bin, after a confirmation.
- French and English interface, configurable shortcuts, help page opened in the browser.
- Not yet checked by hand with NVDA and JAWS.
