: << 'CMDBLOCK'
@echo off
REM grillspec hook runner: one file for cmd.exe and POSIX shells.
REM Based on obra/superpowers hooks/run-hook.cmd (MIT); see NOTICE.
REM Usage: run-hook.cmd <event> <harness>
REM Fail-open: whatever happens, exit 0 so a broken install never blocks the agent.
setlocal
set "ROOT=%~dp0.."
REM scripts\grillspec.cmd finds a Python 3.11+ and exits 127 when there is none.
call "%ROOT%\scripts\grillspec.cmd" hook %1 --harness %2
if not "%ERRORLEVEL%"=="127" exit /b 0
REM No Python: report it in the harness's own shape. One-line ifs, no labels:
REM cmd.exe mis-finds labels in LF files once they sit past a 512-byte boundary.
REM A pre-tool hook then has no opinion; Cursor and Antigravity need JSON for that.
if "%~1"=="pre-tool" if "%~2"=="cursor" echo {}& exit /b 0
if "%~1"=="pre-tool" if "%~2"=="antigravity" echo {"decision": "allow"}& exit /b 0
if "%~1"=="pre-tool" exit /b 0
set "MSG=WARNING: grillspec gates are OFF: python 3.11+ not found"
if "%~2"=="cursor" echo {"additional_context": "%MSG%"}& exit /b 0
if "%~2"=="antigravity" echo {"injectSteps": [{"systemMessage": {"systemMessage": "%MSG%"}}]}& exit /b 0
echo {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "%MSG%"}}
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
# scripts/grillspec finds a Python 3.11+ and exits 127 when there is none. Run it
# through sh: packagers strip exec bits.
sh "$ROOT/scripts/grillspec" hook "$EVENT" --harness "$HARNESS" 2>/dev/null
[ "$?" -eq 127 ] || exit 0
# No Python: a pre-tool hook has no opinion (Cursor and Antigravity need JSON for it).
if [ "$EVENT" = "pre-tool" ]; then
  case "$HARNESS" in
    cursor) printf '{}\n' ;;
    antigravity) printf '{"decision": "allow"}\n' ;;
  esac
  exit 0
fi
MSG='WARNING: grillspec gates are OFF: python 3.11+ not found'
case "$HARNESS" in
  cursor) printf '{"additional_context": "%s"}\n' "$MSG" ;;
  antigravity) printf '{"injectSteps": [{"systemMessage": {"systemMessage": "%s"}}]}\n' "$MSG" ;;
  *) printf '{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "%s"}}\n' "$MSG" ;;
esac
exit 0
