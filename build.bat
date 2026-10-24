@echo off
rem Build the packaged application into dist\WxClaude and zip it as dist\WxClaude-<version>.zip.
cd /d "%~dp0"
".venv\Scripts\python.exe" -m PyInstaller packaging\WxClaude.spec --noconfirm --distpath dist --workpath build\pyinstaller
if errorlevel 1 exit /b 1
copy /y packaging\WxClaude-debug.bat dist\WxClaude\ >nul
for /f %%v in ('.venv\Scripts\python.exe -c "import wxclaude; print(wxclaude.__version__)"') do set VERSION=%%v
if exist "dist\WxClaude-%VERSION%.zip" del "dist\WxClaude-%VERSION%.zip"
powershell -NoProfile -Command "Compress-Archive -Path 'dist\WxClaude' -DestinationPath 'dist\WxClaude-%VERSION%.zip'"
