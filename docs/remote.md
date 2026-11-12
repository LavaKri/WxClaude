# Remote control

Another program can give WxClaude a few commands through a named pipe: stop the message being
answered, send a message, read the last answer and the history of the announcements, and ask which
version answers. It is off unless the user starts WxClaude with `--remote`. Nothing is created and the code is not used
without that option.

## Turning it on

`wxclaude --remote` (or `python -m wxclaude --remote`). The window title then starts with
**Remote enabled** (*Remote activé*) so that the user, and the screen reader that says the title,
always know it is on. If the pipe cannot be created (no pipes on this system, the name is taken)
the application starts without it and says so in a dialog; the title does not say *Remote enabled*.

The option only counts for the first instance: only one WxClaude runs per user (`settings.md`), and
a second launch with `--remote` only brings the window of the first one to the front. To turn the
remote control on, quit WxClaude and start it again with the option.

## The pipe

Its name is fixed per user, so that any program finds it: `\\.\pipe\WxClaude-<user name>` (the
user name as `wx.GetUserId()` gives it; a `\` or `/` in it becomes `_`). A client:

1. connects to the pipe (it fails if WxClaude is not running or runs without `--remote`);
2. writes **one request in one piece**: a JSON object in UTF-8 (a pipe in message mode: the
   request must not be split into several writes);
3. reads **one response**: a JSON object, ASCII only (the accents are escaped, so a client that
   reads with another code page still gets the right text);
4. closes the connection.

A request is at most 256 KB. A client that connects and sends nothing is dropped after 2 seconds,
a request that is too large is dropped without an answer. Each client is served in a thread of its
own (8 at the same time at most, the others wait), and the window runs the commands one after the
other. Clients that arrive at the very same moment can find the pipe **busy** for a few
milliseconds (`ERROR_PIPE_BUSY`; `open` of Python reports it as `errno 22`): a client waits and
tries again, as `NamedPipeClientStream.Connect(timeout)` of .NET does by itself. If the window does not run a command within
5 seconds (a dialog is open and blocks it, for example) the client gets `timeout` and the command
is not run afterwards, so trying again does not do it twice.

There is no key and no handshake: this is what lets a script in any language use the pipe. The
rights of the pipe are the default ones of Windows (a pipe made without a security descriptor): by
its documentation the system, the administrators and the account that runs WxClaude can write to
it, the other accounts of the computer cannot (not checked by the tests, which run under one
account). **Any program run by the same account can give these commands**, as it
could already start `claude` itself: the user decides by starting WxClaude with `--remote`, and the
title says so. A message sent this way goes where a typed one goes: same agent, same permission
questions asked to the user, same restricted mode in a folder that is not approved.

## Commands

A request is `{"command": "<name>", ...}`. The name is written exactly as below.

| Command | More fields | Response |
|---|---|---|
| `interrupt` | | `{"ok": true}`. Same as the button *Interrupt Claude* (it also stops the reading of the gauges). Nothing happens, and it is still `ok`, if nothing is running. |
| `send` | `text`: the message (a string, not empty once trimmed) | `{"ok": true}` as soon as the message started: it is answered later, read it with `last`. Sent with the agent of the conversation. The prompt field and the focus are not touched, so what the user is typing stays. |
| `last` | `fields`: a list of `message`, `status`, `tokens` (all three when it is left out) | `{"ok": true, <the fields asked>}`, see below. |
| `announcements` | `limit`: a whole number from 1 (50 when left out, 500 at most) | `{"ok": true, "lines": ["10:20 Claude is thinking.", ...]}`: the last lines of the history of the announcements (*Help > Announcement history*), the newest last, without its blank separators. |
| `version` | | `{"ok": true, "application": "WxClaude", "version": "0.4.0", "protocol": 1}`. See below. |

### `version`

It tells a client that what answers on the pipe is WxClaude (a program that holds the name of the
pipe by chance would not answer this way; it is not a proof against one that imitates it), which
version it is, and which version of the protocol it speaks.
`protocol` is a whole number, 1 for the commands and responses of this document; it will be raised
when a command or a response changes in a way a client can notice (a field that is only added does not
count: a client ignores the fields it does not know). It is the only command that does not wait for
the window: it is answered at once, even if a dialog blocks the window, so it also tells a client
that WxClaude is there but busy.

### `last`

All the fields come from the same instant. A value that does not exist yet is `null`, which is not
an error.

- `message`: the text of the last answer of Claude that is complete. While a message is being
  answered, the answer in progress is not given: it is the one before. `null` before the first
  answer. The messages that are hidden as noise do not count.
- `status`: `"idle"`, or `"busy"` while Claude answers or the gauges are read (the send buttons are
  greyed then). A client that sent a message waits for `"idle"` and reads `message`.
- `tokens`: the counts of that same answer, `{"input": 1200, "output": 340, "cache_creation": 0,
  "cache_read": 800}` (`claude-cli.md`, the `usage` of each message is its own); `null` when the
  answer has none (the CLI reported none, or the answer has just been shown and the session file
  is not read yet).

```json
{"command": "last", "fields": ["status", "tokens"]}
{"ok": true, "status": "idle", "tokens": {"input": 1200, "output": 340, "cache_creation": 0, "cache_read": 800}}
```

### Errors

`{"ok": false, "error": "<code>"}`:

| Code | When |
|---|---|
| `invalid_request` | not JSON, not an object, `text` missing or not a string, `fields` not a non-empty list, `limit` not a positive whole number |
| `unknown_command` | the command is missing or is not one of the five |
| `unknown_field` | a name of `fields` is not `message`, `status` or `tokens` |
| `empty_text` | `send` with a text that is empty once trimmed |
| `no_conversation` | `send` without a current conversation (open a workspace and a conversation) |
| `busy` | `send` while Claude answers or the gauges are read: wait for `status` to be `idle` |
| `not_started` | `send` that could not start (Claude Code is not found, a provider key is missing...): the user is shown the reason in the window |
| `timeout` | the window did not run the command in 5 seconds |
| `internal_error` | the command failed inside WxClaude (the error is in `wxclaude.log`) |

## Example: PowerShell

```powershell
function Send-WxClaude($request) {
    $pipe = New-Object System.IO.Pipes.NamedPipeClientStream('.', "WxClaude-$env:USERNAME", 'InOut')
    $pipe.Connect(3000)
    $bytes = [Text.Encoding]::UTF8.GetBytes(($request | ConvertTo-Json -Compress))
    $pipe.Write($bytes, 0, $bytes.Length)   # one write
    $buffer = New-Object byte[] 1MB
    $count = $pipe.Read($buffer, 0, $buffer.Length)
    $pipe.Dispose()
    [Text.Encoding]::UTF8.GetString($buffer, 0, $count) | ConvertFrom-Json
}
Send-WxClaude @{ command = 'send'; text = 'Hello' }
Send-WxClaude @{ command = 'last'; fields = @('status') }
```

In Python, `open(r"\\.\pipe\WxClaude-<user>", "r+b", buffering=0)`, one `write`, one `read`.

## How it is built

- `core/remote/protocol.py`: the five commands, `PROTOCOL_VERSION`, the fields, the error codes, `parse_request` (a
  request that is not valid is refused before it reaches the application) and the responses.
- `core/remote/pipe_server.py`: `PipeServer`, the thread that listens (`multiprocessing.connection`
  with `AF_PIPE` and no key: Python's own framing and handshake are not used, the messages are the
  raw bytes of the pipe), `pipe_name`. The first instance of the pipe is created with
  `FILE_FLAG_FIRST_PIPE_INSTANCE`, so a name already taken is an error, not a second server.
- `core/remote/endpoint.py`: `RemoteEndpoint`, the handler of the server: it checks the request in
  the thread of the pipe, has it run on the interface thread (`wx.CallAfter`, given by the window)
  and waits for the response (`version` is answered there and then).
- `presenters/remote_presenter.py`: `RemotePresenter` and `RemoteLinks`, what the commands do,
  without wx (tested with a fake window).
- `ui/remote_control.py`: `RemoteControl`, the pipe and the endpoint tied to `wx.CallAfter`;
  `MainWindow` builds the links, shows the title and stops it when the window closes.

At idle the listening thread waits for a connection and uses no CPU (it was measured: no wake-up,
about 3 MB for the module).

## What is not done

- No key or other check of who the client is (see above); the protection is the option, the title,
  the rights of the pipe and the permission questions.
- Nothing is announced when a command arrives, apart from what the command does itself (*Claude is
  thinking*, *Interrupting Claude*, *Claude has answered*), which is also in the announcement history.
- The window of the first instance is not brought to the front by a command: the focus is never
  changed.
- A client that wants more than the last answer reads the session file of the CLI itself.
