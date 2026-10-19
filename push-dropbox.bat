@echo off
rem Push every branch and tag of this repository to a bare backup repository in Dropbox.
rem The backup repository is created on the first run. The result is shown in a dialog box.
rem Messages are plain ASCII: the console code page would garble accents.
setlocal
cd /d "%~dp0"
set "BACKUP=%USERPROFILE%\Dropbox\Sauvegardes\WxClaude.git"
set "LOG=%TEMP%\wxclaude-push.log"
set "TITLE=Sauvegarde WxClaude"
set "RESULT=OK"
echo Destination : %BACKUP%> "%LOG%"

if exist "%BACKUP%\HEAD" goto have_backup
echo Creation du depot de sauvegarde>> "%LOG%"
git init --bare --initial-branch=main "%BACKUP%" >> "%LOG%" 2>&1
if errorlevel 1 goto failed

:have_backup
git remote get-url dropbox >nul 2>&1
if errorlevel 1 goto add_remote
git remote set-url dropbox "%BACKUP%" >> "%LOG%" 2>&1
goto push

:add_remote
git remote add dropbox "%BACKUP%" >> "%LOG%" 2>&1
if errorlevel 1 goto failed

:push
git push dropbox --all >> "%LOG%" 2>&1
if errorlevel 1 goto failed
git push dropbox --tags >> "%LOG%" 2>&1
if errorlevel 1 goto failed
goto show

:failed
set "RESULT=ECHEC de la sauvegarde"

:show
powershell -NoProfile -Command "Add-Type -AssemblyName System.Windows.Forms; $text = $env:RESULT + [Environment]::NewLine + [Environment]::NewLine + (Get-Content -Raw $env:LOG); [void][System.Windows.Forms.MessageBox]::Show($text, $env:TITLE)"
if "%RESULT%"=="OK" exit /b 0
exit /b 1
