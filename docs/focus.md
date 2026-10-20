# Keyboard focus and caret

Where the keyboard focus and the caret go is decided by four general rules. The particular cases
that differ are listed after them. Every new feature follows a rule, or adds its case here.

## General rules

**A. A dialog closes: the focus goes back where it was.**
Every dialog and message of the application (Options, Find, names, agent, task list, export,
"no more occurrence", errors, warnings, and later the permission questions) is shown through
`MainWindow._modal`: it remembers the focused control and puts the focus back once the dialog is
destroyed, unless the action that followed has deliberately moved the focus inside the window
(rule B or C). It applies to a dialog that opens by itself (an error at the end of an answer) as
much as to one the user opened.

**B. The user loads, sends or refreshes the conversation: the focus goes to the conversation view,
the caret to the start of the last prompt of the user** (`ConversationView.focus_last_prompt`).
This is the case of:

- starting the application;
- opening a workspace (from the menu, from the recent list, from the Claude projects), which
  selects its remembered conversation, else the most recent one;
- resuming a conversation;
- refreshing the conversation (F5);
- sending a prompt (the prompt just sent is then the last one).

The last prompt is the last *visible* one: a hidden system message ("continue") is skipped. A
conversation without any prompt puts the caret at the start of the text.

**C. The user moves inside the text: the focus is on the conversation view, on the target.**
Search (Ctrl+F, F3, Shift+F3) selects the occurrence and announces its line; the title keys (`T`,
`1` to `6`) move the caret, in a view that already has the focus.

**D. An update the user did not ask for moves neither the focus nor the caret.**
The end of an answer (the session file is read again and the view rebuilt if it differs) leaves the
focus where it is, so the user can type the next prompt; changing the option "Hide the system
messages" rebuilds the text and keeps the caret on its message.

## Particular cases

| Case | Focus | Why |
|---|---|---|
| New conversation (Ctrl+N) | the prompt field | there is nothing to read; the only action is to type |
| Workspace without any conversation | the (empty) conversation view, with the announcement "No conversation in this workspace." | the prompt and the buttons are greyed, so they cannot take the focus; the message tells what to do |
| Start with a last workspace that has no conversation | same as above | |
| A conversation that cannot be read | unchanged (rule A, an error dialog) | nothing was loaded |
| Second launch of the application | unchanged in the first window, which is brought to the front | |

## Still to define with the features

- Delete a conversation: the most recent one is selected (rule B); if there is none, the case
  "workspace without any conversation".
- New conversation branch: rule B once the branch is a real fork of the session.
- Permission questions: a dialog during an answer (rule A).
