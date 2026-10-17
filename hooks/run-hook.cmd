: << 'CMDBLOCK'
@echo off
REM grillspec hook runner: one file for cmd.exe and POSIX shells.
REM Based on obra/superpowers hooks/run-hook.cmd (MIT); see NOTICE.
REM Usage: run-hook.cmd <event> <harness>
REM Fail-open: whatever happens, exit 0 so a broken install never blocks the agent.
setlocal
set "ROOT=%~dp0.."
set "PY="
py -3 -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>nul && set "PY=py -3"
if not defined PY python -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>nul && set "PY=python"
if not defined PY goto nopython
%PY% "%ROOT%\scripts\grillspec.py" hook %1 --harness %2
exit /b 0
:nopython
set "MSG=WARNING: grillspec gates are OFF: python 3.11+ not found"
if "%~2"=="cursor" goto cursor
if "%~2"=="antigravity" goto antigravity
echo {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "%MSG%"}}
exit /b 0
:cursor
echo {"additional_context": "%MSG%"}
exit /b 0
:antigravity
echo {"injectSteps": [{"systemMessage": {"systemMessage": "%MSG%"}}]}
exit /b 0
CMDBLOCK

# POSIX shell. Splits $0 instead of calling dirname, so an empty PATH still works.
case "$0" in
  */*|*\\*) HOOK_DIR="$(cd "${0%[/\\]*}" && pwd)" ;;
  *) HOOK_DIR="$(pwd)" ;;
esac
ROOT="${HOOK_DIR%/*}"
EVENT="$1"
HARNESS="$2"
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 &&
    "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then
    "$candidate" "$ROOT/scripts/grillspec.py" hook "$EVENT" --harness "$HARNESS"
    exit 0
  fi
done
MSG='WARNING: grillspec gates are OFF: python 3.11+ not found'
case "$HARNESS" in
  cursor) printf '{"additional_context": "%s"}\n' "$MSG" ;;
  antigravity) printf '{"injectSteps": [{"systemMessage": {"systemMessage": "%s"}}]}\n' "$MSG" ;;
  *) printf '{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "%s"}}\n' "$MSG" ;;
esac
exit 0
