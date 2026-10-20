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
- Status bar: the last announcement. Progress ("Claude is thinking", "Claude uses the tool Read",
  "Claude is answering", "Permission denied for the tool Bash") is announced if the option is on,
  the end of a turn ("Claude has answered", "Claude was interrupted", "Claude could not answer:
  ...") always is. A failure also opens a dialog with the details; the prompt is kept when Claude
  cannot be started.
- Window title: `<conversation> - <workspace> - WxClaude`, the parts that exist.

## Menus

**File**: Open workspace (Ctrl+O), Open from Claude projects, Export the conversation, Recent
(name, then where it is; just above Quit), Quit (Ctrl+Q).

**Conversation**: New conversation (Ctrl+N), Resume a conversation (Ctrl+Shift+O), Refresh the
conversation (F5, reads the session file again and keeps the caret on its message), Rename, New
conversation branch, Delete, Interrupt Claude (Ctrl+Shift+I), Modify the agent, and the
submenu **Search** (see below).

**Tools**: Task list (Ctrl+T, as in the CLI), Open the workspace folder (in the file explorer;
needs a workspace), Options.

**Help**: About.

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
Delete is always greyed for now.

## What is available when

| State | Available |
|---|---|
| No workspace (first start, option off, folder gone) | Open workspace, Open from Claude projects, Recent, Quit, Options, About. Everything else is greyed, including the prompt and the send buttons. |
| Workspace, no conversation | The above and New conversation. |
| Conversation | Everything, except Interrupt Claude which needs an answer in progress. |

Opening another workspace closes the current conversation.

## Names of conversations

A dialog with one field, the proposal selected, opens for: New conversation (`Conversation x`,
the number grows only when the name is accepted), Rename (current name) and New conversation
branch (current name followed by `branch x`). An empty name is refused.

## Agents

An agent bundles a model (listed from the least to the most powerful), an effort and a permission
mode, all three always chosen: the CLI is never left to pick one from its own settings. Two agents
are defined in Options > Agent: the one of a new conversation and the alternative agent, used by the
"send with the alternative agent" command; its fields can be left on "same as the conversation".
Changing the model loses the prompt cache of the conversation (measured with the CLI); changing the
effort or the permission mode does not.

## Options

- **General**: language (applies at the next start); at startup, open the last workspace.
- **Conversation**: hide the system messages (checked by default): the noise the CLI writes in
  a session, such as the answer "No response requested.", is not displayed.
- **Agent**: list of the two agents, their fields, the implication of each permission level and the
  cache notice.
- **Shortcuts**: list of commands, field to press the new shortcut, restore the default, no
  shortcut. A shortcut is refused if it is invalid, reserved, standard or already used.
- **Screen reader**: how announcements are sent (none, UI Automation on Windows); announce the
  progress of Claude (checked by default; it takes effect once Claude is launched from the
  application).
