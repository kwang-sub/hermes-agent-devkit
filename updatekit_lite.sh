#!/usr/bin/env bash
set -euo pipefail
# Host-side Git Bash/WSL wrapper: actual updater is Windows PowerShell.
HERE="$(cd -- "$(dirname -- "$0")" && pwd -P)"
if command -v cygpath >/dev/null 2>&1; then
  SCRIPT="$(cygpath -w "$HERE/updatekit_lite.ps1")"
elif command -v wslpath >/dev/null 2>&1; then
  SCRIPT="$(wslpath -w "$HERE/updatekit_lite.ps1")"
else
  echo "Windows Git Bash (cygpath) or WSL (wslpath) required." >&2
  echo "Use .\\updatekit_lite.ps1 in Windows PowerShell." >&2
  exit 2
fi
if ! command -v powershell.exe >/dev/null 2>&1; then
  echo "powershell.exe not found. Run updatekit_lite.ps1 on the Windows host." >&2
  exit 2
fi
exec powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$SCRIPT" "$@"
