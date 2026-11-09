#!/usr/bin/env bash
set -euo pipefail
timee_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd -- "$timee_root"

# Prefer the system Qt bindings when available; a project venv is the fallback.
if [[ -n "${TIMEE_PYTHON:-}" ]]; then
    timee_python="$TIMEE_PYTHON"
elif [[ -n "${MOLA_PYTHON:-}" ]]; then
    timee_python="$MOLA_PYTHON"
elif command -v python3 >/dev/null 2>&1 && python3 -c 'import PySide6' >/dev/null 2>&1; then
    timee_python="$(command -v python3)"
elif [[ -x "$timee_root/.venv/bin/python" ]] && "$timee_root/.venv/bin/python" -c 'import PySide6' >/dev/null 2>&1; then
    timee_python="$timee_root/.venv/bin/python"
else
    cat >&2 <<'HELP'
Timee requires Python 3 and PySide6. Run these commands from the project directory:

  python3 -m venv .venv
  .venv/bin/python -m pip install -r requirements.txt
  ./run.sh

To select a specific Python interpreter:
  TIMEE_PYTHON=.venv/bin/python ./run.sh
HELP
    exit 1
fi

if ! "$timee_python" -c 'import PySide6' >/dev/null 2>&1; then
    printf '%s\n' 'The selected Python cannot import PySide6. Install requirements.txt into that environment.' >&2
    exit 1
fi
exec "$timee_python" -m mola.app "$@"
