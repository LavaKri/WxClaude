# Interface

## Main window

- **Conversation**: read-only view of the exchange. It never takes the focus by itself. How the
  conversation will be displayed (Markdown, navigation by headings) is in
  `conversation-display.md`; for now it only echoes what is sent.
- **Prompt**: multi-line field. Enter adds a line break; the send shortcuts are configurable
  (default Ctrl+Enter to send, Shift+Enter to send with the alternative agent).
- Buttons: *Send*, *Send with the alternative agent* (their labels show the current shortcuts) and
  *Interrupt Claude* (active only while Claude is answering).
- Status bar: the last announcement.
- Window title: `<conversation> - <workspace> - WxClaude`, the parts that exist.

## Menus

**File**: Open workspace (Ctrl+O), Open from Claude projects, Export the conversation, Recent
(name, then where it is; just above Quit), Quit (Ctrl+Q).

**Conversation**: New conversation (Ctrl+N), Resume a conversation (Ctrl+Shift+O), Rename, New
conversation branch, Delete, Interrupt Claude (Ctrl+Shift+I), Modify the agent.

**Tools**: Task list (Ctrl+T, as in the CLI), Options.

**Help**: About.

Resume and Delete need the history of sessions and are always greyed for now.

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
mode; a field left unset is not passed to the CLI, which then uses its own settings. Two agents are
defined in Options > Agent: the one of a new conversation and the alternative agent, used by the
"send with the alternative agent" command; its unset fields come from the conversation's agent.
Changing the model loses the prompt cache of the conversation (measured with the CLI); changing the
effort or the permission mode does not.

## Options

- **General**: language (applies at the next start); at startup, open the last workspace.
- **Agent**: list of the two agents, their fields, the implication of each permission level and the
  cache notice.
- **Shortcuts**: list of commands, field to press the new shortcut, restore the default, no
  shortcut. A shortcut is refused if it is invalid, reserved, standard or already used.
- **Screen reader**: how announcements are sent (none, UI Automation on Windows).
