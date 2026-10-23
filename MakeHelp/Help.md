# WxClaude help

WxClaude is a desktop interface for the Claude Code command line, used in non-interactive mode (`claude -p`).
It is designed for use with a screen reader and the keyboard alone.
It uses the native controls of Windows.
It is not a terminal.

## Installation and setup

### Claude Code (claude -p)

WxClaude needs the Claude Code program.
Install it by following the [Claude Code documentation](https://code.claude.com/docs/en/overview).

Check the installation in a terminal with `claude --version`.

To use Claude Code, you must sign in:

- in a terminal, run `claude auth login` and follow the instructions.
- Check with `claude auth status`.

### Claude in WxClaude

In the "Claude" tab of the preferences, you will be able to set how the Claude Code program is used.

In particular, the interface type is the way Claude's permission questions reach WxClaude.
It applies to the next message and can be changed at any time.

- **Stdio protocol** (default):
all the permission questions, the structured questions of Claude and the approval of its plans.
- **HTTP hook**:
the permission questions about tools. For this, WxClaude starts a local HTTP server on 127.0.0.1.

With the HTTP hook, a question that is not answered within the waiting time is refused by Claude Code. Set this time (1 to 10 minutes) on the same page.

In the permission mode *Do not ask*, nothing is asked, whatever the type.

## How it works

### Workspaces

A workspace is a working folder. Claude works in it and reads its files.

- File > Open from Claude projects lists the folders already used with Claude Code.
- At startup, the last workspace is reopened. You can turn this off in the Preferences, General page.
- Tools > Workspace settings changes the permission rules of the `.claude` folder. They are shared with Claude Code in a terminal.

### Conversations

A conversation always belongs to a workspace. Opening a workspace loads its remembered conversation, otherwise the most recent one. A conversation is never created automatically.

- Conversation > Resume a conversation lists those of the workspace, the most recent first.
- Conversation > Refresh the conversation reads the session file again.

Conversation > Modify the agent changes the agent of the current conversation.
Changing the model loses the prompt cache of the conversation. Changing the effort or the permission mode does not.

### Agents

An agent is a set of characteristics.
For WxClaude, it is limited to a model, an effort and a permission mode.

Two agents are defined in the Preferences, Agent page:

- the one of new conversations, by default.
It belongs to a conversation and can be changed independently of the others.
- an alternative agent.
The alternative agent has its own send button and it is the same for all workspaces.
It is useful to send prompts easily with a low effort level, for example, without changing the main agent.

Changing the model loses the prompt cache of the conversation. Changing the effort or the permission mode does not.

### Permissions

When Claude wants to use a tool that the permission mode does not allow, a dialog box asks the question. The status bar announces it.

- *Allow* allows the tool this time.
- *Always allow this* writes a rule in `.claude/settings.local.json`, as Claude Code does. This button appears when Claude Code proposes a rule.
- *Deny* refuses. You can type an explanation that is sent to Claude.

Closing the box with Escape is a refusal. The first field describes the request and receives the initial focus.

The workspace settings let you give each tool an allow, ask or deny rule. Deny prevails over ask, and ask over allow.

## User interface

### Conversation area

The conversation area shows the exchange in read-only form.
Your message is a level 1 heading. Claude's answer is a level 2 heading.
Move through it with the heading navigation of your screen reader.

It never takes the focus when an answer arrives.
It takes it when you load, send, refresh or search.

You can search for text in it. The search does not wrap around: at the end, it tells you so.

The context menu depends on the message where the cursor is. It only offers what applies:

- *Show the tools used*: when the answer used tools. A list gives the details of each.
- *Show the table*: when the cursor is in a table. Its rows are read one by one. You can copy the table.
- *Show the links*: when the message contains some. You can open a web or mail link, or copy the address.

### Prompt

The prompt is the field where you write your message to Claude.
It can hold several lines. Its context menu is the one of Windows.
It is greyed out as long as there is no active conversation.

Two buttons send the message: one with the agent of the conversation, the other with the alternative agent.
While Claude answers, sending is greyed out. The field stays usable for typing.

The *Interrupt Claude* button stops the answer and the programs started by Claude.
It is only active during an answer.

### Status bar

The status bar has three zones. It does not take the focus: use the command of your screen reader to read it.

- The position: `Message 3 of 8` gives the message where the cursor is among yours. It is empty if there are none.
- The step: `Step 2 of 5: subject` gives the task of Claude's list that it has just started. It is empty if there is none and when WxClaude waits for your message.
- The message: the last announcement. When WxClaude waits for your message, it says `Ready`, followed by the 5-hour gauge if it is known: `Ready, gauge at 50 %`. The week is added from 75 %: `Ready, gauge at 50 %, week at 76 %`. After a failure, it keeps the error.

### Announcements

WxClaude tells your screen reader what is happening. The announcements are grouped in categories.

In the "Screen reader" tab of the preferences, you choose for each category what is done.
Depending on the category: nothing, a message, reading the line, a dialog box or a sound.
The *Announcements* choice turns the sending to the screen reader off or on.

Errors from Claude always open a dialog box.

#### Gauge alerts

The subscription has two gauges: the 5-hour window and the week.
Each alert is spoken the first time the gauge reaches or passes its threshold.
The thresholds are those of Claude Code: 90 % for the 5 hours, 25, 50 and 75 % for the week.

### Tasks, plans and usage

Three information windows open on request. They show what WxClaude knows when they open.

- The task list gives the tasks that Claude set itself for the conversation: number, subject and state (pending, in progress, completed). A line also says what blocks it. The details of the chosen task are below.
- The plans are those that Claude wrote in the permission mode *Plan only*. They are read-only: there is nothing to approve here.
- The usage shows the gauges of the subscription and their reset. It also gives information about the tokens used.
