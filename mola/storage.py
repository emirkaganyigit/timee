"""Small atomic, local-only preference store."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import tempfile


class Store:
    def __init__(self, directory: str | Path | None = None):
        base = directory or os.environ.get("TIMEE_DATA_DIR") or os.environ.get("MOLA_DATA_DIR")
        data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
        self.directory = Path(base) if base else data_home / "timee"
        self.path = self.directory / "state.json"
        self.error = ""
        if base is None:
            self._copy_legacy_state(data_home / "mola")

    def _copy_legacy_state(self, legacy_directory: Path) -> None:
        """Copy a Mola state once, leaving the legacy data as a safe backup."""
        legacy = legacy_directory / "state.json"
        if self.path.exists() or not legacy.is_file():
            return
        try:
            value = json.loads(legacy.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                return
            self.directory.mkdir(parents=True, exist_ok=True)
            shutil.copy2(legacy, self.path)
        except (OSError, ValueError):
            return

    def load(self) -> dict:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise ValueError("Invalid state")
            return value
        except FileNotFoundError:
            return {}
        except (OSError, ValueError):
            self.error = "Kayıt okunamadı. Önceki dosya korunuyor; yeni kayıt ayrı tutulacak."
            # Never overwrite a damaged/unreadable original with defaults.
            self.path = self.directory / "state-recovered.json"
            try:
                value = json.loads(self.path.read_text(encoding="utf-8"))
                return value if isinstance(value, dict) else {}
            except (OSError, ValueError):
                return {}

    def save(self, state: dict) -> bool:
        temporary = None
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.directory, prefix=".state-", delete=False) as stream:
                temporary = stream.name
                json.dump(state, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            return True
        except (OSError, ValueError, TypeError):
            self.error = "Değişiklikler diske kaydedilemedi. Klasör izinlerini ve disk alanını kontrol et."
            return False
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)
