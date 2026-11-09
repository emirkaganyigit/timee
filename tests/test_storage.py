import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mola.storage import Store


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="mola-storage-")
        self.addCleanup(self.directory.cleanup)
        self.store = Store(self.directory.name)

    def test_unicode_plan_survives_restart(self):
        data = {"planner": [{"title": "Çalışma ve öğle arası", "day": 0}], "engine": {"today_work": 123.5}}
        self.assertTrue(self.store.save(data))
        self.assertEqual(Store(self.directory.name).load(), data)

    def test_damaged_original_is_preserved_and_recovery_reopens(self):
        original = b'{"planner": interrupted'
        self.store.path.write_bytes(original)
        self.assertEqual(self.store.load(), {})
        self.assertIn("korunuyor", self.store.error)
        self.assertTrue(self.store.save({"planner": ["recovered"]}))
        self.assertEqual((Path(self.directory.name)/"state.json").read_bytes(), original)
        self.assertEqual(Store(self.directory.name).load(), {"planner": ["recovered"]})

    def test_failed_atomic_replace_keeps_previous_state(self):
        self.store.save({"engine": {"today_work": 120}})
        with patch("mola.storage.os.replace", side_effect=OSError("disk full")):
            self.assertFalse(self.store.save({"engine": {"today_work": 240}}))
        self.assertEqual(self.store.load(), {"engine": {"today_work": 120}})
        self.assertEqual(list(Path(self.directory.name).glob(".state-*")), [])

    def test_invalid_json_numbers_cannot_overwrite_valid_state(self):
        self.store.save({"engine": {"today_work": 120}})
        self.assertFalse(self.store.save({"engine": {"today_work": float("nan")}}))
        self.assertEqual(self.store.load(), {"engine": {"today_work": 120}})

    def default_store(self, data_home: Path) -> Store:
        """Construct a default store without inheriting developer overrides."""
        with patch.dict(os.environ, {"XDG_DATA_HOME": str(data_home)}, clear=False):
            os.environ.pop("TIMEE_DATA_DIR", None)
            os.environ.pop("MOLA_DATA_DIR", None)
            return Store()

    def test_legacy_mola_state_is_copied_and_left_intact(self):
        data_home = Path(self.directory.name) / "data"
        legacy = data_home / "mola" / "state.json"
        legacy.parent.mkdir(parents=True)
        original = {"planner": [{"title": "Legacy plan"}], "preferences": {"sound": True}}
        legacy.write_text(json.dumps(original), encoding="utf-8")
        original_bytes = legacy.read_bytes()

        store = self.default_store(data_home)

        self.assertEqual(store.directory, data_home / "timee")
        self.assertEqual(store.load(), original)
        self.assertEqual((data_home / "timee" / "state.json").read_bytes(), original_bytes)
        self.assertEqual(legacy.read_bytes(), original_bytes)

    def test_existing_timee_state_wins_over_legacy_mola_state(self):
        data_home = Path(self.directory.name) / "data"
        legacy = data_home / "mola" / "state.json"
        current = data_home / "timee" / "state.json"
        legacy.parent.mkdir(parents=True)
        current.parent.mkdir(parents=True)
        legacy.write_text(json.dumps({"source": "mola"}), encoding="utf-8")
        current.write_text(json.dumps({"source": "timee"}), encoding="utf-8")

        store = self.default_store(data_home)

        self.assertEqual(store.load(), {"source": "timee"})
        self.assertEqual(json.loads(legacy.read_text(encoding="utf-8")), {"source": "mola"})

    def test_corrupt_legacy_state_is_ignored_without_creating_timee_state(self):
        data_home = Path(self.directory.name) / "data"
        legacy = data_home / "mola" / "state.json"
        legacy.parent.mkdir(parents=True)
        legacy.write_bytes(b'{"interrupted":')

        store = self.default_store(data_home)

        self.assertEqual(store.load(), {})
        self.assertFalse((data_home / "timee" / "state.json").exists())
        self.assertEqual(legacy.read_bytes(), b'{"interrupted":')
        self.assertEqual(store.error, "")

    def test_explicit_directory_never_imports_default_legacy_state(self):
        data_home = Path(self.directory.name) / "data"
        legacy = data_home / "mola" / "state.json"
        legacy.parent.mkdir(parents=True)
        legacy.write_text(json.dumps({"source": "mola"}), encoding="utf-8")
        explicit = Path(self.directory.name) / "isolated-profile"

        with patch.dict(os.environ, {"XDG_DATA_HOME": str(data_home)}, clear=False):
            store = Store(explicit)

        self.assertEqual(store.directory, explicit)
        self.assertEqual(store.load(), {})
        self.assertFalse((explicit / "state.json").exists())
        self.assertEqual(json.loads(legacy.read_text(encoding="utf-8")), {"source": "mola"})


if __name__ == "__main__":
    unittest.main()
