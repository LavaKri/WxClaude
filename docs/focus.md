# Keyboard focus and caret

Where the keyboard focus and the caret go is decided by four general rules. The particular cases
that differ are listed after them. Every new feature follows a rule, or adds its case here.

## General rules

**A. A dialog closes: the focus goes back where it was.**
Every dialog and message of the application (Preferences, Workspace settings, Find, names, agent, task list, export,
"no more occurrence", errors, warnings, the permission questions) is shown through
`Feedback.modal` (`ui/feedback.py`): it remembers the focused control and puts the focus back once the dialog is
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
(When the text has to be rebuilt, as for the summary of the tools under the answers, the
caret stays on its message, at the same place in it.)
The end of an answer (the session file is read again and the view rebuilt if it differs) leaves the
focus where it is, so the user can type the next prompt; changing the option "Hide the system
messages" rebuilds the text and keeps the caret on its message.

## Particular cases

| Case | Focus | Why |
|---|---|---|
| New conversation (Ctrl+N) | the prompt field | there is nothing to read; the only action is to type |
| Workspace without any conversation | the (empty) conversation view, with the announcement "No conversation in this workspace." | the prompt and the buttons are greyed, so they cannot take the focus; the message tells what to do |
| Start with a last workspace that has no conversation | same as above | |
| Permission question of Claude (a dialog during an answer) | the description of the request inside the dialog; rule A when it closes | the user may be anywhere when it opens |
| A conversation that cannot be read | unchanged (rule A, an error dialog) | nothing was loaded |
| Second launch of the application | unchanged in the first window, which is brought to the front | |
| New conversation branch | rule B: the conversation view, at the last prompt (the text stays) | the branch shows the conversation it copies |
| Delete a conversation | rule B on the most recent conversation left; without any, the case "workspace without any conversation" | the deleted one cannot be shown any more |
