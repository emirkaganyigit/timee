import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
from datetime import datetime

from PySide6.QtWidgets import QApplication
from mola.planner import PlannerWidget, TaskDialog, active_task, normalize_entries, time_minutes, validate_entry


def task(day=0, start="08:00", end="09:00", title="Odak", identifier="first"):
    return {"id": identifier, "day": day, "start": start, "end": end, "title": title}


class PlannerValidationTests(unittest.TestCase):
    def test_touching_blocks_allowed_but_overlaps_rejected(self):
        existing = [task()]
        validate_entry(task(start="09:00", end="10:00", identifier="next"), existing)
        for start, end in (("08:30", "09:30"), ("07:30", "08:30"), ("07:00", "10:00"), ("08:10", "08:20")):
            with self.assertRaises(ValueError):
                validate_entry(task(start=start, end=end, identifier="next"), existing)

    def test_same_times_on_other_days_allowed(self):
        for day in range(1, 7):
            self.assertEqual(validate_entry(task(day=day), [task()])["day"], day)

    def test_edit_ignores_original_task_only(self):
        self.assertEqual(validate_entry(task(title="Yeni başlık"), [task()], ignore_id="first")["title"], "Yeni başlık")
        with self.assertRaises(ValueError):
            validate_entry(task(), [task()], ignore_id="different")

    def test_invalid_time_day_title_rejected(self):
        for bad in ("24:00", "00:60", "8:00", "-1:20", None):
            with self.assertRaises(ValueError):
                time_minutes(bad)
        for bad in (-1, 7, True, "1", None):
            with self.assertRaises(ValueError):
                validate_entry(task(day=bad), [])
        for bad in ("", "  ", "a" * 141):
            with self.assertRaises(ValueError):
                validate_entry(task(title=bad), [])
        for start, end in (("09:00", "09:00"), ("23:00", "01:00")):
            with self.assertRaises(ValueError):
                validate_entry(task(start=start, end=end), [])

    def test_midnight_and_last_minute_valid(self):
        self.assertEqual(time_minutes("00:00"), 0)
        self.assertEqual(time_minutes("23:59"), 1439)
        validate_entry(task(start="00:00", end="00:01"), [])

    def test_normalization_drops_invalid_saved_data_and_duplicates_ids_fixed(self):
        entries = normalize_entries([None, "broken", {}, task(), task(day=1), task(start="08:30", end="10:00", identifier="overlap")])
        self.assertEqual(len(entries), 2)
        self.assertNotEqual(entries[0]["id"], entries[1]["id"])
        self.assertEqual(normalize_entries({}), [])

    def test_current_task_end_exclusive_and_weekly(self):
        entries = [task()]
        for monday in (9, 16):
            self.assertIsNotNone(active_task(entries, datetime(2026, 11, monday, 8)))
            self.assertIsNotNone(active_task(entries, datetime(2026, 11, monday, 8, 59)))
            self.assertIsNone(active_task(entries, datetime(2026, 11, monday, 9)))
        self.assertIsNone(active_task(entries, datetime(2026, 11, 10, 8)))
        active_task(entries, datetime(2026, 11, 9, 8))["title"] = "Changed"
        self.assertEqual(entries[0]["title"], "Odak")


class PlannerWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_widget_and_dialog_validation(self):
        widget = PlannerWidget([task()])
        widget.resize(900, 650)
        widget.show()
        self.app.processEvents()
        self.assertEqual(widget.columns.count(), 7)
        widget.select_day(6)
        self.app.processEvents()
        self.assertEqual(widget.selected_day, 6)
        dialog = TaskDialog(widget.entries, 0)
        dialog.title_input.setText("Çakışma")
        dialog._save()
        self.assertIn("çakışıyor", dialog.error_label.text())
        self.assertIsNone(dialog.result_entry)
        dialog.day_input.setCurrentIndex(1)
        dialog._save()
        self.assertEqual(dialog.result_entry["day"], 1)
        widget.close()
        dialog.close()


if __name__ == "__main__":
    unittest.main()
