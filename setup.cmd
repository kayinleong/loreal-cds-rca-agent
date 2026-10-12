@echo off
rem One-command setup for the RCA Copilot agents (Windows, batch only - no PowerShell).
rem Finds a suitable Python by running a probe, then runs scripts\bootstrap.py.
setlocal EnableDelayedExpansion
cd /d "%~dp0"

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
exit /b 1

:found
echo Using Python: !PY!
!PY! scripts\bootstrap.py %*
exit /b !ERRORLEVEL!

:try
%~1 -c "import sys,struct; sys.exit(0 if sys.version_info>=(3,10) and struct.calcsize('P')==8 else 1)" >nul 2>&1
if not errorlevel 1 set "PY=%~1"
exit /b 0
