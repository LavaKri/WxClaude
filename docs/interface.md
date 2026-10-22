# Interface

## Main window

- **Conversation**: read-only view of the exchange. It takes the focus only when the user loads, sends or
  refreshes, or searches (`focus.md`); never at the end of an answer. How the
  conversation will be displayed (Markdown, navigation by headings) is in
  `conversation-display.md`. Your prompt appears as soon as it is sent, then each block of text of
  the answer.
- **Prompt**: multi-line field. Enter adds a line break; the send shortcuts are configurable
  (default Ctrl+Enter to send, Shift+Enter to send with the alternative agent).
- Buttons: *Send*, *Send with the alternative agent* (their labels show the current shortcuts) and
  *Interrupt Claude* (active only while Claude is answering; it also stops the programs Claude
  started). While Claude answers, Send is greyed; the prompt field stays usable.
- Status bar, two fields: the position of the caret among your prompts (`Message 3 of 8`), then the
  last announcement. Progress ("Claude is thinking", "Claude uses the tool Read",
  "Claude is answering", "Permission denied for the tool Bash") is announced if the option is on,
  the end of a turn ("Claude has answered", "Claude was interrupted", "Claude could not answer:
  ...") always is. A failure also opens a dialog with the details; the prompt is kept when Claude
  cannot be started.
- Window title: `<conversation> - <workspace> - WxClaude`, the parts that exist.

## Menus

**File**: Open workspace (Ctrl+O), Open from Claude projects, Export the conversation, Recent
(name, then where it is; just above Quit), Quit (Ctrl+Q).

**Conversation**: New conversation (Ctrl+N), Resume a conversation (Ctrl+Shift+O), Refresh the
conversation (F5, reads the session file again; the focus goes to the conversation, the caret to
the last prompt), Rename, New conversation branch (provisional: a new identifier, the text stays),
Delete (greyed until it is built), Interrupt Claude (Ctrl+Shift+I), Modify the agent, and the
submenu **Search** (see below).

**Tools**: Task list (Ctrl+T, as in the CLI), Claude usage (Ctrl+Shift+U), Open the workspace folder
(in the file explorer; needs a workspace), Workspace settings (needs a workspace), Preferences.

The context menu of the conversation (tools used, table, links, copy) is in
`conversation-display.md`, with the usage dialog.

## Task list

*Tools > Task list…* shows the tasks Claude wrote for the current conversation, read from
`<config>/tasks/<conversation id>/*.json` (read only; `CLAUDE_CONFIG_DIR` is honoured). A list, one
task per line in number order: number, subject, state (*pending*, *in progress*, *completed*) and,
when it still waits for tasks that are not completed, `blocked by 3 4`; for example `2, Build, pending,
blocked by 1`. A read-only field below gives the description of the selected task. A file that is not
a readable task is named on the last line of the list. Without any task the list says so. The
dialog shows what the folder holds when it opens; it is not refreshed while it is open.

**Help**: About.

## Permissions

When Claude wants to run a tool that the permission mode of the agent does not allow, a dialog asks
(the status bar and the announcements say "Claude asks permission for the tool ..."):

- a read-only field describes the request (tool, what it is for, the path, the arguments); it has
  the initial focus, so a screen reader reads it and a stray Enter does nothing;
- a field for the explanation sent to Claude if the user denies;
- *Allow*, *Always allow this* (only when the CLI proposes a rule to remember) and *Deny*. Esc or
  closing the dialog is a denial. The answer is announced ("Permission granted / refused for the
  tool ...").

*Always allow this* writes an *allow* rule (for example `Bash(touch x)` or `Edit`) in the personal
settings file of the workspace, `.claude/settings.local.json`, as the CLI itself does: Claude does
not ask about it again, in this message or in the next ones (and neither does the CLI in a terminal).
If the file cannot be read (invalid JSON) it is left as it is and an error says so. A tool that was
denied without a question (a *deny* rule, or the `dontAsk` mode) is only shown as progress.

With the HTTP hook channel (Preferences, Claude), the CLI stops waiting after the waiting time
and denies the tool: if the dialog is still open it is closed, and "The question about the tool ...
expired: Claude denied the tool." is announced. A tool refused by the user's own answer is announced
once ("Permission refused ...", not "Permission denied ..." as well).

## Workspace settings

*Tools > Workspace settings...* edits the permission rules that Claude Code keeps in the `.claude`
folder of the workspace. It is a dialog with one tab for now, **Tools**:

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
  (status bar and UI Automation). When there is no more occurrence in the direction asked, a
  message dialog says so ("No next occurrence of ...", "No previous occurrence of ...").

Resume lists the conversations of the workspace, the one with the most recent message first.

## What is available when

| State | Available |
|---|---|
| No workspace (first start, option off, folder gone) | Open workspace, Open from Claude projects, Recent, Quit, Preferences, About. Everything else is greyed, including the prompt and the send buttons. |
| Workspace, no conversation | The above and New conversation. |
| Conversation | Everything, except Interrupt Claude which needs an answer in progress. Refresh, Rename, Branch, the Search items, Modify the agent and Task list need a conversation; Open the workspace folder and Workspace settings only need a workspace. |

Opening another workspace closes the current conversation.

## Names of conversations

A dialog with one field, the proposal selected, opens for: New conversation (`Conversation x`,
the number grows only when the name is accepted), Rename (current name) and New conversation
branch (current name followed by `branch x`). An empty name is refused.

## Agents

An agent bundles a model (listed from the least to the most powerful), an effort and a permission
mode, all three always chosen: the CLI is never left to pick one from its own settings. Two agents
are defined in Preferences > Agent: the one of a new conversation and the alternative agent, used by the
"send with the alternative agent" command; its fields can be left on "same as the conversation".
Changing the model loses the prompt cache of the conversation (measured with the CLI); changing the
effort or the permission mode does not.

## Preferences

- **General**: language (applies at the next start); at startup, open the last workspace.
- **Claude** (after General): *Automatic search for claude-p* (checked by default: `claude` is looked
  for in the PATH); *Path of claude-p* and *Select…* (file dialog), both greyed while the search is
  automatic. OK is refused, with the focus on the path, if the search is off and the path is empty
  or not a file. *Interface type* (a drop-down list, *Stdio protocol* by default or *HTTP hook*): how
  Claude's permission questions reach WxClaude, applied to the next message (the conversation can
  switch at any time). *Wait for your answer, in minutes (HTTP hook)* (1 to 10, 10 by default) is
  greyed with the stdio protocol. What the HTTP hook cannot do is in `claude-cli.md`,
  "Permission channels" (a help page will say it to the user, see `open-questions.md`).
- **Workspace**: hide the system messages (checked by default): the noise the CLI writes in
  a session, such as the answer "No response requested.", is not displayed; change the tools only
  in the local file, which is not versioned (unchecked by default, see Workspace settings).
- **Agent**: list of the two agents, their fields, the implication of each permission level and the
  cache notice.
- **Shortcuts**: list of commands, field to press the new shortcut, restore the default, no
  shortcut. A shortcut is refused if it is invalid, reserved, standard or already used.
- **Screen reader**: how announcements are sent (none, UI Automation on Windows); announce the
  progress of Claude (checked by default; the end of a turn, errors and permission answers are
  always announced).
