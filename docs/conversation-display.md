# Conversation display

Specification decided with the user. Implemented: `core/headings.py` (parser, navigation, UTF-16),
`core/conversation_document.py` (text and message spans), `ui/conversation_view.py` (the field and
its keys). Not implemented yet: the rebuild after each turn (needs the runner), the option that
shows hidden messages, the context menu.

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

# Réponse de claude-sonnet-5-5, effort moyen
<the answer, unchanged>
```

- The prompt is a **level 1 title**; the title of an answer is also level 1 (the model that
  answered and the effort that was requested, since the stream does not report it; without a
  known effort: `Réponse de <model>`; an answer without a model, for example the message that
  announces a usage limit: `Claude a répondu`).
- The **headings of Claude's answer are not modified** (no level shift).
- The preview is the first sentence if it has 20 words or fewer, else the first 20 words and `…`.
- Titles are translated (`_()`); the exact wording above is to be confirmed.
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
  an option asks for it.

## Later: other information in dialogs

The message model keeps what is not displayed (tools used, tool results, thinking, usage). In the
body of a message the context menu (Applications key, Shift+F10) offers an item to show it in a
dialog: "Show the tools used", and the same mechanism for a **table** or a **link** found by the
parser at the caret position.

## Progress and usage

- **Progress** goes to the status bar (not focusable) and is announced through UI Automation;
  a configurable shortcut reads it again. Two status fields: the action, the current task.
- **Usage of Claude**: a dialog in the Tools menu (subscription gauges, tokens of the last turn and
  of the session, cost). Data arrives with the answers.
- **Errors** are not part of the conversation text: status bar and a dialog.
