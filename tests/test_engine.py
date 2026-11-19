import json
import math
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch

from mola.engine import Engine, default_clock


class Clock:
    def __init__(self):
        self.time = 100.0
        self.wall = 1_700_000_000.0
        self.day = date(2026, 11, 9)
        self.moment = datetime(2026, 11, 9, 12, 0)

    def __call__(self):
        return self.time


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.engine = self.new_engine()

    def new_engine(self):
        return Engine(self.clock, lambda: self.clock.day, wall_clock=lambda: self.clock.wall)

    def elapse(self, seconds):
        """Move both clocks without ticking, as during inactivity or shutdown."""
        self.clock.time += seconds
        self.clock.wall += seconds

    def advance(self, seconds):
        events = []
        while seconds > 0:
            step = min(seconds, 1)
            self.elapse(step)
            events.extend(self.engine.tick())
            seconds -= step
        return events

    def timed_engine(self, moment):
        self.clock.moment = moment
        return Engine(
            self.clock,
            lambda: self.clock.moment.date(),
            wall_clock=lambda: self.clock.wall,
            now=lambda: self.clock.moment,
        )

    def timed_tick(self, engine, seconds=1):
        self.clock.time += seconds
        self.clock.wall += seconds
        self.clock.moment += timedelta(seconds=seconds)
        return engine.tick()

    def test_stopwatch_credits_only_active_work(self):
        self.engine.start()
        self.advance(10)
        self.engine.pause()
        self.advance(50)
        self.engine.start()
        self.advance(7)
        self.assertEqual(self.engine.stopwatch_elapsed, 17)
        self.assertEqual(self.engine.today_work, 17)
        self.assertEqual(self.engine.total_work, 17)
        self.assertEqual(self.engine.desk_elapsed, 67)
        self.assertEqual(self.engine.since_movement, 67)

    def test_desk_controls_are_independent_from_work_pause(self):
        self.engine.eye_interval = 10_000
        self.engine.movement_interval = 10_000
        self.engine.start()
        self.advance(30)
        self.engine.pause()
        self.advance(10)
        self.assertEqual(self.engine.today_work, 30)
        self.assertEqual(self.engine.desk_elapsed, 40)
        self.assertEqual(self.engine.desk_state, "running")

        self.engine.pause_desk()
        self.advance(20)
        self.assertEqual(self.engine.desk_elapsed, 40)
        self.assertEqual(self.engine.since_movement, 40)
        self.assertEqual(self.engine.desk_state, "paused")
        self.assertTrue(self.engine.start_desk())
        self.advance(5)
        self.assertEqual(self.engine.today_work, 30)
        self.assertEqual(self.engine.desk_elapsed, 45)
        self.assertEqual(self.engine.state, "paused")

    def test_leaving_desk_pauses_active_work_but_never_resets_cadence(self):
        self.engine.start()
        self.advance(15)
        self.engine.pause_desk()
        self.assertEqual(self.engine.state, "paused")
        self.assertFalse(self.engine.desk_active)
        self.advance(30)
        self.assertEqual(self.engine.today_work, 15)
        self.assertEqual(self.engine.since_eye, 15)
        self.assertEqual(self.engine.since_movement, 15)

    def test_resetting_visible_desk_timer_preserves_reminders(self):
        self.engine.start()
        self.advance(12)
        self.engine.reset_desk_elapsed()
        self.assertEqual(self.engine.desk_elapsed, 0)
        self.assertEqual(self.engine.since_eye, 12)
        self.assertEqual(self.engine.since_movement, 12)
        self.assertTrue(self.engine.desk_active)

    def test_work_pause_keeps_independent_desk_clock_running(self):
        self.engine.start()
        self.advance(10)
        self.engine.pause()
        self.advance(299)
        self.assertTrue(self.engine.start())
        self.assertEqual(self.engine.since_eye, 309)
        self.assertEqual(self.engine.since_movement, 309)
        self.assertEqual(self.engine.desk_elapsed, 309)
        self.advance(1)
        self.assertEqual(self.engine.since_eye, 310)
        self.assertEqual(self.engine.today_work, 11)

    def test_five_minute_work_pause_never_claims_a_break(self):
        self.engine.goal_enabled = True
        self.engine.goal_seconds = 1000
        self.engine.start()
        self.advance(7)
        self.engine.switch_mode("timer")
        self.engine.set_timer(100)
        self.engine.start()
        self.advance(13)
        self.engine.pause()
        self.advance(300)
        self.assertTrue(self.engine.start())
        self.assertEqual(self.engine.since_eye, 320)
        self.assertEqual(self.engine.since_movement, 320)
        self.assertEqual(self.engine.stopwatch_elapsed, 7)
        self.assertEqual(self.engine.timer_remaining, 87)
        self.assertEqual(self.engine.today_work, 20)
        self.assertEqual(self.engine.total_work, 20)
        self.assertEqual(self.engine.remaining_goal, 980)
        self.advance(1)
        self.assertEqual(self.engine.since_eye, 321)
        self.assertEqual(self.engine.timer_remaining, 86)
        self.assertEqual(self.engine.remaining_goal, 979)

    def test_separate_work_pauses_accumulate_as_desk_presence(self):
        self.engine.start()
        self.advance(10)
        self.engine.pause()
        self.advance(200)
        self.engine.start()
        self.advance(1)
        self.engine.pause()
        self.advance(200)
        self.engine.start()
        self.assertEqual(self.engine.since_eye, 411)
        self.assertEqual(self.engine.since_movement, 411)
        self.assertEqual(self.engine.today_work, 11)

    def test_work_controls_do_not_reset_desk_reminder_cadence(self):
        self.engine.start()
        self.advance(10)
        self.engine.pause()
        self.advance(120)
        self.engine.pause()
        self.engine.reset_current()
        self.advance(100)
        self.engine.switch_mode("timer")
        self.engine.set_timer(600)
        self.advance(80)
        self.engine.start()
        self.assertEqual(self.engine.since_eye, 310)
        self.assertEqual(self.engine.since_movement, 310)
        self.assertEqual(self.engine.today_work, 10)
        self.assertEqual(self.engine.timer_remaining, 600)

    def test_controls_sync_partial_tick_without_losing_events(self):
        self.engine.eye_interval = 1
        self.engine.start()
        self.clock.time += 1.25
        self.engine.pause()
        self.assertEqual(self.engine.today_work, 1)
        self.assertEqual(self.engine.tick(), ["break"])
        self.assertEqual(self.engine.tick(), [])
        self.engine.finish_break()
        self.assertEqual(self.engine.state, "paused")

    def test_automatic_break_pauses_and_resumes(self):
        self.engine.eye_interval = 10
        self.engine.start()
        self.assertEqual(self.advance(10), ["break"])
        self.assertEqual(self.engine.state, "break")
        self.assertEqual(self.engine.pending_break, ("eye",))
        self.advance(20)
        self.assertEqual(self.engine.today_work, 10)
        self.engine.finish_break()
        self.assertEqual(self.engine.state, "running")
        self.assertEqual(self.engine.since_eye, 0)
        self.advance(2)
        self.assertEqual(self.engine.today_work, 12)

    def test_manual_break_from_paused_or_idle_does_not_start_work(self):
        self.engine.begin_break(("movement",))
        self.engine.finish_break()
        self.assertEqual(self.engine.state, "idle")
        self.engine.start()
        self.advance(2)
        self.engine.pause()
        self.engine.begin_break(("eye",))
        self.advance(20)
        self.engine.finish_break()
        self.assertEqual(self.engine.state, "paused")
        self.assertEqual(self.engine.today_work, 2)

    def test_simultaneous_reminders_share_one_break(self):
        self.engine.eye_interval = 10
        self.engine.movement_interval = 10
        self.engine.start()
        self.assertEqual(self.advance(10), ["break"])
        self.assertEqual(self.engine.pending_break, ("eye", "movement"))
        self.engine.finish_break()
        self.assertEqual(self.engine.since_eye, 0)
        self.assertEqual(self.engine.since_movement, 0)
        self.assertEqual(self.engine.break_count, 1)

    def test_movement_snooze_waits_ten_more_desk_minutes(self):
        self.engine.eye_enabled = False
        self.engine.movement_interval = 3
        self.engine.start()
        self.assertEqual(self.advance(3), ["break"])
        self.engine.snooze_movement()
        self.assertEqual(self.engine.pending_break, ())
        self.assertEqual(self.engine.state, "running")
        self.assertTrue(self.engine.desk_active)
        self.assertEqual(self.engine.movement_snooze_remaining, 600)
        self.assertEqual(self.engine.since_movement, 3)
        self.assertEqual(self.advance(599), [])
        self.assertEqual(self.engine.movement_snooze_remaining, 1)
        self.assertEqual(self.advance(1), ["break"])
        self.assertEqual(self.engine.pending_break, ("movement",))

    def test_snoozing_movement_in_combined_popup_leaves_eye_choice_visible(self):
        self.engine.eye_interval = 3
        self.engine.movement_interval = 3
        self.engine.start()
        self.assertEqual(self.advance(3), ["break"])
        self.engine.snooze_movement(600)
        self.assertEqual(self.engine.pending_break, ("eye",))
        self.assertEqual(self.engine.state, "break")
        self.assertFalse(self.engine.desk_active)
        self.engine.finish_break(completed=False, kinds=("eye",))
        self.assertEqual(self.engine.state, "running")
        self.assertTrue(self.engine.desk_active)
        self.assertEqual(self.engine.since_eye, 0)
        self.assertEqual(self.engine.since_movement, 3)
        self.assertEqual(self.engine.movement_snooze_remaining, 600)

    def test_acknowledging_movement_restarts_normal_interval(self):
        self.engine.eye_enabled = False
        self.engine.movement_interval = 3
        self.engine.start()
        self.assertEqual(self.advance(3), ["break"])
        self.engine.acknowledge_movement()
        self.assertEqual(self.engine.state, "running")
        self.assertEqual(self.engine.since_movement, 0)
        self.assertEqual(self.engine.movement_snooze_remaining, 0)
        self.assertEqual(self.engine.break_count, 1)
        self.assertEqual(self.advance(2), [])
        self.assertEqual(self.advance(1), ["break"])

    def test_default_reminders_align_at_sixty_minutes_of_work(self):
        self.engine.start()
        self.advance(1200)
        self.engine.finish_break()
        self.advance(1200)
        self.engine.finish_break()
        self.advance(1200)
        self.assertEqual(self.engine.pending_break, ("eye", "movement"))
        self.assertEqual(self.engine.today_work, 3600)

    def test_close_custom_reminders_coalesce_when_first_is_due(self):
        self.engine.eye_interval = 20 * 60
        self.engine.movement_interval = 21 * 60
        self.engine.start()
        self.assertEqual(self.advance(19 * 60), [])
        self.assertEqual(self.advance(60), ["break"])
        self.assertEqual(self.engine.pending_break, ("eye", "movement"))
        self.engine.finish_break()
        self.assertEqual(self.advance(60), [])
        self.assertEqual(self.engine.break_count, 1)

    def test_movement_first_can_coalesce_upcoming_eye_reminder(self):
        self.engine.eye_interval = 23 * 60
        self.engine.movement_interval = 20 * 60
        self.engine.start()
        self.assertEqual(self.advance(20 * 60), ["break"])
        self.assertEqual(self.engine.pending_break, ("eye", "movement"))

    def test_reminder_outside_coalescing_window_stays_separate(self):
        self.engine.eye_interval = 20 * 60
        self.engine.movement_interval = 23 * 60 + 1
        self.engine.start()
        self.assertEqual(self.advance(20 * 60), ["break"])
        self.assertEqual(self.engine.pending_break, ("eye",))
        self.engine.finish_break()
        self.assertEqual(self.advance(181), ["break"])
        self.assertEqual(self.engine.pending_break, ("movement",))

    def test_disabled_reminder_is_not_added_to_combined_break(self):
        self.engine.eye_interval = 20 * 60
        self.engine.movement_interval = 60
        self.engine.movement_enabled = False
        self.engine.start()
        self.assertEqual(self.advance(20 * 60), ["break"])
        self.assertEqual(self.engine.pending_break, ("eye",))

    def test_switch_preserves_counters_and_only_one_mode_runs(self):
        self.engine.start()
        self.advance(4)
        self.engine.switch_mode("timer")
        self.assertEqual(self.engine.state, "paused")
        self.engine.set_timer(20)
        self.engine.start()
        self.advance(3)
        self.assertEqual(self.engine.stopwatch_elapsed, 4)
        self.assertEqual(self.engine.timer_remaining, 17)
        self.assertEqual(self.engine.today_work, 7)

    def test_goal_decreases_for_both_modes_and_cuts_at_boundary(self):
        self.engine.goal_enabled = True
        self.engine.goal_seconds = 7.5
        self.engine.start()
        self.advance(4)
        self.engine.switch_mode("timer")
        self.engine.set_timer(20)
        self.engine.start()
        self.assertEqual(self.advance(4), ["goal_done"])
        self.assertEqual(self.engine.today_work, 7.5)
        self.assertEqual(self.engine.timer_remaining, 16.5)
        self.assertEqual(self.engine.remaining_goal, 0)
        self.assertFalse(self.engine.start())
        self.advance(5)
        self.assertEqual(self.engine.total_work, 7.5)

    def test_reset_goal_progress_preserves_work_timers_reminders_and_breaks(self):
        self.engine.goal_enabled = True
        self.engine.goal_seconds = 1000
        self.engine.break_count = 2
        self.engine.start()
        self.advance(7)
        self.engine.switch_mode("timer")
        self.engine.set_timer(100)
        self.engine.start()
        self.advance(13)

        self.engine.reset_goal_progress()

        self.assertEqual(self.engine.goal_work, 0)
        self.assertEqual(self.engine.remaining_goal, 1000)
        self.assertEqual(self.engine.today_work, 20)
        self.assertEqual(self.engine.total_work, 20)
        self.assertEqual(self.engine.stopwatch_elapsed, 7)
        self.assertEqual(self.engine.timer_remaining, 87)
        self.assertEqual(self.engine.since_eye, 20)
        self.assertEqual(self.engine.since_movement, 20)
        self.assertEqual(self.engine.break_count, 2)
        self.assertEqual(self.engine.state, "running")

        self.advance(1)
        self.assertEqual(self.engine.goal_work, 1)
        self.assertEqual(self.engine.today_work, 21)
        saved = self.engine.snapshot()
        restored = self.new_engine()
        restored.restore(saved)
        self.assertEqual(restored.goal_work, 1)
        self.assertEqual(restored.today_work, 21)

    def test_reset_at_goal_boundary_clears_stale_completion_and_unlocks_goal(self):
        self.engine.goal_enabled = True
        self.engine.goal_seconds = 3
        self.engine.start()
        self.elapse(3)
        self.engine.reset_goal_progress()
        self.assertEqual(self.engine.state, "paused")
        self.assertEqual(self.engine.today_work, 3)
        self.assertEqual(self.engine.goal_work, 0)
        self.assertEqual(self.engine.remaining_goal, 3)
        self.assertEqual(self.engine.tick(), [])
        self.assertTrue(self.engine.start())

    def test_timer_finishes_before_reminder_and_can_restart(self):
        self.engine.switch_mode("timer")
        self.engine.set_timer(10)
        self.engine.eye_interval = 10
        self.engine.start()
        self.assertEqual(self.advance(10), ["timer_done"])
        self.assertEqual(self.engine.pending_break, ())
        self.assertEqual(self.engine.today_work, 10)
        self.assertEqual(self.engine.timer_remaining, 0)
        self.assertEqual(self.engine.state, "paused")
        # Desk presence remains active, so the due eye reminder is delivered
        # independently on the next scheduler tick.
        self.assertEqual(self.advance(1), ["break"])
        self.assertEqual(self.engine.pending_break, ("eye",))
        self.engine.finish_break()
        self.assertTrue(self.engine.start())
        self.assertEqual(self.engine.timer_remaining, 10)

    def test_time_away_from_desk_does_not_claim_an_eye_break(self):
        self.engine.switch_mode("timer")
        self.engine.set_timer(10)
        self.engine.eye_interval = 10
        self.engine.start()
        self.assertEqual(self.advance(10), ["timer_done"])
        self.engine.pause_desk()
        self.elapse(300)
        self.assertTrue(self.engine.start_desk())
        self.assertEqual(self.engine.since_eye, 10)
        self.assertEqual(self.engine.since_movement, 10)
        self.assertEqual(self.advance(1), ["break"])
        self.assertEqual(self.engine.pending_break, ("eye",))
        self.assertEqual(self.engine.timer_remaining, 0)
        self.assertEqual(self.engine.today_work, 10)

    def test_goal_and_timer_complete_together_without_popup(self):
        self.engine.switch_mode("timer")
        self.engine.set_timer(4)
        self.engine.goal_enabled = True
        self.engine.goal_seconds = 4
        self.engine.eye_interval = 4
        self.engine.start()
        self.assertEqual(self.advance(4), ["goal_done", "timer_done"])
        self.assertEqual(self.engine.pending_break, ())

    def test_enabling_an_already_met_goal_stops_without_crediting_more(self):
        self.engine.start()
        self.advance(10)
        self.engine.goal_seconds = 5
        self.engine.goal_enabled = True
        self.assertEqual(self.advance(1), ["goal_done"])
        self.assertEqual(self.engine.today_work, 10)
        self.assertEqual(self.engine.state, "paused")
        self.engine.goal_enabled = False
        self.assertEqual(self.engine.state, "paused")
        self.assertTrue(self.engine.start())
        self.advance(2)
        self.assertEqual(self.engine.today_work, 12)

    def test_new_day_unlocks_completed_goal_without_starting_automatically(self):
        self.engine.goal_seconds = 5
        self.engine.goal_enabled = True
        self.engine.start()
        self.advance(5)
        self.clock.day += timedelta(days=1)
        self.assertEqual(self.engine.tick(), ["day_changed"])
        self.assertEqual(self.engine.state, "paused")
        self.assertEqual(self.engine.remaining_goal, 5)
        self.assertTrue(self.engine.start())

    def test_large_monotonic_gap_excludes_suspend_time(self):
        self.engine.start()
        self.advance(3)
        self.clock.time += 100
        self.assertEqual(self.engine.tick(), ["suspended"])
        self.assertEqual(self.engine.today_work, 3)
        self.assertEqual(self.engine.state, "paused")
        self.assertFalse(self.engine.desk_active)
        self.assertEqual(self.engine.tick(), [])

    def test_suspend_pauses_desk_without_faking_a_completed_break(self):
        self.engine.start()
        self.advance(10)
        self.elapse(300)
        self.assertEqual(self.engine.tick(), ["suspended"])
        self.assertEqual(self.engine.state, "paused")
        self.assertFalse(self.engine.desk_active)
        self.assertEqual(self.engine.since_eye, 10)
        self.assertEqual(self.engine.since_movement, 10)
        self.assertEqual(self.engine.today_work, 10)
        self.assertEqual(self.engine.stopwatch_elapsed, 10)
        self.engine.start()
        self.assertEqual(self.advance(1), [])
        self.assertEqual(self.engine.since_eye, 11)

    def test_time_after_suspend_never_changes_reminders_while_desk_is_paused(self):
        self.engine.start()
        self.advance(10)
        self.elapse(100)
        self.assertEqual(self.engine.tick(), ["suspended"])
        self.assertEqual(self.engine.since_eye, 10)
        self.elapse(200)
        self.engine.start()
        self.assertEqual(self.engine.since_eye, 10)
        self.assertEqual(self.engine.since_movement, 10)
        self.assertEqual(self.engine.today_work, 10)

    def test_linux_default_clock_detects_system_suspend(self):
        with patch("mola.engine.time.CLOCK_BOOTTIME", 7, create=True), \
                patch("mola.engine.time.clock_gettime", side_effect=[100, 100, 200], create=True) as boot:
            engine = Engine()
            engine.start()
            self.assertEqual(engine.tick(), ["suspended"])
            self.assertEqual(engine.today_work, 0)
            self.assertEqual(engine.state, "paused")
            boot.assert_called_with(7)

    def test_default_clock_falls_back_when_boottime_unavailable(self):
        with patch("mola.engine.time.CLOCK_BOOTTIME", None, create=True), \
                patch("mola.engine.time.monotonic", return_value=123.5):
            self.assertEqual(default_clock(), 123.5)
        with patch("mola.engine.time.CLOCK_BOOTTIME", 7, create=True), \
                patch("mola.engine.time.clock_gettime", side_effect=OSError, create=True), \
                patch("mola.engine.time.monotonic", return_value=456.0):
            self.assertEqual(default_clock(), 456.0)

    def test_reset_does_not_erase_work_or_defeat_reminders(self):
        self.engine.start()
        self.advance(4)
        self.engine.reset_current()
        self.assertEqual(self.engine.stopwatch_elapsed, 0)
        self.assertEqual(self.engine.today_work, 4)
        self.assertEqual(self.engine.since_eye, 4)
        self.assertEqual(self.engine.state, "idle")

    def test_persistence_never_resumes_unattended(self):
        self.engine.start()
        self.advance(8)
        saved = json.loads(json.dumps(self.engine.snapshot(), allow_nan=False))
        self.clock.time += 500
        new = self.new_engine()
        new.restore(saved)
        self.assertEqual(new.state, "paused")
        self.assertFalse(new.desk_active)
        self.assertEqual(new.desk_elapsed, 8)
        self.assertEqual(new.tick(), [])
        self.assertEqual(new.today_work, 8)
        self.assertEqual(new.stopwatch_elapsed, 8)
        self.assertEqual(new.pending_break, ())

    def test_immediate_reopen_preserves_cadence_and_never_resumes_itself(self):
        self.engine.start()
        self.advance(10)
        self.engine.pause()
        saved = self.engine.snapshot()
        new = self.new_engine()
        new.restore(saved)
        self.assertEqual(new.state, "paused")
        self.assertEqual(new.since_eye, 10)
        self.assertEqual(new.since_movement, 10)
        self.assertTrue(new.start())
        self.assertEqual(new.since_eye, 10)
        self.assertEqual(new.today_work, 10)

    def test_offline_time_never_resets_cadence_across_reboot(self):
        self.engine.goal_enabled = True
        self.engine.goal_seconds = 1000
        self.engine.start()
        self.advance(10)
        self.engine.pause()
        self.elapse(120)
        saved = json.loads(json.dumps(self.engine.snapshot()))
        self.clock.wall += 180
        self.clock.time = 2  # A reboot gives BOOTTIME a different origin.
        new = self.new_engine()
        new.restore(saved)
        self.assertEqual(new.state, "paused")
        self.assertFalse(new.desk_active)
        self.assertTrue(new.start())
        self.assertEqual(new.since_eye, 10)
        self.assertEqual(new.since_movement, 10)
        self.assertEqual(new.stopwatch_elapsed, 10)
        self.assertEqual(new.today_work, 10)
        self.assertEqual(new.total_work, 10)
        self.assertEqual(new.remaining_goal, 990)

    def test_offline_duration_never_advances_or_resets_desk_cadence(self):
        self.engine.start()
        self.advance(10)
        self.engine.pause()
        self.elapse(120)
        saved = self.engine.snapshot()
        self.elapse(179)
        new = self.new_engine()
        new.restore(saved)
        self.assertEqual(new.since_eye, 10)
        self.assertEqual(new.since_movement, 10)
        self.elapse(1)
        self.assertTrue(new.start())
        self.assertEqual(new.since_eye, 10)
        self.assertEqual(new.since_movement, 10)

    def test_legacy_snapshot_preserves_cadence_without_guessing_time_away(self):
        self.engine.start()
        self.advance(10)
        self.engine.pause()
        saved = self.engine.snapshot()
        saved.pop("saved_at", None)
        saved.pop("rest_elapsed", None)
        saved.pop("day_reset_minutes", None)
        saved.pop("desk_active", None)
        saved.pop("desk_elapsed", None)
        saved.pop("movement_snooze_remaining", None)
        saved["version"] = 1
        self.elapse(1000)
        new = self.new_engine()
        new.restore(saved)
        self.assertEqual(new.since_eye, 10)
        self.assertEqual(new.since_movement, 10)
        self.elapse(299)
        new.tick()
        self.assertEqual(new.since_eye, 10)
        self.elapse(1)
        self.assertTrue(new.start())
        self.assertEqual(new.since_eye, 10)
        self.assertEqual(new.since_movement, 10)
        self.assertEqual(new.desk_elapsed, new.today_work)

    def test_legacy_snapshot_from_before_midnight_survives_until_five_am(self):
        legacy = self.timed_engine(datetime(2026, 11, 9, 23, 59))
        legacy.start()
        self.clock.time += 1
        self.clock.wall += 1
        legacy.tick()
        saved = legacy.snapshot()
        for key in ("day_reset_minutes", "desk_active", "desk_elapsed",
                    "movement_snooze_remaining"):
            saved.pop(key, None)
        saved["version"] = 1

        self.clock.moment = datetime(2026, 11, 10, 2, 0)
        restored = self.timed_engine(self.clock.moment)
        restored.restore(saved)
        self.assertEqual(restored.today_work, 1)
        self.assertEqual(restored.desk_elapsed, 1)
        self.assertEqual(restored.since_eye, 1)

    def test_future_saved_timestamp_does_not_create_false_offline_rest(self):
        self.engine.start()
        self.advance(10)
        self.engine.pause()
        saved = self.engine.snapshot()
        saved["saved_at"] = self.clock.wall + 600
        new = self.new_engine()
        new.restore(saved)
        self.assertTrue(new.start())
        self.assertEqual(new.since_eye, 10)
        self.assertEqual(new.since_movement, 10)

    def test_negative_saved_timestamp_is_treated_as_legacy_data(self):
        self.engine.start()
        self.advance(10)
        self.engine.pause()
        saved = self.engine.snapshot()
        saved["saved_at"] = -1
        self.elapse(1000)
        new = self.new_engine()
        new.restore(saved)
        self.assertTrue(new.start())
        self.assertEqual(new.since_eye, 10)
        self.assertEqual(new.since_movement, 10)

    def test_saved_break_restores_paused(self):
        self.engine.start()
        self.advance(3)
        self.engine.begin_break(("eye",))
        saved = self.engine.snapshot()
        self.engine.restore(saved)
        self.assertEqual(self.engine.state, "paused")
        self.assertEqual(self.engine.pending_break, ())
        self.assertEqual(self.engine.tick(), [])

    def test_new_day_resets_daily_goal_and_keeps_lifetime_work(self):
        self.engine.start()
        self.advance(10)
        self.clock.day += timedelta(days=1)
        self.assertEqual(self.engine.tick(), ["day_changed"])
        self.assertEqual(self.engine.today_work, 0)
        self.assertEqual(self.engine.goal_baseline, 0)
        self.assertEqual(self.engine.desk_elapsed, 0)
        self.assertEqual(self.engine.total_work, 10)
        self.advance(2)
        self.assertEqual(self.engine.today_work, 2)
        self.assertEqual(self.engine.desk_elapsed, 2)
        self.assertEqual(self.engine.total_work, 12)

    def test_default_rollover_is_five_am_not_midnight(self):
        midnight = self.timed_engine(datetime(2026, 11, 9, 23, 59, 59))
        midnight.start()
        midnight.today_work = 100
        midnight.total_work = 100
        self.assertEqual(self.timed_tick(midnight), [])
        self.assertEqual(midnight.today_work, 101)

        five_am = self.timed_engine(datetime(2026, 11, 10, 4, 59, 59))
        five_am.start()
        five_am.today_work = 100
        five_am.goal_baseline = 40
        five_am.total_work = 100
        five_am.desk_elapsed = 150
        five_am.break_count = 3
        self.assertEqual(self.timed_tick(five_am), ["day_changed"])
        self.assertEqual(five_am.today_work, 1)
        self.assertEqual(five_am.goal_baseline, 0)
        self.assertEqual(five_am.desk_elapsed, 1)
        self.assertEqual(five_am.break_count, 0)
        self.assertEqual(five_am.total_work, 101)

    def test_custom_daily_rollover_minute_is_persisted_and_applied(self):
        engine = self.timed_engine(datetime(2026, 11, 10, 1, 59, 59))
        engine.set_day_reset(2 * 60)
        engine.start()
        engine.today_work = 25
        engine.total_work = 25
        engine.desk_elapsed = 30
        self.assertEqual(self.timed_tick(engine), ["day_changed"])
        self.assertEqual(engine.today_work, 1)
        self.assertEqual(engine.desk_elapsed, 1)
        snapshot = engine.snapshot()
        self.assertEqual(snapshot["day_reset_minutes"], 120)

        restored = self.timed_engine(self.clock.moment)
        restored.restore(snapshot)
        self.assertEqual(restored.day_reset_minutes, 120)
        self.assertEqual(restored.today_work, 1)
        with self.assertRaises(ValueError):
            restored.set_day_reset(1440)

    def test_restoring_another_day_resets_daily_values(self):
        self.engine.start()
        self.advance(10)
        saved = self.engine.snapshot()
        self.clock.day += timedelta(days=1)
        self.engine.restore(saved)
        self.assertEqual(self.engine.today_work, 0)
        self.assertEqual(self.engine.desk_elapsed, 0)
        self.assertEqual(self.engine.total_work, 10)

    def test_corrupt_persistence_stays_finite_and_safe(self):
        self.engine.restore({"mode": "bad", "state": "running", "timer_duration": -30,
                             "today_work": math.nan, "goal_seconds": "wrong",
                             "timer_remaining": math.inf, "since_eye": -30,
                             "goal_enabled": "false", "break_count": []})
        self.assertEqual(self.engine.mode, "stopwatch")
        self.assertEqual(self.engine.state, "paused")
        self.assertGreater(self.engine.timer_duration, 0)
        self.assertEqual(self.engine.today_work, 0)
        self.assertFalse(self.engine.goal_enabled)
        json.dumps(self.engine.snapshot(), allow_nan=False)

    def test_disabled_reminders_do_not_interrupt(self):
        self.engine.eye_enabled = False
        self.engine.movement_enabled = False
        self.engine.eye_interval = 1
        self.engine.movement_interval = 1
        self.engine.start()
        self.assertEqual(self.advance(20), [])
        self.assertEqual(self.engine.state, "running")

    def test_skipping_break_resumes_and_resets_cadence_without_completion(self):
        self.engine.eye_interval = 3
        self.engine.start()
        self.advance(3)
        self.engine.finish_break(completed=False)
        self.assertEqual(self.engine.state, "running")
        self.assertEqual(self.engine.break_count, 0)
        self.assertEqual(self.engine.since_eye, 0)
        self.assertEqual(self.advance(2), [])
        self.assertEqual(self.advance(1), ["break"])

    def test_manual_break_consumes_pending_automatic_popup(self):
        self.engine.eye_interval = 3
        self.engine.start()
        self.clock.time += 3
        self.engine.begin_break(("movement",))
        self.assertEqual(self.engine.pending_break, ("eye", "movement"))
        self.assertEqual(self.engine.tick(), [])
        self.engine.finish_break()
        self.assertEqual(self.engine.break_count, 1)

    def test_manual_exercise_resets_only_its_own_cadence(self):
        self.engine.start()
        self.advance(3)
        self.engine.begin_break(("eye",))
        self.elapse(20)
        self.engine.finish_break()
        self.assertEqual(self.engine.since_eye, 0)
        self.assertEqual(self.engine.since_movement, 3)

    def test_eye_dialog_never_resets_movement_cadence(self):
        self.engine.start()
        self.advance(10)
        self.engine.begin_break(("eye",))
        self.elapse(300)
        self.engine.finish_break()
        self.assertEqual(self.engine.state, "running")
        self.assertEqual(self.engine.since_eye, 0)
        self.assertEqual(self.engine.since_movement, 10)
        self.assertEqual(self.engine.today_work, 10)
        self.assertEqual(self.engine.break_count, 1)

    def test_eye_break_resets_only_eye_after_work_was_paused(self):
        self.engine.start()
        self.advance(10)
        self.engine.pause()
        self.advance(290)
        self.engine.begin_break(("eye",))
        self.elapse(20)
        self.engine.finish_break()
        self.assertEqual(self.engine.state, "paused")
        self.assertEqual(self.engine.since_eye, 0)
        self.assertEqual(self.engine.since_movement, 300)
        self.assertEqual(self.engine.today_work, 10)


if __name__ == "__main__":
    unittest.main()
