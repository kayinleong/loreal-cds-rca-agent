@echo off
rem One-command setup for the RCA Copilot agents (Windows, batch only - no PowerShell).
rem Finds a suitable Python by running a probe, then runs scripts\bootstrap.py.
rem Delayed expansion is deliberately NOT enabled: "!" in arguments (proxy passwords) or paths must survive.
setlocal
cd /d "%~dp0"

rem Double-clicked from Explorer? cmdcmdline then names this script; keep the window open at the end.
set "PAUSEIT="
echo %cmdcmdline% | find /i "%~nx0" >nul
if not errorlevel 1 set "PAUSEIT=1"
rem PowerShell / VS Code / Windows Terminal also launch .cmd via "cmd /c setup.cmd", so skip the pause
rem whenever a terminal or automation (Copilot, Claude Code, CI) is the caller - a pause would hang it.
if defined SETUP_NOPAUSE set "PAUSEIT="
if defined TERM_PROGRAM set "PAUSEIT="
if defined VSCODE_PID set "PAUSEIT="
if defined WT_SESSION set "PAUSEIT="
if defined CLAUDECODE set "PAUSEIT="
if defined CI set "PAUSEIT="

set "PY="
call :try "py -3.12"
if defined PY goto found
call :try "py -3.11"
if defined PY goto found
call :try "py -3.13"
if defined PY goto found
call :try "py -3.10"
if defined PY goto found
call :try "py -3"
if defined PY goto found
call :try "python"
if defined PY goto found
call :try "python3"
if defined PY goto found

echo ERROR: no suitable Python found. Need Python 3.10 or newer, 64-bit. 3.12 is recommended.
echo The Microsoft Store python shortcut does not count.
echo Install one of these, no admin rights needed:
echo   - python.org installer: https://www.python.org/downloads/windows/
echo     choose "Install Python for me only" and tick "Add python.exe to PATH"
echo   - winget install Python.Python.3.12 --scope user
echo Then open a new terminal and run setup.cmd again.
set "RC=1"
goto finish

:found
echo Using Python: %PY%
%PY% scripts\bootstrap.py %*
set "RC=%ERRORLEVEL%"

:finish
if defined PAUSEIT pause
exit /b %RC%

:try
%~1 -c "import sys,struct; sys.exit(0 if sys.version_info>=(3,10) and struct.calcsize('P')==8 else 1)" >nul 2>&1
if not errorlevel 1 set "PY=%~1"
exit /b 0
