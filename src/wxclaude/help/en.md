# WxClaude help

## General description

WxClaude is a desktop front end for the Claude Code command line, used in non-interactive mode (`claude -p`). It is designed for use with a screen reader and the keyboard alone.

It uses native Windows controls. It is not a terminal.

Each message you send starts one `claude -p` process. The session file written by Claude Code is the history of the conversation. WxClaude never writes it.

The conversation is shown as a read-only Markdown document. Your prompts are level 1 headings and Claude's answers are level 2 headings, so you can move through it with your screen reader's heading navigation.

## Installation

### Claude Code (claude -p)

WxClaude needs the Claude Code command line. Install it by following the [Claude Code documentation](https://code.claude.com/docs/en/overview).

Check the installation in a terminal with `claude --version`.

WxClaude looks for `claude` in the PATH. To use another file, open Tools > Preferences, Claude page, clear *Automatic search* and select the file.

### Authentication

Claude Code uses the login of the Windows user who runs it. Run WxClaude in your own session.

1. In a terminal, run `claude auth login` and follow the instructions.
2. Check with `claude auth status`.

Without a valid login, WxClaude shows the error from Claude Code in the status bar and in a dialog.

### Choosing the interface type

The interface type is the way Claude's permission questions reach WxClaude. Choose it in Tools > Preferences, Claude page. It applies to the next message, and you can change it at any time.

- **Stdio protocol** (default): every permission question, the structured questions of Claude and the approval of its plans.
- **HTTP hook**: the permission questions about tools. WxClaude starts a local HTTP server on 127.0.0.1 for this.

With the HTTP hook, a question you do not answer within the waiting time is denied by Claude Code. Set the waiting time (1 to 10 minutes) on the same page.

In the permission mode *Do not ask*, nothing is asked with either type.

## Usage

### Workspaces

A workspace is a working folder. Claude works in it and reads its files.

- File > Open workspace chooses a folder.
- File > Open from Claude projects lists the folders already used with Claude Code.
- File > Recent lists the last workspaces.
- At startup, the last workspace is reopened. You can turn this off in Preferences, General page.
- Tools > Open the workspace folder shows it in the file explorer.
- Tools > Workspace settings edits the permission rules of the `.claude` folder. They are shared with Claude Code in a terminal.

Without a workspace, most items are greyed. Opening another workspace closes the current conversation.

### Conversations

A conversation always belongs to a workspace. Opening a workspace loads its remembered conversation, otherwise the most recent one. A conversation is never created automatically.

- Conversation > New conversation starts one. You choose its name.
- Conversation > Resume a conversation lists the conversations of the workspace, the most recent first.
- Conversation > Rename changes the name. The name is kept by WxClaude only.
- Conversation > Refresh the conversation reads the session file again.
- File > Export the conversation saves the text to a file.
- Conversation > Search finds text in the conversation.

The main window has the conversation, the prompt field, the send buttons, a button to interrupt Claude and a status bar.

- In the prompt, Enter adds a line break. The send shortcuts are shown on the buttons and can be changed in Preferences, Shortcuts page.
- While Claude answers, Send is greyed. The prompt stays usable.
- Interrupt Claude stops the answer and the programs Claude started.
- The conversation view never takes the focus when an answer arrives. It takes it when you load, send, refresh or search.
- The status bar shows your position among your prompts, then the last announcement.

### Agents

An agent is a model, an effort and a permission mode. All three are always set.

Two agents are defined in Preferences, Agent page: the one used by new conversations and an alternative one. The alternative agent has its own send button. Its fields can stay on *same as the conversation*.

Conversation > Modify the agent changes the agent of the current conversation.

Changing the model loses the prompt cache of the conversation. Changing the effort or the permission mode does not.

### Permissions

When Claude wants to use a tool that the permission mode does not allow, a dialog asks. The status bar announces it.

- *Allow* allows the tool this time.
- *Always allow this* writes a rule in `.claude/settings.local.json`, as Claude Code does. It appears when Claude Code proposes a rule.
- *Deny* refuses. You can type an explanation that is sent to Claude.

Closing the dialog with Escape is a denial. The first field describes the request and has the initial focus.

Workspace settings lets you give each tool an allow, ask or deny rule. Deny prevails over ask, and ask over allow.

### Details of a message

Open the context menu of the conversation on a message to see the tools Claude used, its tables and its links, or to copy the message. Only web and mail addresses are handed to the system.

Preferences, Workspace page, can hide the system messages written by Claude Code.

### Tasks, plans and usage

- Tools > Task list shows the tasks Claude wrote for the conversation.
- Tools > Plan shows the plans Claude wrote in the permission mode *Plan only*. You read them there.
- Tools > Claude usage shows the usage limits and the tokens spent. It is filled from the answers received, so it is empty before the first message.

### Errors

Errors from Claude go to the status bar and to a dialog, never into the conversation text. If Claude cannot be started, your prompt is kept.

Announcements go to the status bar and, through UI Automation, to your screen reader. Preferences, Screen reader page, turns the progress announcements on or off. The end of an answer and errors are always announced.
