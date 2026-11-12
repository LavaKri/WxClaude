# Interface

## Main window

- **Conversation**: read-only view of the exchange. It takes the focus only when the user loads, sends or
  refreshes, or searches (`focus.md`); never at the end of an answer. How the
  conversation will be displayed (Markdown, navigation by headings) is in
  `conversation-display.md`. Your prompt appears as soon as it is sent, then each block of text of
  the answer.
- **Prompt**: multi-line field. Enter adds a line break; the send shortcuts are configurable
  (default Ctrl+Enter to send, Shift+Enter to send with the alternative agent). Its context menu
  (right click, Applications key, Shift+F10) has *Cut*, *Copy* and *Paste* (greyed when they do not
  apply), then *Modify the agent…*, the same as in the Conversation menu, with its current shortcut
  shown; the field itself is plain text.
- Buttons: *Send*, *Send with the alternative agent* (their labels show the current shortcuts) and
  *Interrupt Claude* (active only while Claude is answering; it also stops the programs Claude
  started). While Claude answers, Send is greyed; the prompt field stays usable.
- **Claude Code not found**: once the window is up, if `claude` cannot be started (not in the PATH, or
  the file chosen in Preferences > Claude does not exist) a message says "Claude Code was not found on this
  computer. Install it, or give its path in File > Preferences > Claude." with the buttons *Open the
  Preferences* (on the Claude page) and *Close* (the default). It is said once per launch. The message
  field of the status bar then says "Claude Code not found" instead of "Ready", until it is found: the
  check runs again when the Preferences are closed with OK, and the "Ready" line comes back. The send
  buttons are not greyed, on purpose: the interface does not become empty, and the error comes with the
  message that is sent.
- **Claude Code not logged in**: when `claude` is found, `claude auth status` is asked in a thread (the window is
  not held; `core/claude/status.py`, `read_login`) at the start and when the Preferences are closed with OK. If
  it says it is not logged in, the status bar says "Not logged in to Claude Code" instead of "Ready", and,
  at the start only, a message says so with the buttons *Sign in…* (opens the dialog of *Tools > Sign in to
  Claude…*) and *Close* (the default). When the sign-in dialog is closed the state is asked again and the
  "Ready" line comes back if it worked. An answer that cannot be read says nothing. Nothing is asked when
  the default agent uses another provider than Claude (it has its own key).
- Status bar, three fields: the position of the caret among your prompts (`Message 3 of 8`), the
  step Claude works on (`Step 2 of 5: Build the module`; empty when there is none and while the
  window waits for a prompt), then the last announcement. Progress ("Claude is thinking", "Claude
  uses the tool Read", "Claude is answering", "Permission denied for the tool Bash"), the steps, the
  end of a turn ("Claude has answered", "Claude was interrupted") and the other announcements go
  where the Announcements page of the Preferences says, per category. The announcements that name who answers (thinking, tool, answer,
  interruption, failure, permission and plan questions) say the name of the provider of the agent of
  the message ("DeepSeek is thinking", "DeepSeek uses the tool Read"); Claude for the built-in one. A failure ("Claude could not
  answer: ...") is written in the status bar and opens a dialog with the details; the prompt is
  kept when Claude cannot be started. No field of the status bar holds more than 200 characters: a
  longer text is cut and ends with `…` (`STATUS_TEXT_LIMIT` in `ui/feedback.py`).
- **Step**: when Claude puts a task of its list in progress (`TaskUpdate` with the status
  `in_progress`, seen with the real CLI), the step is the place of that task in the task files of the
  conversation (`core/claude/tasks.py`). It is announced (category "Step in progress", instead of "Claude
  uses the tool TaskUpdate") and kept in the second status field until the end of the turn. A task
  that is not in the files gives the normal progress.
- Help menu: *WxClaude help* (F1), *Statistics…*, *Announcement history…*, *Open the log folder* (the folder
  that holds `wxclaude.log` and `wxclaude-crash.log`, in the file explorer), *About*.
- Error boxes: two buttons, *Close* (the default one: Enter and Escape) and *Copy the details*, which puts the
  text of the error and `WxClaude <version>` on the clipboard and says *Details copied.* (nothing of the log is
  copied). The text of an error is also in the announcement history.
- Window title: `<conversation> - <workspace> - WxClaude`, the parts that exist. With the remote
  control on (`--remote`, `remote.md`) it starts with `Remote enabled`.

## Menus

**File**: Open workspace (Ctrl+O), Open from Claude projects, Export the conversation, Recent
(name, then where it is), Preferences, Quit (Ctrl+Q); Preferences and Quit are the last two.

**Conversation**: New conversation (Ctrl+N), Resume a conversation (Ctrl+Shift+O), Refresh the
conversation (F5, reads the session file again; the focus goes to the conversation, the caret to
the last prompt), Rename (the CLI renames the session), New conversation branch (see "Branch and delete"),
Delete the conversation (see "Branch and delete"), Interrupt Claude (Ctrl+Shift+I), Modify the agent
(Ctrl+Shift+A), the submenu **Display** (two check items, both on by default and kept in the settings:
*Remove the Markdown formatting* and *Summary of the tools under the answers*, see the conversation
display) and the submenu **Search** (see below).

**Tools**: Task list (Ctrl+T, as in the CLI), Plan (no shortcut), Usage gauge (Ctrl+Shift+U), Sign
in to Claude (no shortcut; needs nothing, not even a workspace), Open the workspace folder (in the
file explorer; needs a workspace), Workspace settings (Alt+Enter; needs a workspace).

The context menu of the conversation (tools used, table, links, copy) is in
`conversation-display.md`, with the usage gauge and the statistics.

**Help**: WxClaude help (F1), Statistics (the spending and the statistics of the workspace; needs a
workspace; no shortcut), About.

## Sign in

*Tools > Sign in to Claude…* (`ui/login_dialog.py`, `presenters/login_presenter.py`,
`core/claude/auth.py`) signs in to Claude Code without a terminal, for the program chosen in the
Preferences. Only the subscription sign-in exists (`claude auth login --claudeai`); signing out and
the SSO and Console sign-ins are not offered.

- Fields, in the order of the Tab key: the read-only *State of Claude Code* (the focus when the dialog
  opens, so a screen reader reads it; same text as the *Claude state* button of the Preferences);
  *E-mail address (optional, not remembered)*, passed to the sign-in page with `--email` when it is
  filled in and never stored; the read-only *Sign-in progress*; the read-only *Address of the
  sign-in page*. Buttons: *Sign in* (the default one), *Copy the address* (active once the CLI has
  printed the address), *Cancel the sign-in* (active while it runs), *Close*.
- *Sign in* starts the command with no console and its input closed. The CLI opens the browser by
  itself; the user finishes in the page (e-mail, code sent by e-mail, or the account already signed in
  there, then *Authorize*). No code is typed in WxClaude: the browser comes back to a port the CLI
  listens on. The command must stay alive until then (`claude-cli.md`, "State and sign-in").
- While it runs, only *Cancel the sign-in* and *Close* work and the focus is on the progress
  ("Finish the sign-in in the browser. Waiting for it to end."). Closing the dialog (Escape, Close)
  stops the command first.
- When it ends, the state is read again. If `auth status` says logged in, a message says
  "You are signed in to Claude Code." and the focus is back on the state; if the command ended well but
  the state does not say so, or if it failed, an error shows what the command printed. A
  cancellation is said in the progress field, where the focus goes, without a message box.
- The question of the working folder that the interactive `claude` asks is not asked by this
  command (see `claude-cli.md`) and is not handled here.
- An expired session during a conversation ("Failed to authenticate: OAuth session expired and could
  not be refreshed") is left in the conversation as any other answer; the dialog is opened by hand.

## Task list

*Tools > Task list…* shows the tasks Claude wrote for the current conversation, read from
`<config>/tasks/<conversation id>/*.json` (read only; `CLAUDE_CONFIG_DIR` is honoured). A list, one
task per line in number order: number, subject, state (*pending*, *in progress*, *completed*) and,
when it still waits for tasks that are not completed, `blocked by 3 4`; for example `2, Build, pending,
blocked by 1`. A read-only field below gives the description of the selected task. A file that is not
a readable task is named on the last line of the list. Without any task the list says so. The
dialog shows what the folder holds when it opens; it is not refreshed while it is open.

## Plan

*Tools > Plan…* shows the plans Claude wrote in the current conversation (in the mode *Plan only
(plan)*), to read them; there is nothing to approve here. It needs a conversation, like the task
list, and is never greyed for lack of a plan: without any, the list says "No plan in this
conversation yet.". A list, one plan per line (the name of its file, `<config>/plans/<name>.md`;
`, file missing, text from the session` when the file is gone), the last one selected; a read-only
field below gives the text of the selected plan. The plans are the `Write` calls of the session file
to the plans folder, so it is the same with the stdio protocol and with the HTTP hook
(`claude-cli.md`, "Permission channels"); the text is read from the file, which Claude may have
edited since. The dialog shows what exists when it opens.

**Help**: WxClaude help (F1), About. The help page is one plain HTML file per language
(`src/wxclaude/help/fr.html`, `en.html`, package data; no CSS, no script) that F1 opens as it is in
the default browser; a language without a page falls back on English, and a missing page is
reported. The text is written in Markdown in `MakeHelp/` (`Aide.md` for French, `Help.md` for
English, with the same headings: a test checks it) and
`MakeHelp/make_help.py` turns it into the HTML page: `.venv\Scripts\python.exe MakeHelp\make_help.py
[source.md] [language]` (defaults: `Aide.md`, `fr`; for English `MakeHelp\make_help.py
MakeHelp\Help.md en`), to run again after every edit and once per language. A test fails when a page
of the package is not the conversion of its text. The text only describes what exists and was tested, names no shortcut, and is updated with
the features.

## Permissions

When Claude wants to run a tool that the permission mode of the agent does not allow, a dialog asks
(the status bar and the announcements say "Claude asks permission for the tool ..."):

- a read-only field describes the request (tool, what it is for, the path, the arguments); it has
  the initial focus, so a screen reader reads it and a stray Enter does nothing;
- a field for the explanation sent to Claude if the user denies;
- *Allow*, *Always allow this* (only when the CLI proposes a rule to remember) and *Deny*. Esc or
  closing the dialog is a denial. The answer is announced ("Permission granted / refused for the
  tool ...").

**A plan.** In the mode *Plan only (plan)* with the stdio protocol, Claude submits its plan by asking to
leave the mode (the tool `ExitPlanMode`, whose input holds `plan` and `planFilePath`). The dialog is
titled "Claude proposes a plan" and announced "Claude proposes a plan." (category *Question of
permission*). The read-only field starts with one line that says how to answer ("Allow approves it; Deny
asks for changes (explain below)"), then the text of the plan as Claude wrote it, then the other fields
(the file of the plan). *Allow* approves the plan; *Deny*, with an explanation, asks for changes, and
Claude is told the explanation. The answers are announced like any permission ("Permission granted /
refused for the tool ExitPlanMode."). A request without a text of plan is shown as an ordinary request.
The hook channel has no such request (`claude-cli.md`).

*Always allow this* writes an *allow* rule (for example `Bash(touch x)` or `Edit`) in the personal
settings file of the workspace, `.claude/settings.local.json`, as the CLI itself does: Claude does
not ask about it again, in this message or in the next ones (and neither does the CLI in a terminal).
If the file cannot be read (invalid JSON) it is left as it is and an error says so. A tool that was
denied without a question (a *deny* rule, or the `dontAsk` mode) is only shown as progress.

With the HTTP hook channel (Preferences, Claude), the CLI stops waiting after the waiting time
and denies the tool: if the dialog is still open it is closed, and "The question about the tool ...
expired: Claude denied the tool." is announced. A tool refused by the user's own answer is announced
once ("Permission refused ...", not "Permission denied ..." as well). With this channel the first line of
the request field says until when the CLI waits: "Without an answer by 13:59 (10 min), Claude denies
the tool." (the time of the question plus the waiting time; no such line with the stdio channel).

The structured questions of Claude (`AskUserQuestion`, stdio channel only) are read by
`core/claude/questions.py` and answered by `ClaudeRunner.answer_questions` (the labels chosen for
each question, several joined with ", "). Their dialog (`ui/question_dialog.py`, "Claude asks you") has,
for each question, a label made of its header and its text, the list of its choices (`label: description`) as check boxes (Space checks, which the screen reader says; with a single answer allowed, checking a line unchecks the others) and a text field "Your own answer, if none of the choices
fits", which replaces the choice when it is filled. Nothing is chosen at first, the first list has the
initial focus. *Send* needs an answer to every question (else a message and the focus on the first one
left), *Deny* and Esc refuse (Claude is told the user denied the action). It is announced ("Claude has
questions for you.", category *Question of permission*) and the sending of the answers too ("Your answers
were sent to Claude.", category *Answer to a permission*). Questions that cannot be read are asked as an
ordinary request.

## Workspace settings

*Tools > Workspace settings...* (Alt+Enter, configurable) edits what Claude Code keeps in the `.claude`
folder of the workspace, and the alternative agent of the workspace.
It is a dialog with four tabs: **Tools** (the permission rules), **Environment variables** (the `env`
key of the same files), **Security** (the trusted folder and the watched files) and **Alternative
agent**. When it opens, the keyboard focus is on the first tab, and the watched files of an approved
folder are checked (see "Trusted folders" below). The tab **Alternative agent** has the four fields of
the Agent dialog (*Provider*, *Model*, *Effort*, *Permission mode*; no access keys, and no entry
"same as ..."): the alternative agent is always complete and holds for every conversation of the
workspace. A new workspace gets the values of the alternative agent of the Preferences when it is
opened for the first time, and a field that the Preferences leave on "same as the conversation" gets the
value of the agent of a new conversation. After that the Preferences no longer change it: only the user
does, in this tab. OK remembers the choice in the file of the workspace (`settings.md`); Cancel changes
nothing. The tab **Tools**:

- **Target file** (list): *Settings* (`.claude/settings.json`, shared and versioned, the default)
  or *SettingsLocal* (`.claude/settings.local.json`, personal). With the preference "Change the
  tools only in the local file, which is not versioned" only *SettingsLocal* is proposed, so a
  developer who shares the project with others using the CLI never modifies the shared file. A
  read-only field says which file will be modified and whether it is versioned, and that the
  general file (`~/.claude/settings.json`) is only read.
- **Tools** (list): the tools Claude knows (the file `src/wxclaude/data/tools.txt` and the tools
  that the files name). One line per tool: its name, then the pieces of information that have a
  value, separated by commas: the approval it has in the target file (*Allow*, *Ask*, *Deny*), the
  approval that prevails and the file it comes from when it differs ("Deny by general"), and
  "with rules" when rules with a specifier exist (not evaluated). Example:
  `Bash Allow, Deny by general, with rules`. A tool with nothing to say shows only its name.
  The files are *general*, *Settings* and *SettingsLocal*; the prevailing approval is *Deny*, then
  *Ask*, then *Allow*, whatever the file.
- Buttons **Deny**, **Ask**, **Allow**: give the selected tool one rule without specifier in the target
  file, replacing the ones it had there. Greyed when the file cannot be modified.
- **Rules of the target file** (list): every rule, "Deny, Bash(git *)", sorted by tool then by
  approval, and **Remove** (this is also how a tool goes back to "no rule").
- **Rule to add**, **Approval of the rule** (list) and **Add the rule**: any rule as typed. Rules are
  not checked and may contradict each other.
- OK writes the files that changed (atomically, the other keys of a file are kept, a file that
  cannot be read is never overwritten); Cancel writes nothing. The rules apply to the messages sent
  afterwards.

The tab **Environment variables**:

- **Target file** (list), as in the tab Tools; with the preference only *SettingsLocal* is proposed, and
  changing *Settings* (versioned) asks first, once per target.
- **Variables** (list): the variables of `data/env_vars.txt` and those the target file holds without
  describing them, sorted by name. One line per variable: its name, then what has a value, separated by
  commas: `not set`, `enabled`, `set to 60000` (`value set` for a name that looks like a credential: a
  secret is never shown), `sensitive` (a credential, or a setting that redirects the traffic such as a proxy
  or an address) and `ignored in project files` (a variable the CLI only takes from the shell, the user or
  the managed settings). The variables that choose the provider are not listed.
- Buttons **Enable** / **Disable** (a flag: enabled is the value `1`, disabled takes the variable out of
  the file), **Set the value…** and **Remove**, greyed when they do not apply.
- **Explanation** (read-only field): what the selected variable does, from the file `env_vars.txt` (one
  language); a variable that is not described says so.
- The changes are kept in memory and written by OK, like the tab Tools.

The tab **Security** (what is decided here applies at once, OK is not needed):

- **Trusted folder** (check box). Checking it asks for a confirmation, then the files as they are become
  the approved reference; unchecking it restricts the folder (the reference is kept).
- **Limit of turns per message** (number, 0 = no limit, kept in the file of the workspace). It is given to
  the CLI as `--max-turns`; it is here and not in the Tools tab because it is not a setting of Claude Code.
  When the CLI stops for it (`error_max_turns`), the error dialog says the limit was reached.
- **Watched files** (list with a check box per file): `.claude/settings.json`, `.claude/settings.local.json`,
  `.mcp.json`, the files of `.claude/agents`, `.claude/skills` and `.claude/commands`, and those the user
  added. One line per file: its path, its state (`unchanged`, `changed`, `added`, `removed`, `absent`) and
  `not watched` when its check box is clear. Buttons **Accept the change** (the selected file), **Add a
  file…** (a file of the workspace) and **Remove from the list** (only a file the user added).
- **Explanation** (read-only field): what the approved and the restricted folder mean and what to be careful
  about.

## Trusted folders

A folder is *approved* or *restricted* (`security.md`). In a restricted folder the CLI ignores the hooks, the
settings and the servers of the project, Claude cannot act without permission (the modes `plan` and
`dontAsk` are kept, the others become `manual`) and it can still read the project.

- **When a workspace opens**, once the window shows, a folder that was never answered gets the dialog
  *Approve this folder?*: what the folder is (new, or used before), the watched files it holds, and two
  buttons, *Approve the folder* and *Keep restricted* (the default). The question is asked once; the tab
  Security approves later. Afterwards a restricted folder is only announced ("Folder not trusted:
  restricted mode.", category *Trust of the folder*, written in the status bar).
- **A watched file of an approved folder changed** (when the folder opens, when the Workspace settings
  open, or when a write is refused because the file changed from outside): the dialog *A watched file
  changed* lists the files and, under the list, the differences of the selected one with the approved copy
  (a secret shows only as another hash, a new file as added lines). Buttons *Accept the changes* and
  *Restrict the folder*; Close decides nothing (the change is announced and asked again next time). A
  restricted folder is not alerted.
- A write of the settings files (the tab Tools, the tab Environment variables, "always allow") is refused
  when its file changed from outside since it was approved; nothing is written, the alert above opens and
  the error "The settings could not be saved." is shown.

## Search

Submenu *Search* of the Conversation menu: *Find…* (Ctrl+F), *Find next* (F3), *Find
previous* (Shift+F3); all need a conversation. They look in the text of the conversation view (what
is displayed, titles included).

- *Find…* opens a dialog: the term (the previous one is proposed and selected), *Match case*,
  *Whole words only*. An empty term is refused. OK searches forward from the caret.
- *Find next* / *Find previous* repeat the search of the last term in either direction; without a
  previous term they open the dialog. The search starts after the selection (before it when going
  backwards), so repeating it walks through the occurrences. It does not wrap around.
- An occurrence is selected and the view gets the focus (`focus.md`); the whole line that holds it is announced
  (status bar and UI Automation). When there is no more occurrence in the direction asked,
  "No next occurrence of ..." or "No previous occurrence of ..." goes where the category
  "Unsuccessful search" says: nothing, a message (default; said to the screen reader, not written
  in the status bar) or a message dialog. The status bar keeps the messages of the progress of
  Claude, the answers to a permission and the refresh (`accessibility.md`).
- **Gauge alerts**: the 5-hour gauge and the weekly gauge (`unifiedWindows` of the `rate_limit_event`)
  are announced the first time they reach or pass an alert threshold (90 % for the 5 hours; 25 %,
  50 % and 75 % for the week: the early-warning thresholds of Claude Code itself, see
  `claude-cli.md`; `ALERT_THRESHOLDS` in `core/claude/usage.py`), by the category "Gauge alerts" (nothing or a message, default message):
  "Alert: the 5-hour gauge is at 91 %." and "Alert: the weekly gauge is at 76 %.". A gauge is
  announced again only after it went back under that threshold, so the windows that start again
  at 0 % (every 5 hours, every week) are announced again in an application left open. An alert is
  only said, never written in the status bar (it would stay there until the next message).
- **Silent retries of the CLI**: when the server returns an error that the CLI retries (overloaded, 429,
  5xx: up to ten times with growing waits), each retry is said with its reason: "The server of Claude
  returned an error (overloaded). Retry 2 of 10; you can interrupt." Category "Progress of Claude" (so
  it is also written in the status bar). A refusal of the credentials (401, 403) is not one of these:
  the run is stopped at once and the error box tells why.
- **Compaction**: when the CLI compacts the conversation (`system` / `compact_boundary` in the stream,
  automatic or after `/compact`), WxClaude says "Conversation compacted (automatic): 362766 tokens
  reduced to 76351. Claude may have lost details; consider a new conversation or a branch." Always
  said as a message (not a category: it is information, not progress). Not yet written in the
  conversation itself.
- **A permission mode that was not applied**: the `system` / `init` line gives the mode the CLI really
  uses (`default` for our `manual`). When it is not the one sent for the message, WxClaude says so,
  category "Permission mode not applied" (nothing, a message, default, or a dialog box). With the key
  transmission *Masked* the text says why ("The mode plan was not applied: with the key transmission
  Masked, Claude Code forces the manual mode. Change it in the Preferences, page Providers."), else it
  names both modes. A restricted folder makes the mode manual on purpose (`security.md`): this is
  compared with the mode sent, so it is not reported again.
- **MCP servers that did not start**: the `init` line of the CLI lists its MCP servers with their state
  (`connected`, `pending`, `failed`). A `failed` one is said ("The MCP server ollama did not start:
  its tools are not available."), a `pending` one too, with another text ("...is slow to start: its
  tools may not be available for this message."): a slow server is not ready for the first message
  and starts again at each message, as each message is a new process (`claude-cli.md`). Each is said
  once for each state, not at each message, and said again if it worked in between. Category "MCP
  servers" (nothing, a message, default, or a dialog box). Other states, and the servers that work,
  say nothing. Not written in the conversation: this is about one start, not about the exchange.
- **History of the announcements** (*Help > Announcement history…*, no shortcut, needs nothing): so that
  an announcement that was missed, or sent to nothing, is not lost. A `TextDialog` (read-only text and a
  Close button) with one line per announcement, the oldest first and the newest last, the caret on the
  last line: `10:20 Ready`. It holds the last 500 lines, in memory (a new start begins empty), for the
  whole session: a change of conversation does not clear it, it adds a blank line and a line
  `Workspace: WxClaude` when a workspace is opened, or `Conversation: Fix` when another conversation
  becomes the current one (not for a refresh, a rename or the same workspace again). Every announcement
  is kept, even when its category is set to *No announcement* and whatever its destination (message,
  sound, dialog box), except the movements in the conversation and the searches (they answer at once
  to a key and are many). The texts of the message boxes (errors, warnings, information) are kept too,
  on one line; the questions (Yes / No) are not. The same text is never merged with the previous one.
  The time is `hh:mm`, 24 hours. An empty history says "No announcement yet.".
- When Claude has answered (or was interrupted) the status bar goes back to "Ready", followed by
  the 5-hour gauge when it is known: "Ready, gauge at 50 %". The weekly gauge is added once it is at
  or over its last alert threshold (75 %): "Ready, gauge at 50 %, week at 76 %"; under it, the usage
  dialog has it. This line is state, not an announcement: it does not depend on the destination of
  the gauge alerts. After a failure the status bar keeps the error.
- **Reading the gauges** (`claude-cli.md`, "Gauges without a message"): at startup, when a first
  workspace opens, and by a timer of one minute when a gauge is unknown or past its reset time,
  WxClaude reads them with `/usage`, without sending a message. It is handled like a message: both
  send buttons and the *Usage gauge* item of the Tools menu are greyed, the message field of the
  status bar says "Refreshing the gauges", and *Interrupt Claude* stays available to stop it. At the
  end, success or not, the window is back to waiting for a prompt ("Ready, gauge at 50 %"). Nothing
  is shown as an error and the only thing said is a gauge alert when a threshold is reached; nothing
  is read without a workspace.

Resume lists the conversations of the workspace, the one with the most recent message first.

## What is available when

| State | Available |
|---|---|
| No workspace (first start, option off, folder gone) | Open workspace, Open from Claude projects, Recent, Quit, Preferences, About. Everything else is greyed, including the prompt and the send buttons. |
| Workspace, no conversation | The above and New conversation. |
| Conversation | Everything, except Interrupt Claude which needs an answer in progress. Refresh, Rename, Branch, Delete, the Search items, Modify the agent and Task list need a conversation; Open the workspace folder and Workspace settings only need a workspace. |

Opening another workspace closes the current conversation.

## Branch and delete

**New conversation branch** asks for a name (current name followed by `branch x`) and makes the
branch the current conversation: the text on screen stays, the focus goes to the last prompt
(`focus.md`, rule B). Its first message copies the history of the conversation into a Claude Code
session of its own (`--fork-session`); the original is left as it is. A conversation without any
message cannot be branched (an error says there is nothing to copy). Leaving a branch before its
first message forgets it, as a new conversation never sent.

**Delete the conversation** asks `Move the conversation "<name>" to the Recycle Bin?` (Yes, No; No
by default), then moves to the Recycle Bin of Windows what Claude Code keeps of it (its transcript,
the folder beside it, its file history, its tasks). The announcement `Conversation "<name>" moved
to the Recycle Bin.` follows, and the most recent conversation of the workspace is selected, else
the workspace is left without any. It is refused while Claude answers. If a file cannot be moved,
an error says so and the conversation stays.

## Names of conversations

A dialog with one field, the proposal selected, opens for: New conversation (`Conversation x`,
the number grows only when the name is accepted), Rename (current name) and New conversation
branch (current name followed by `branch x`). An empty name is refused.

The name of a conversation is the name of its Claude Code session, so Claude Code (`--resume`, the
picker, `/rename`) and WxClaude show the same one:

- A conversation that has no session yet (no message sent) only has its name in WxClaude; the first
  message gives it to the CLI with `--name` (`claude-cli.md`, "Name of a session").
- Rename on a conversation that has a session runs `/rename <name>` through the CLI
  (`ClaudeRunner.rename_session`, instant and free); if it fails the name does not change and the
  error is shown. It is refused while Claude is answering. Refresh takes a name given elsewhere.
- A session without a name is shown by the start of its identifier. WxClaude no longer stores
  names (`settings.md`).

## Agents

An agent bundles a provider, a model (those of the provider; for Claude, from the least to the most
powerful), an effort and a permission mode, all four always chosen: the CLI is never left to pick one from its own settings. Two agents
are defined in Preferences > Agent: the one of a new conversation and the alternative agent, used by the
"send with the alternative agent" command; its fields can be left on "same as the conversation". The
Workspace settings (tab *Alternative agent*) hold the alternative agent of each workspace, which is the
one used there: the Preferences only give its first value to a new workspace.
Changing the provider (the first list of the Agent dialog and of the Agent page) takes the first model of
the new provider unless the current model is one of its models, and, like changing the model, loses the
prompt cache of the conversation (measured with the CLI); changing the effort or the permission mode
does not. The alternative agent can leave the provider on "same as the conversation"; the models of
Claude are then offered. A provider that was deleted shows as Claude. See `providers.md`.

## Preferences

- **General**: language (applies at the next start); at startup, open the last workspace; *Maximize
  the window at startup* (checked by default; applies at the next start).
- **Claude** (after General): *Automatic search for claude-p* (checked by default: `claude` is looked
  for in the PATH); *Path of claude-p* and *Select…* (file dialog), both greyed while the search is
  automatic. OK is refused, with the focus on the path, if the search is off and the path is empty
  or not a file. *Interface type* (a drop-down list, *Stdio protocol* by default or *HTTP hook*): how
  Claude's permission questions reach WxClaude, applied to the next message (the conversation can
  switch at any time). *Wait for your answer, in minutes (HTTP hook)* (1 to 10, 10 by default) is
  greyed with the stdio protocol. What the HTTP hook cannot do is in `claude-cli.md`,
  "Permission channels". The button *Claude state* asks the program chosen on the page (not yet saved)
  and shows the answer in the read-only field *State of Claude Code* below it, where the focus goes
  so that a screen reader reads it: found or not (and why), the path, the version and the connection
  ("logged in (claude.ai, pro)", "not logged in" or unknown). It runs `claude --version` and `claude
  auth status` (`core/claude/status.py`); the address and the organization that `auth status` also
  gives are not read. The window waits for the answer (20 seconds at most). Signing in has a dialog
  of its own, *Tools > Sign in to Claude…* (see "Sign in" above); the Preferences have no button for it.
- **Providers** (after Claude): the list of the providers, one line each (`Claude, built in`; `DeepSeek,
  https://api.deepseek.com/anthropic, key saved`), the buttons *Add…*, *Edit…* and *Delete…* (asks first, No
  by default; the key goes with it). Whether a key is saved is said by the line of the list only. Claude
  is always first and cannot be changed or deleted. What is done to the providers is saved at once (Cancel
  does not undo it). Under the buttons, the list *API key transmission* (*Masked*, the default, *Shared*
  or *Relayed*) and the read-only field *Explanation* that tells what the chosen one means: *Masked*
  hides the key from the commands that Claude runs but the CLI then forces the manual permission mode;
  *Shared* leaves the key readable by them and applies every mode; *Relayed* keeps the key in WxClaude,
  which forwards the requests with it, so the key is hidden and every mode applies (`providers.md`,
  "How the key reaches the CLI" and "The relay"). OK stores this choice (the setting
  `key_transmission`). The form of a provider: name, address
  (`http://` or `https://`), where the key comes from (saved by
  WxClaude, or none for a local server), a button *Add a key* / *Remove the key* (by whether the provider
  has one; greyed for a provider that needs none; the key is typed in a password field with a check box
  *Show the key*, kept encrypted when the form is accepted, never shown again; Cancel changes nothing),
  a list box *Variable* (a classic list, one line selected, all six lines visible) and a field *Value*: the list holds one line per variable, written `Small model =
  deepseek-v4-flash`: the four models (*Small*, *Medium*, *Large* and *Largest model*; an empty one takes
  the weakest model given, one is enough; the first three also stand for `haiku`, `sonnet` and `opus`),
  then the variables of the CLI the provider can set (`API_TIMEOUT_MS`, `CLAUDE_CODE_MAX_CONTEXT_TOKENS`,
  `CLAUDE_CODE_AUTO_COMPACT_WINDOW`, `CLAUDE_CODE_MAX_OUTPUT_TOKENS`: a closed list, whole numbers; empty means not set: `providers.md`). The field *Value* holds the value of
  the selected line (its name says which: *Value of API_TIMEOUT_MS*) and a read-only field *Explanation*
  says what the line does. The line follows the value when the field is left, not at each key, so a screen
  reader does not read the list again at each one. The check box *Send the
  effort*, then, at the bottom, two lists *Models retrieval* (*No method*, *V1*) and *Gauge retrieval*
  (*No method*, *DeepSeek*), and right under them the button *Check the data retrieved* (greyed while a key
  is needed and missing, or when both lists say *No method*): it asks the server with the two methods
  chosen and shows the models and the credit in a read-only text (`providers.md`, "The data of a
  server"). The same form serves to add and to change a provider. A form that is not valid is asked again with what
  was typed, the key included.
- **Workspace**: hide the system messages (checked by default): the noise the CLI writes in
  a session, such as the answer "No response requested." or the summary of a compaction, is not displayed; change the tools only
  in the local file, which is not versioned (unchecked by default, see Workspace settings).
- **Agent**: list of the two agents, their fields (the provider first), the check box *Refuse the requests of Claude to
  leave the Plan mode* (checked by default) and the read-only field that gives the implication of
  each permission level, the cache notice and, last, a paragraph that explains the check box (a
  screen reader reads a field, not a note under a check box). Checked, two requests of Claude are
  refused at once, with no dialog: its plan (the request to leave the mode Plan, see the permission
  dialog) and, while the agent of the message is in the mode Plan, its structured questions (the
  dialog of the questions is still used in the other modes). Claude is told to stay in the mode Plan
  and to present its plan and ask its questions in its answer, and the status bar and the
  announcement (category *permission answer*) say "Claude asked to leave the Plan mode: refused, as
  set in the Preferences." or "Claude's questions were refused in the Plan mode, as set in the
  Preferences." The plan can still be read with *Tools > Plan…*, and the user leaves the mode by
  changing the agent. Unchecked, both are asked in their dialogs as before. Only the stdio protocol
  sends these requests.
- **Shortcuts**: list of commands, field to press the new shortcut, restore the default, no
  shortcut. A shortcut is refused if it is invalid, reserved, standard or already used.
- **Announcements**: how announcements are sent (none, UI Automation on Windows); the list of the
  announcement categories with their destination, a list to change the destination of the selected
  category and a button to restore its default (changes apply with OK). Destinations: *No
  announcement*, *Message*, *Read the line* (movement in the conversation, headings), *Dialog box* (unsuccessful search), *Message.wav*,
  *Permission.wav*. Defaults: Message, except
  the end of an answer (Message.wav) and the question of permission (Permission.wav). See `accessibility.md`.
