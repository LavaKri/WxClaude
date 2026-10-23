# Conversation display

Specification decided with the user. Implemented: `core/conversation/headings.py` (parser, navigation, UTF-16),
`core/conversation/conversation_document.py` (text and message spans), `ui/conversation_view.py` (the field and
its keys). The system messages are hidden by default (Preferences > Workspace > "Hide the
system messages"). Where the focus and the caret go when the text changes is in `focus.md`;
search is in `interface.md`.

The French wording of the titles is `Vous dites : …` and `Réponse de <model>, effort <effort>`
(effort names: faible, moyen, élevé, très élevé, maximum); `Claude a répondu` without a model.

## The text

The conversation is shown in a **read-only multi-line text field** as one Markdown document. The
displayed text is the raw Markdown: the `#` of the headings stay, so the offsets given by the
parser are the offsets in the field (only the UTF-16 conversion is needed, see below).

First version: **only the user's prompts and Claude's answers**. Nothing else is displayed
(thinking, tools, tool results, system messages, notifications).

For each exchange:

```
# Vous dites : <preview of the prompt>
<the prompt>

## Réponse de claude-sonnet-5-5, effort moyen
<the answer, unchanged>
```

- The prompt is a **level 1 title**; the title of an answer is a **level 2 title** (the model that
  answered and the effort it was generated with, read from the `effort` field of the session
  file (the stream does not report it, so for a message just sent the requested effort is used);
  without a known effort: `Réponse de <model>`; an answer without a model, for example the message that
  announces a usage limit: `Claude a répondu`).
- The **headings of Claude's answer are not modified** (no level shift), so they can be of any
  level; `1` visits the prompts and the level 1 titles inside answers.
- The preview is the first sentence if it has 20 words or fewer, else the first 20 words and `…`.
- Titles are translated (`_()`).
- Only complete messages are appended (no partial text), so the field is never rewritten in the
  middle and the caret and the focus are not disturbed.

## Navigation by headings

The field is read-only, so letters are free:

| Key | Action |
|---|---|
| `T` / `Shift+T` | next / previous heading, any level |
| `1` to `6` | next heading of that level |
| `Shift+1` to `Shift+6` | previous heading of that level |

The caret moves to the start of the heading. **The screen reader does not read the line when the
caret is moved by the application**, so the application announces it through UI Automation:
`<title text>, title <N>` (N = number of `#`), without the `#`. When the user moves with the arrow
keys the screen reader reads the raw line.

Messages announce the boundaries ("no more heading") the way the other announcements do.

## Parser

`markdown-it-py` (CommonMark): ATX and Setext headings, code blocks ignored. Each heading has a
level, a title, and offsets; a node's body goes up to the next heading of any level. Build it in
`core/` without `wx` (new dependency `markdown-it-py`). Positions: Windows text fields count in
UTF-16 units, so convert between Python indexes and field positions (an emoji takes two).

## Keeping the field and the data in step

- The data is a list of `Message`; the field is only a projection of it.
- Each message remembers its span (start, end) in the field, found back from the caret position by
  bisection (context menu, copy).
- After each turn, the session file written by the CLI is read again; it is the reference. If the
  messages differ from what was appended, the field is rebuilt.
- Hidden noise (the answer "No response requested.", the prompt "continue") is not displayed unless
  the option "Hide the system messages" is cleared; the view keeps all the messages and rebuilds
  the text when the option changes, the caret staying on its message.

## Other information in dialogs

The message model keeps what is not displayed (tools used, tool results, thinking, usage). The
context menu of the view (Applications key, Shift+F10) works on the message that holds the caret and
offers, in this order, only what applies, then always *Copy the message* (its Markdown text) and
*Copy the exchange* (the prompt of the exchange the message belongs to and every answer to it,
as displayed, titles included; answers shown before any prompt make an exchange of their own;
nothing is announced, the user asked for it), and last *Next heading* (`T`) and *Previous heading*
(`Shift+T`), the same jumps as the keys, announced like them (the shortcut shown is the key itself):

- **Show the tools used…** when the message has tools (an answer gets them from the session file once
  the turn is over). A dialog lists the tools, one per line (`Bash, git status, failed`: name, what
  it worked on, and "failed" if it did), and a read-only field gives everything about the selected
  one (each argument, then the result).
- **Show the table…** when the caret is on a line of a table (`core/conversation/details.py`, the parser with the
  `table` rule; a table inside a code block is not one). The dialog lists the rows, one per line
  (`Name: a.txt, Size: 3`, empty cells left out), and *Copy the table* puts its Markdown on the
  clipboard.
- **Show the links…** when the message has a link (`[text](address)` or `<address>`). The dialog
  lists them (`text, address`) with the link of the caret's line selected (else the first);
  *Open in the browser* only hands `http://`, `https://` and `mailto:` addresses to the system (any
  other kind is refused with an error; the parser itself does not make links of `file:` or
  `javascript:`), *Copy the address* copies it.

The native menu of the field (undo, redo, cut, paste...) is never shown: the rich text field opens it
by itself for Shift+F10 and for the Applications key when the key goes up, so the view handles
Shift+F10 when it goes down and swallows both keys when they go up (the Applications key and the
right click still reach `EVT_CONTEXT_MENU`, checked with real key and mouse events). Without a
message at the caret (empty conversation) no menu opens. After an action the focus returns to the
view (`focus.md`).

## Progress and usage

- **Progress** goes to the status bar (not focusable) and is announced through UI Automation
  (category "Progress of Claude" of Preferences > Screen reader); there is no shortcut of ours to read
  it again, screen readers have their own for the status bar. Three status fields: the first gives the
  position of the caret in the conversation, `Message 3 of 8` (French: `Message 3 sur 8`); only the
  prompts of the user are counted, an answer belongs to the prompt it follows, and the field is empty
  while the conversation has no prompt (the number is 0 before the first prompt, for example when
  the system messages are shown and an answer opens the conversation). It follows the keyboard, the
  mouse, the jumps by headings and the search, and is not announced. The second field gives the step
  Claude works on (`interface.md`, "Step"), the third holds the last announcement.
- **Usage of Claude**: a dialog in the Tools menu, `Ctrl+Shift+U`, always available. A read-only
  field (initial focus) with one fact per line: each gauge of the subscription (`5-hour window, 74 %
  used, resets at 16:00`, from the `rate_limit_event` lines; the time alone for today, else date and
  time), the limit status when it is not `allowed`, when the gauges were updated, then the tokens, the cost at
  list price, the duration and the turns of the last message, and the totals of the conversation
  since it was opened in WxClaude (sum of the `result` lines received; they start again when another
  conversation becomes current, the gauges belong to the account and stay). A `result` reports the
  total cost of the session, so the cost of a message is that total minus the one before it (a
  message whose previous total is not known is counted without a cost). Data arrives with the
  answers: before the first one the dialog says so. Facts that are unknown are not written.
- **Errors** are not part of the conversation text: status bar and a dialog.
