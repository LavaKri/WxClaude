# Changelog

Every version of WxClaude and what changed in it, newest first. The rules for versions are in
`docs/versions.md`. Format: one line per change, no jargon.

## 0.2.0 (2026-10-26)

The application works from end to end. The number 0.1.0 was never released: what it was meant to
hold is part of this version.

- Send messages to Claude Code (`claude -p`) and read the answers in a read-only conversation view
  with headings; the session file of the CLI is the history.
- Workspaces, conversations that carry the name of their Claude Code session (`--name`, `/rename`),
  resume, refresh, search.
- Permission questions answered in a dialog, with two channels (stdio protocol, HTTP hook), "always
  allow" rules written in `.claude/settings.local.json`, and an editor of the permission rules of
  the workspace.
- Agents (model, effort, permission mode) with an alternative agent for a second send button.
- Statistics of the whole workspace at the end of the usage dialog: messages, conversations,
  tokens, time of work, cost and split by model, deleted conversations included. The numbers
  of tokens are written short above a million (1,5 million, 12 milliards).
- A line under each answer that used tools sums them up (commands run, files modified and
  read, other tools, failures); an item of the Display submenu shows or hides it.
- Keys of the conversation: `H` for headings (`1` to `6` as before), `T` for tables, `L` for lists
  and `I` for the items of the list the caret is in, with Shift to go backwards; two announcement
  categories for them. `Space` on a line of a table shows the table.
- A button *Claude state* in the Claude page of the Preferences, with a read-only field: whether Claude
  Code is found, its path, its version and whether it is logged in.
- *Tools > Sign in to Claude…*: a dialog that signs in to Claude Code with `claude auth login` without a
  terminal. The browser opens by itself; the dialog waits, says the result, can be cancelled, shows
  the address of the page to copy, and takes an optional e-mail address for the page (not remembered).
- A check box *Maximize the window at startup* in the General page of the Preferences, checked by
  default.
- A check box *Refuse the requests of Claude to leave the Plan mode* in the Agent page of the
  Preferences, checked by default: in the mode Plan, its request to leave the mode and its structured
  questions are refused for you, with a message to Claude to present its plan and ask its questions
  in its answer.
- A message at the start when Claude Code is not found, with a way to open the Preferences, and a status
  bar that says so instead of "Ready".
- The keys `K` and `Shift+K` of the conversation go from link to link and say the text and the address
  of the link (same announcement categories as the other jumps).
- A submenu Display in the Conversation menu, with the summary of the tools and a new item, on by default,
  that removes the marks of bold and italic (`**`, `*`) from the conversation so the screen reader does not
  read them; the export keeps them.
- The plan that Claude submits in the mode Plan is shown as such: its own title, a line that says how to
  answer, then its text, announced "Claude proposes a plan.".
- A context menu on the prompt field: Cut, Copy, Paste, Modify the agent.
- The fields of the status bar are cut at 200 characters.
- Shortcut `Ctrl+Shift+A` for *Modify the agent*, configurable in the Preferences like the others.
- The summary the CLI writes when it compacts a conversation is hidden with the other system messages.
- A dialog for the structured questions of Claude: the choices of each question in a list of check
  boxes (one answer at most when the question allows only one), an answer of one's own, Send and Deny.
- With the HTTP hook channel, the permission question says until when Claude waits for the answer.
- The table of a message is shown one column at a time: Left and Right change the column, and a field gives the cell.
- A log file of the errors, written with the other data files of WxClaude.
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
- The two sounds of the announcements are new: made by synthesis by `packaging/make_sounds.py`, so
  they belong to the project (the Windows sounds used before could not be published).
- Published under the GNU General Public License version 3 only (`LICENSE`), with a `README.md`
  and a `CONTRIBUTING.md` (no contributions are accepted). The packaged folder and zip carry
  `LICENSE` and `THIRD-PARTY-NOTICES.txt`, the licenses of the software they contain.
- Not yet checked by hand with NVDA and JAWS.
