# Architecture

WxClaude is a wxPython desktop front end for `claude -p --output-format stream-json`.

- `core/`: logic, never imports `wx` (mypy strict).
- `ui/`: thin wx layer.
- Worker threads (CLI reader, permission hook server) never touch wx; they post to the UI with
  `wx.CallAfter`.

The full milestone plan is kept in the project plan; see `roadmap.md` once written.
