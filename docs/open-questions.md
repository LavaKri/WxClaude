# Open questions and improvements

The other files of `docs/` describe what is true and decided. Everything that is still to decide,
to verify or to improve lives here, and nowhere else. When an item is settled, move the result to
the file it belongs to and delete it from this one.

## To decide

Nothing at the moment.

## To verify

- **UI Automation notifications and JAWS.** They reach NVDA and Narrator; test JAWS, with a focusable
  progress field as a fallback if they do not.
- **Reading the usage gauge without sending a message** (no way found yet).
- **Title entry of a generated title**: the reader expects an `ai-title` entry with an `aiTitle`
  field; only `custom-title` / `customTitle` was seen in real files.
- **Effort in the session files**: only `low` and `medium` were seen. Are `xhigh` and `max` written
  the same way, and are `effort` and `perTurnEffort` always equal?
- **Subscription use.** Driving `claude -p` from a custom front end with a subscription login may
  be restricted by the usage policy of the provider (an API key is the safe path). Check the current
  terms.

## Improvements not done yet

- A second launch of the application only shows a message; it could bring the window of the
  first instance to the front instead.
- The option "Announce the progress of Claude" is stored but has no effect until the runner exists.
- Context menu on a message (copy, show the tools used, a table, a link), see
  `conversation-display.md`.
- Delete a conversation (the menu item is greyed).
- Rebuild of the conversation view after each turn, from the session file (needs the runner).
