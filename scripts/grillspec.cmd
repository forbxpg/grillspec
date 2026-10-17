@echo off
REM Run the grillspec CLI with a suitable Python (3.11 or newer) on Windows.
REM Order: %GRILLSPEC_PYTHON%, py -3.15 ... py -3.11, python3, python, then uv run.
REM No labels or goto: cmd.exe mis-finds labels in LF files past 512 bytes.
REM Exits 127 when nothing works, so the hook runner can tell.
setlocal
set "SCRIPT=%~dp0grillspec.py"
set "CHECK=import sys; sys.exit(not (3, 11) <= sys.version_info[:2])"
set "PYEXE="
set "PYARG="
if defined GRILLSPEC_PYTHON "%GRILLSPEC_PYTHON%" -c "%CHECK%" >nul 2>nul && set "PYEXE=%GRILLSPEC_PYTHON%"
for %%V in (3.15 3.14 3.13 3.12 3.11) do if not defined PYEXE py -%%V -c "%CHECK%" >nul 2>nul && set "PYEXE=py" && set "PYARG=-%%V"
for %%C in (python3 python) do if not defined PYEXE %%C -c "%CHECK%" >nul 2>nul && set "PYEXE=%%C"
if defined PYEXE "%PYEXE%" %PYARG% "%SCRIPT%" %*
if defined PYEXE exit /b %ERRORLEVEL%
set "HASUV="
where uv >nul 2>nul && set "HASUV=1"
if defined HASUV uv run --no-project --quiet --python ">=3.11" python "%SCRIPT%" %*
if defined HASUV exit /b %ERRORLEVEL%
echo grillspec: no Python 3.11 or newer found (tried GRILLSPEC_PYTHON, py, python3, python, uv). 1>&2
echo Install Python 3.11+ or uv, or set GRILLSPEC_PYTHON to a Python 3.11+ executable. 1>&2
exit /b 127
