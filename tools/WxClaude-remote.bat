@echo off
rem Starts WxClaude with the remote control on: other programs can give it a few commands through
rem the named pipe \\.\pipe\WxClaude-<user> (see remote.md, next to this file).
start "" "%~dp0..\WxClaude.exe" --remote
