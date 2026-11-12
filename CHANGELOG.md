# Changelog

Every version of WxClaude and what changed in it, newest first. The rules for versions are in
`docs/versions.md`. Format: one or two lines per change, starting with `Added:`, `Modified:` or
`Fixed:`, no jargon.

## 0.4.0 (2026-11-12)

- Added: the option `--remote`, which lets another program give WxClaude a few commands through the
  named pipe `\\.\pipe\WxClaude-<user>`: stop the message being answered, send a message, read the last
  answer with its status and its tokens, read the history of the announcements, and ask which version
  of WxClaude and of the protocol answers (`docs/remote.md`).
  It is off unless the option is given, and the window title then starts with *Remote enabled*
  (*Remote activé*). A message sent this way goes through the usual permission questions and does not
  touch the prompt or the focus.
- Modified: the announcement history says what a tool works on: `Claude uses the tool Edit on build.bat.`,
  `... Bash to run git.`, `... Grep on def main.` (the name of the file without its folder, only the program
  of a command, the host of a web address). What is said to the screen reader and shown in the status bar does
  not change (`Claude uses the tool Edit.`).
- Added: when Claude Code is not logged in, the status bar says "Not logged in to Claude Code" instead of
  "Ready", and at the start a message offers to sign in (*Sign in…*, or *Close*). It is asked in the
  background, so the window does not wait; it is asked again when the Preferences or the sign-in dialog are
  closed. It is not asked when the default agent uses another provider than Claude.
- Added: *Help > Open the log folder*, which shows the folder of `wxclaude.log` in the file explorer.
- Added: the error boxes have a button *Copy the details* (the text of the error and the version of WxClaude
  go to the clipboard) next to *Close*, which stays the default one (Enter, Escape).
- Fixed: the announcement history (and every list that opens on its last line) puts the caret back on the
  last line once the dialog is up, in case Windows selected the whole text when the field took the focus.
- Added: the folder `tools` of the packaged application holds `WxClaude-remote.bat` (starts WxClaude with
  `--remote`), the description of the remote control (`remote.md`) and `WxClaude-debug.bat`, moved there.

## 0.3.1 (2026-11-11)

- Modified: the help is corrected, translated again to English, and holds the agents of a workspace, the
  announcement history and the delegation of tasks to a local AI.
- Added: *Help > Announcement history…*, a read-only list of the last 500 announcements with their time
  (`10:20 Ready`), the newest last. It keeps what was said even when a category is set to *No
  announcement*, and the messages of the error and information boxes; the movements in the conversation
  and the searches are left out. A change of workspace or conversation adds a blank line and a line
  that names it; it does not clear the history.
- Added: an MCP server that did not start, or is slow to start, is said once (new category *MCP servers*),
  so that the user knows why its tools are missing.
- Added: when the server returns an error that the CLI retries (overloaded, 429, 5xx), each retry is
  said with its reason and its number ("Retry 2 of 10; you can interrupt"), in the status bar too.
- Added: when Claude compacts the conversation, it is said, with the sizes before and after and the advice
  to consider a new conversation or a branch (a fixed announcement).
- Added: when the CLI runs a message in another permission mode than the one sent, it is said (new
  category *Permission mode not applied*); with the key transmission *Masked* the text says that Claude
  Code forces the manual mode. This also shows that `auto` is not applied.
- Added: tab *Alternative agent* in the Workspace settings, with the fields of the Agent dialog (provider,
  model, effort, permission mode). Each workspace has its own alternative agent, used by Shift+Enter in
  all its conversations, so a workspace can send with another provider. A new workspace takes the values
  of the alternative agent of the Preferences (a field left on "same as the conversation" takes the value
  of the agent of a new conversation); after that only the user changes it.
- Added: the shortcut Alt+Enter opens the Workspace settings; it is shown in the menu and can be changed.
- Modified: when the Workspace settings open, the keyboard focus is on the first tab instead of the list of tools.
- Added: at the first start (no `providers.json` yet), the providers *DeepSeek* (its key to add) and *Ollama*
  (a local server, no key) are already there; a provider deleted later does not come back.
- Added: a provider can set `API_TIMEOUT_MS`, `CLAUDE_CODE_MAX_CONTEXT_TOKENS`, `CLAUDE_CODE_AUTO_COMPACT_WINDOW`
  and `CLAUDE_CODE_MAX_OUTPUT_TOKENS` (a closed list, whole numbers);
  they are sent to the CLI for this provider only, also in a restricted folder.
- Modified: in the form of a provider, the four fields of the models are replaced by a list *Variable*
  (`Small model = ...`, then the two variables) and a field *Value* for the selected line, with its explanation.
- Fixed: after Alt+Tab the focus no longer jumps to a control it was on long before; a button (such as
  *Interrupt Claude*) or a control that is greyed by then gives the focus to the prompt, or to the conversation.
- Added: field *Limit of turns per message* in the tab *Security* of the Workspace settings (0: no limit);
  when Claude reaches it, a message says so.

## 0.3.0 (2026-11-10)

- Added: page *Providers* in the Preferences (DeepSeek, a local server...): four ranked models and a key
  encrypted with the Windows account, set in the form of the provider; list *Provider* in the agents.
- Added: lists *Models retrieval* and *Gauge retrieval* in the form of a provider, and the button
  *Check the data retrieved*, which shows the models and the credit its server gives.
- Added: list *API key transmission* (*Masked*, *Shared*, *Relayed*) with an explanation; *Relayed* keeps
  the key in WxClaude behind a local relay, so the commands of Claude cannot read it.
- Added: the dialog *Usage gauge* shows the credit left with the providers that have a gauge method
  (DeepSeek).
- Added: item *Statistics* in the Help menu, with the spending and the statistics of the workspace.
- Added: a folder not seen before is offered for approval, and runs in restricted mode until approved.
- Added: dialog that shows the changes of the files that can change what Claude does, to accept or restrict.
- Added: tabs *Environment variables* and *Security* in the Workspace settings.
- Added: settings `relay_idle_minutes` and `relay_timeout_seconds` of the relay, in the file only.
- Modified: *Claude usage* becomes *Usage gauge* (gauges and credits only, a blank line between each).
- Modified: the announcements name the provider of the message ("DeepSeek is thinking").
- Modified: the setting `scrub_credentials` becomes `key_transmission` (the old value is read).
- Fixed: a server that refuses the key (401 or 403) stops the message at once, not after minutes of retries.
- Fixed: the focus returns to its control after Alt+Tab, and the status bar goes back to "Ready" after a
  new or resumed conversation.

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
