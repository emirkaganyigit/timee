"""Offscreen lifecycle checks across the session engine and real Qt dialogs."""

import copy
from datetime import date
import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, QTime, Qt, QTimer
from PySide6.QtWidgets import QApplication, QDialog, QPushButton

from mola.app import Window
from mola.engine import Engine
from mola.wellness import BreakDialog, EYE_ORDERS, MOVEMENT_IDS, normalize_rotation


class Clock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value


class MemoryStore:
    error = ""

    def __init__(self):
        self.data = {}

    def load(self):
        return copy.deepcopy(self.data)

    def save(self, data):
        self.data = copy.deepcopy(data)
        return True


class SessionDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.clock = Clock()
        self.store = MemoryStore()
        self.engine = Engine(self.clock, lambda: date(2026, 11, 9))
        self.window = Window(store=self.store, engine=self.engine)
        self.window.ticker.stop()
        self.window.saver.stop()
        self.window.preferences["reminder_sound"] = False
        self.time_patch = patch("mola.wellness.time.monotonic", self.clock)
        self.time_patch.start()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.time_patch.stop()

    def work(self, seconds):
        for _ in range(seconds):
            self.clock.value += 1
            self.window.pulse()

    def complete_kind(self, dialog, kind):
        """Run one selected reminder through its real timed dialog flow."""
        if dialog.active_kind != kind:
            dialog.kind_actions[kind]["start"].click()
        self.assertEqual(dialog.active_kind, kind)
        if dialog.started_at is None:
            dialog.primary.click()
        while dialog.outcomes[kind] is None:
            duration = dialog.duration
            self.clock.value += duration
            dialog.tick()
            if (dialog.outcomes[kind] is None and dialog.elapsed >= duration
                    and dialog.primary.isEnabled()):
                dialog.primary.click()

    def accept_goal_reset(self):
        """Accept the real confirmation dialog from its nested event loop."""
        self.assertTrue(self.window.goal_reset.isEnabled())
        confirmations = []

        def accept_confirmation():
            dialog = self.app.activeModalWidget()
            if not isinstance(dialog, QDialog):
                confirmations.append(None)
                return
            matches = [button for button in dialog.findChildren(QPushButton)
                       if button.text() == "Bugünü sıfırla"]
            confirmations.append((dialog.windowTitle(), len(matches)))
            if len(matches) == 1:
                matches[0].click()
            else:
                dialog.reject()

        QTimer.singleShot(0, accept_confirmation)
        self.window.goal_reset.click()
        self.assertEqual(confirmations, [("Bugünkü ilerlemeyi sıfırla", 1)])

    def test_combined_popup_pauses_until_whole_sequence_finishes_then_resumes(self):
        self.engine.eye_interval = 3
        self.engine.movement_interval = 4
        self.window.toggle_running()
        self.work(3)
        dialog = self.window.break_dialog
        self.assertIsNotNone(dialog)
        self.assertEqual(self.engine.state, "break")
        self.assertTrue(dialog.selector.isVisible())
        self.assertTrue(dialog.kind_cards["eye"].isVisible())
        self.assertTrue(dialog.kind_cards["movement"].isVisible())
        self.assertLess(dialog.kind_cards["eye"].y(), dialog.kind_cards["movement"].y())
        self.assertEqual(len([item for item, _ in dialog.steps if item["kind"] == "movement"]), 1)

        # The user chooses movement first even though eye is listed first.
        self.complete_kind(dialog, "movement")
        self.assertIs(self.window.break_dialog, dialog)
        self.assertTrue(dialog.kind_cards["eye"].isVisible())
        self.assertEqual(self.engine.state, "break")
        self.complete_kind(dialog, "eye")

        self.assertIsNone(self.window.break_dialog)
        self.assertEqual(self.engine.state, "running")
        self.assertTrue(self.engine.desk_active)
        self.assertEqual(self.engine.today_work, 3)
        self.assertEqual(self.engine.break_count, 1)
        self.work(1)
        self.assertEqual(self.engine.today_work, 4)
        self.assertEqual(self.engine.desk_elapsed, 4)

    def test_skip_and_window_close_resume_without_false_completion(self):
        self.engine.eye_interval = 3
        self.window.toggle_running()
        self.work(3)
        self.window.break_dialog.kind_actions["eye"]["skip"].click()
        self.assertEqual(self.engine.state, "running")
        self.assertEqual(self.engine.break_count, 0)
        self.work(2)
        self.assertIsNone(self.window.break_dialog)
        self.work(1)
        self.window.break_dialog.close()
        self.assertEqual(self.engine.state, "running")
        self.assertEqual(self.engine.break_count, 0)
        self.assertEqual(self.engine.since_eye, 0)

    def test_library_from_idle_never_starts_work_when_closed(self):
        self.window.open_exercise("distance")
        self.assertEqual(self.engine.state, "break")
        self.window.break_dialog.close()
        self.assertEqual(self.engine.state, "idle")
        self.assertEqual(self.engine.today_work, 0)

    def test_manual_exercise_at_reminder_boundary_opens_only_one_dialog(self):
        self.engine.eye_interval = 3
        self.window.toggle_running()
        self.clock.value += 3
        self.window.open_exercise("shoulders")
        first = self.window.break_dialog
        self.assertEqual(self.engine.pending_break, ("eye", "movement"))
        self.window.pulse()
        self.assertIs(self.window.break_dialog, first)
        self.assertEqual(len([d for d in self.window.findChildren(BreakDialog) if d.isVisible()]), 1)

    def test_save_triggered_reminder_is_delivered_by_next_pulse(self):
        self.engine.eye_interval = 3
        self.window.toggle_running()
        self.clock.value += 3
        self.window.save()
        self.assertEqual(self.engine.state, "break")
        self.assertIsNone(self.window.break_dialog)
        self.window.pulse()
        self.assertIsNotNone(self.window.break_dialog)
        first = self.window.break_dialog
        self.window.pulse()
        self.assertIs(self.window.break_dialog, first)

    def test_new_break_event_plays_one_calm_combined_chime(self):
        self.engine.eye_interval = 3
        self.engine.movement_interval = 4
        self.window.preferences["reminder_sound"] = True
        self.window.play_reminder_chime = Mock()
        self.window.toggle_running()
        self.work(3)
        self.window.play_reminder_chime.assert_called_once_with()
        self.assertEqual(self.engine.pending_break, ("eye", "movement"))

    def test_configurable_daily_reset_time_saves_from_settings(self):
        self.window.settings.day_reset.setTime(QTime(4, 35))
        self.window.settings.save_day_reset()
        self.assertEqual(self.engine.day_reset_minutes, 4 * 60 + 35)
        self.assertEqual(self.store.data["engine"]["day_reset_minutes"], 4 * 60 + 35)
        self.assertIn("04:35", self.window.settings.day_saved.text())

    def test_mini_buttons_control_same_session_and_close_preserves_running(self):
        self.window.open_mini()
        mini = self.window.mini
        self.assertTrue(mini.windowFlags() & Qt.WindowType.Tool)
        self.assertTrue(mini.windowFlags() & Qt.WindowType.FramelessWindowHint)
        self.assertTrue(mini.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        self.assertEqual((mini.width(), mini.height()), (300, 145))
        mini.toggle.click()
        self.work(2)
        self.assertEqual(self.engine.stopwatch_elapsed, 2)
        self.assertEqual(self.engine.desk_elapsed, 2)
        mini.toggle.click()
        self.work(2)
        self.assertEqual(self.engine.stopwatch_elapsed, 2)
        self.assertEqual(self.engine.desk_elapsed, 4)
        self.assertTrue(self.engine.desk_active)
        mini.desk_toggle.click()
        self.assertFalse(self.engine.desk_active)
        self.assertEqual(self.engine.state, "paused")
        mini.desk_toggle.click()
        self.assertTrue(self.engine.desk_active)
        mini.toggle.click()
        mini.close()
        self.assertEqual(self.engine.state, "running")
        self.work(1)
        self.assertEqual(self.engine.stopwatch_elapsed, 3)
        self.window.change_mode("timer")
        self.window.open_mini()
        self.assertEqual(mini.mode.text(), "ZAMANLAYICI")

    def test_work_pause_keeps_desk_cadence_until_explicit_desk_pause(self):
        self.engine.movement_interval = 60
        self.window.toggle_running()
        self.work(30)
        self.window.toggle_running()
        self.assertEqual(self.engine.state, "paused")
        self.assertTrue(self.engine.desk_active)
        self.work(10)
        self.assertEqual(self.engine.today_work, 30)
        self.assertEqual(self.engine.desk_elapsed, 40)
        self.assertEqual(self.engine.since_movement, 40)
        self.assertEqual(self.engine.next_movement, 20)

        self.window.toggle_desk()
        self.work(10)
        self.assertFalse(self.engine.desk_active)
        self.assertEqual(self.engine.desk_elapsed, 40)
        self.assertEqual(self.engine.next_movement, 20)

    def test_mini_accepts_small_resize_and_restores_saved_size(self):
        self.window.open_mini()
        mini = self.window.mini
        mini.resize(236, 126)
        self.app.processEvents()
        self.assertEqual((mini.width(), mini.height()), (236, 126))
        self.assertEqual(self.window.preferences["mini_size"], [236, 126])
        mini.close()
        self.assertEqual(self.store.data["preferences"]["mini_size"], [236, 126])

        restored_engine = Engine(self.clock, lambda: date(2026, 11, 9))
        restored = Window(store=self.store, engine=restored_engine)
        restored.ticker.stop()
        restored.saver.stop()
        try:
            restored.open_mini()
            self.app.processEvents()
            self.assertEqual((restored.mini.width(), restored.mini.height()), (236, 126))
        finally:
            restored.close()
            restored.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_goal_and_timer_completion_stay_paused_with_no_exercise(self):
        self.window.change_mode("timer")
        self.engine.set_timer(3)
        self.engine.goal_enabled = True
        self.engine.goal_seconds = 3
        self.engine.eye_interval = 100
        self.window.toggle_running()
        self.work(3)
        self.assertEqual(self.engine.state, "paused")
        self.assertEqual(self.engine.timer_remaining, 0)
        self.assertIsNone(self.window.break_dialog)
        self.assertIsNotNone(self.window.notice)
        self.window.notice.accept()
        self.work(2)
        self.assertEqual(self.engine.today_work, 3)
        self.assertEqual(self.engine.state, "paused")

    def test_confirmed_goal_reset_preserves_work_counters_and_reminder_cadence(self):
        self.engine.goal_enabled = True
        self.engine.goal_seconds = 60
        self.window.toggle_running()
        self.work(5)
        self.window.change_mode("timer")
        self.engine.set_timer(180)
        self.window.toggle_running()
        self.work(7)
        self.engine.break_count = 2
        self.window.refresh()
        before = self.engine.snapshot()
        self.assertEqual(self.engine.goal_work, 12)
        self.assertEqual(self.engine.stopwatch_elapsed, 5)
        self.assertEqual(self.engine.timer_remaining, 173)
        self.assertEqual(self.engine.since_eye, 12)
        self.assertEqual(self.engine.since_movement, 12)

        self.accept_goal_reset()

        after = self.engine.snapshot()
        self.assertEqual(self.engine.goal_work, 0)
        self.assertEqual(self.engine.remaining_goal, 60)
        self.assertEqual(after["goal_baseline"], before["today_work"])
        for key, value in before.items():
            if key not in ("goal_baseline", "saved_at"):
                with self.subTest(preserved=key):
                    self.assertEqual(after[key], value)
        self.assertEqual(self.window.goal_progress.value(), 0)
        self.assertFalse(self.window.goal_reset.isEnabled())
        self.assertEqual(
            {key: value for key, value in self.store.data["engine"].items() if key != "saved_at"},
            {key: value for key, value in after.items() if key != "saved_at"},
        )

        self.work(2)
        self.assertEqual(self.engine.goal_work, 2)
        self.assertEqual(self.engine.today_work, 14)
        self.assertEqual(self.engine.stopwatch_elapsed, 5)
        self.assertEqual(self.engine.timer_remaining, 171)
        self.assertEqual(self.engine.since_eye, 14)
        self.assertEqual(self.engine.since_movement, 14)
        self.assertEqual(self.engine.break_count, 2)

    def test_delayed_goal_notice_is_ignored_after_confirmed_reset(self):
        self.engine.goal_enabled = True
        self.engine.goal_seconds = 3
        self.window.toggle_running()
        self.work(3)
        self.assertIsNotNone(self.window.notice)
        self.window.notice.accept()
        self.assertIsNone(self.window.notice)

        self.accept_goal_reset()
        QTimer.singleShot(0, lambda: self.window.show_notice(
            "Bugünkü hedefine ulaştın.", "Gecikmiş hedef bildirimi", "goal"
        ))
        self.app.processEvents()
        self.assertEqual(self.engine.goal_work, 0)
        self.assertEqual(self.engine.today_work, 3)
        self.assertEqual(self.engine.state, "paused")
        self.assertIsNone(self.window.notice)

    def test_completion_notice_is_deferred_until_manual_exercise_closes(self):
        self.window.change_mode("timer")
        self.engine.set_timer(3)
        self.window.toggle_running()
        self.clock.value += 3
        self.window.open_exercise("shoulders")
        self.window.pulse()
        self.assertEqual(self.engine.state, "break")
        self.assertIsNotNone(self.window.break_dialog)
        self.assertIsNone(self.window.notice)
        self.window.break_dialog.skip.click()
        self.app.processEvents()
        self.assertIsNotNone(self.window.notice)
        self.assertEqual(self.engine.state, "paused")
        self.assertEqual(self.engine.today_work, 3)

    def test_first_launch_starts_idle(self):
        fresh = Window(store=MemoryStore())
        fresh.ticker.stop()
        fresh.saver.stop()
        try:
            self.assertEqual(fresh.engine.state, "idle")
            self.assertEqual(fresh.engine.today_work, 0)
        finally:
            fresh.close()
            fresh.deleteLater()

    def test_closing_main_window_during_break_cannot_resume_in_background(self):
        self.window.toggle_running()
        self.work(2)
        self.window.open_exercise("distance")
        self.window.close()
        self.assertEqual(self.engine.state, "paused")
        self.assertIsNone(self.window.break_dialog)
        self.assertEqual(self.engine.today_work, 2)
        self.assertEqual(self.engine.break_count, 0)
        self.assertEqual(self.store.data["engine"]["state"], "paused")

    def test_shutdown_drops_deferred_completion_notice(self):
        self.window.change_mode("timer")
        self.engine.set_timer(3)
        self.window.toggle_running()
        self.clock.value += 3
        self.window.open_exercise("shoulders")
        self.window.pulse()
        self.assertIsNone(self.window.notice)
        self.window.close()
        self.app.processEvents()
        self.assertTrue(self.window.notice is None or not self.window.notice.isVisible())
        self.assertEqual(self.engine.state, "paused")

    def test_manual_movement_selection_updates_duration_before_start(self):
        self.window.open_exercise("shoulders")
        dialog = self.window.break_dialog
        self.assertEqual(dialog.duration, 25)
        dialog.chooser.setCurrentIndex(dialog.chooser.findData("walk"))
        self.assertEqual(dialog.duration, 300)
        self.assertEqual(dialog.item["id"], "walk")
        dialog.primary.click()
        self.assertFalse(dialog.chooser.isEnabled())

    def test_automatic_movement_offers_one_exercise_and_can_snooze(self):
        self.engine.eye_enabled = False
        self.engine.movement_interval = 3
        self.window.toggle_running()
        self.work(3)
        dialog = self.window.break_dialog
        self.assertEqual(len(dialog.steps), 1)
        self.assertEqual(dialog.steps[0][0]["kind"], "movement")
        self.assertTrue(dialog.selector.isVisible())
        self.assertIn("snooze", dialog.kind_actions["movement"])
        dialog.kind_actions["movement"]["snooze"].click()
        self.assertIsNone(self.window.break_dialog)
        self.assertEqual(self.engine.state, "running")
        self.assertTrue(self.engine.desk_active)
        self.assertEqual(self.engine.next_movement, 600)
        self.assertEqual(self.engine.break_count, 0)
        self.work(1)
        self.assertEqual(self.engine.next_movement, 599)

    def test_movement_acknowledgement_resets_normal_interval_and_counts_break(self):
        self.engine.eye_enabled = False
        self.engine.movement_interval = 30
        self.window.toggle_running()
        self.work(30)
        dialog = self.window.break_dialog
        dialog.kind_actions["movement"]["acknowledged"].click()
        self.assertIsNone(self.window.break_dialog)
        self.assertEqual(self.engine.state, "running")
        self.assertEqual(self.engine.next_movement, 30)
        self.assertEqual(self.engine.break_count, 1)

    def test_automatic_movement_single_exercise_completes_and_resumes(self):
        self.engine.eye_enabled = False
        self.engine.movement_interval = 3
        self.window.toggle_running()
        self.work(3)
        dialog = self.window.break_dialog
        dialog.kind_actions["movement"]["start"].click()
        self.assertTrue(dialog.chooser.isHidden())
        self.assertEqual(len(dialog.steps), 1)
        self.complete_kind(dialog, "movement")
        self.assertIsNone(self.window.break_dialog)
        self.assertEqual(self.engine.state, "running")
        self.assertEqual(self.engine.break_count, 1)
        self.assertEqual(self.engine.today_work, 3)

    def test_skipped_automatic_break_advances_rotation_only_once(self):
        self.engine.eye_enabled = False
        self.engine.movement_interval = 3
        self.window.toggle_running()
        self.work(3)
        first = self.window.break_dialog
        first_ids = [item["id"] for item, _ in first.steps]
        saved_rotation = copy.deepcopy(self.store.data["exercise_rotation"])
        self.assertEqual(saved_rotation["movement"], 1)
        self.assertEqual(saved_rotation["eye"], 0)

        self.window.open_break()
        self.window.pulse()
        self.window.save()
        self.assertIs(self.window.break_dialog, first)
        self.assertEqual(self.store.data["exercise_rotation"], saved_rotation)

        first.kind_actions["movement"]["skip"].click()
        self.assertEqual(self.engine.break_count, 0)
        self.window.open_break()  # No pending break must not consume a routine.
        self.work(3)
        second = self.window.break_dialog
        second_ids = [item["id"] for item, _ in second.steps]
        self.assertNotEqual(first_ids[0], second_ids[0])
        self.assertEqual(second_ids[0], MOVEMENT_IDS[1])
        self.assertEqual(self.store.data["exercise_rotation"]["movement"], 2)
        self.assertEqual(self.store.data["exercise_rotation"]["eye"], 0)

    def test_eye_sequence_rotates_and_advances_without_next_click(self):
        self.engine.movement_enabled = False
        self.engine.eye_interval = 3
        self.window.toggle_running()
        self.work(3)
        first = self.window.break_dialog
        self.assertEqual(tuple(item["id"] for item, _ in first.steps), EYE_ORDERS[0])
        self.assertEqual(sum(duration for _, duration in first.steps), 30)
        first.kind_actions["eye"]["start"].click()
        first.primary.click()
        self.assertTrue(first.animation.timer.isActive())
        self.assertFalse(first.primary.isEnabled())
        self.clock.value += first.duration
        first.tick()
        self.assertEqual(first.active_position, 1)
        self.assertFalse(first.primary.isEnabled())
        self.assertIs(self.window.break_dialog, first)
        self.clock.value += first.duration
        first.tick()
        self.assertIsNone(self.window.break_dialog)
        self.work(3)
        second = self.window.break_dialog
        self.assertEqual(tuple(item["id"] for item, _ in second.steps), EYE_ORDERS[1])
        self.assertEqual(self.store.data["exercise_rotation"]["movement"], 0)
        self.assertEqual(self.store.data["exercise_rotation"]["eye"], 2)

    def test_manual_exercise_does_not_consume_automatic_rotation(self):
        self.window.save()
        before = copy.deepcopy(self.store.data["exercise_rotation"])
        self.window.open_exercise("shoulders")
        dialog = self.window.break_dialog
        self.assertEqual([item["id"] for item, _ in dialog.steps], ["shoulders"])
        self.assertFalse(dialog.chooser.isHidden())
        self.complete_kind(dialog, "movement")
        self.assertEqual(self.engine.state, "idle")
        self.assertEqual(self.store.data["exercise_rotation"], before)

    def test_rotation_survives_window_recreation_after_skipped_break(self):
        self.engine.eye_enabled = False
        self.engine.movement_interval = 3
        self.window.toggle_running()
        self.work(3)
        self.window.break_dialog.kind_actions["movement"]["skip"].click()
        self.window.close()
        persisted = copy.deepcopy(self.store.data)
        self.assertEqual(persisted["exercise_rotation"]["movement"], 1)

        restored_store = MemoryStore()
        restored_store.data = persisted
        restored_engine = Engine(self.clock, lambda: date(2026, 11, 9))
        restored_engine.eye_enabled = False
        restored_engine.movement_interval = 3
        restored = Window(store=restored_store, engine=restored_engine)
        restored.ticker.stop()
        restored.saver.stop()
        restored.preferences["reminder_sound"] = False
        try:
            restored.toggle_running()
            for _ in range(3):
                self.clock.value += 1
                restored.pulse()
            self.assertIsNotNone(restored.break_dialog)
            self.assertEqual(restored.break_dialog.steps[0][0]["id"], MOVEMENT_IDS[1])
            self.assertEqual(restored_store.data["exercise_rotation"]["movement"], 2)
        finally:
            restored.close()
            restored.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_bad_saved_rotation_recovers_without_preventing_breaks(self):
        invalid_store = MemoryStore()
        invalid_store.data = {"exercise_rotation": {"eye": True, "movement": "bad"}}
        recovered_engine = Engine(self.clock, lambda: date(2026, 11, 9))
        recovered_engine.eye_enabled = False
        recovered_engine.movement_interval = 3
        recovered = Window(store=invalid_store, engine=recovered_engine)
        recovered.ticker.stop()
        recovered.saver.stop()
        recovered.preferences["reminder_sound"] = False
        try:
            recovered.save()
            self.assertEqual(invalid_store.data["exercise_rotation"], normalize_rotation(None))
            recovered.toggle_running()
            for _ in range(3):
                self.clock.value += 1
                recovered.pulse()
            self.assertIsNotNone(recovered.break_dialog)
            self.assertEqual(recovered.break_dialog.steps[0][0]["id"], MOVEMENT_IDS[0])
        finally:
            recovered.close()
            recovered.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_combined_break_can_skip_both_independently(self):
        self.engine.eye_interval = 3
        self.engine.movement_interval = 4
        self.window.toggle_running()
        self.work(3)
        dialog = self.window.break_dialog
        dialog.kind_actions["movement"]["skip"].click()
        self.assertIs(self.window.break_dialog, dialog)
        self.assertEqual(self.engine.state, "break")
        dialog.kind_actions["eye"]["skip"].click()
        self.assertEqual(self.engine.state, "running")
        self.assertEqual(self.engine.break_count, 0)
        self.assertEqual(self.engine.today_work, 3)
        self.assertIsNone(self.window.break_dialog)


if __name__ == "__main__":
    unittest.main()
