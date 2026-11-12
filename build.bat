@echo off
rem Build the packaged application into dist\WxClaude and zip it as dist\WxClaude-<version>.zip.
cd /d "%~dp0"
".venv\Scripts\python.exe" -m PyInstaller packaging\WxClaude.spec --noconfirm --distpath dist --workpath build\pyinstaller
if errorlevel 1 exit /b 1
rem The launchers (debug log, remote control) and the description of the remote control go in tools.
if not exist dist\WxClaude\tools mkdir dist\WxClaude\tools
copy /y tools\*.bat dist\WxClaude\tools\ >nul
copy /y docs\remote.md dist\WxClaude\tools\ >nul
rem The license of WxClaude and the notices of the software it carries go in the folder (and the zip).
copy /y LICENSE dist\WxClaude\ >nul
".venv\Scripts\python.exe" packaging\make_notices.py dist\WxClaude\THIRD-PARTY-NOTICES.txt
if errorlevel 1 exit /b 1
for /f %%v in ('.venv\Scripts\python.exe -c "import wxclaude; print(wxclaude.__version__)"') do set VERSION=%%v
if exist "dist\WxClaude-%VERSION%.zip" del "dist\WxClaude-%VERSION%.zip"
powershell -NoProfile -Command "Compress-Archive -Path 'dist\WxClaude' -DestinationPath 'dist\WxClaude-%VERSION%.zip'"
