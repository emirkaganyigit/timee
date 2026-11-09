#!/usr/bin/env bash
set -euo pipefail
timee_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
timee_data_home="${XDG_DATA_HOME:-$HOME/.local/share}"
timee_applications="$timee_data_home/applications"
timee_icons="$timee_data_home/icons/hicolor/scalable/apps"

if [[ ! -f "$timee_root/assets/timee.svg" ]]; then
    printf '%s\n' 'Application icon is missing: assets/timee.svg' >&2
    exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
    printf '%s\n' 'Python 3 is required to generate the desktop launcher.' >&2
    exit 1
fi

install -d -- "$timee_applications" "$timee_icons"
install -m 644 -- "$timee_root/assets/timee.svg" "$timee_icons/io.github.emirkaganyigit.timee.svg"
python3 - "$timee_root" "$timee_applications/io.github.emirkaganyigit.timee.desktop" <<'PY'
from pathlib import Path
import sys
root, destination = map(Path, sys.argv[1:])
launcher = str(root / "run.sh")
if any(char in launcher for char in "\n\r"):
    raise SystemExit("The project directory cannot contain a newline.")
# Desktop Entry Exec has its own quoting and percent-field-code rules.
argument = launcher.replace("%", "%%")
argument = "".join("\\" + char if char in '\\"`$' else char for char in argument)
argument = '"' + argument.replace("\\", "\\\\") + '"'
template = (root / "assets/io.github.emirkaganyigit.timee.desktop").read_text(encoding="utf-8")
destination.write_text(template.replace("@LAUNCHER@", argument), encoding="utf-8")
destination.chmod(0o644)
print(f"Launcher created: {destination}")
PY
rm -f -- "$timee_applications/io.github.mola.desktop" "$timee_icons/io.github.mola.svg"
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$timee_applications" >/dev/null 2>&1 || true
fi
if [[ -x "$timee_root/scripts/install-kwin-rule.sh" ]]; then
    "$timee_root/scripts/install-kwin-rule.sh"
fi
printf '%s\n' 'Timee is now available in the application menu. Run this installer again if the project directory moves.'
