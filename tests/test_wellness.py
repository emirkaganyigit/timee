"""Deterministic planning and interactive break-dialog contracts."""

import copy
import json
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from mola.content import EXERCISES
from mola.wellness import (
    BreakDialog, EYE_ORDERS, EXERCISE_MAP, MOVEMENT_IDS,
    MOVEMENT_SNOOZE_SECONDS, normalize_rotation, plan_automatic_break,
)


class RotationTests(unittest.TestCase):
    def test_missing_legacy_or_non_mapping_rotation_uses_v2_defaults(self):
        expected = {"version": 2, "eye": 0, "movement": 0}
        for value in (
            None, {}, [], "invalid", 5, True,
            {"version": 1, "eye": 1, "movement": 4},
        ):
            with self.subTest(value=value):
                self.assertEqual(normalize_rotation(value), expected)

    def test_malformed_cursors_recover_independently(self):
        for invalid in (None, True, False, -1, "2", 1.5, [], {}):
            with self.subTest(invalid=invalid):
                self.assertEqual(normalize_rotation({"eye": invalid, "movement": 3})["eye"], 0)
                self.assertEqual(normalize_rotation({"eye": invalid, "movement": 3})["movement"], 3)
                self.assertEqual(normalize_rotation({"eye": 1, "movement": invalid})["eye"], 1)
                self.assertEqual(normalize_rotation({"eye": 1, "movement": invalid})["movement"], 0)

    def test_valid_cursors_are_normalized_without_mutating_input(self):
        original = {"version": 2, "eye": 7, "movement": 18, "unrelated": "preserve caller"}
        before = copy.deepcopy(original)
        result = normalize_rotation(original)
        self.assertEqual(result, {
            "version": 2,
            "eye": 7 % len(EYE_ORDERS),
            "movement": 18 % len(MOVEMENT_IDS),
        })
        self.assertEqual(original, before)

    def test_eye_rotation_is_varied_and_keeps_sourced_duration_shape(self):
        self.assertGreaterEqual(len(EYE_ORDERS), 5)
        state = normalize_rotation(None)
        plans = []
        for _ in range(len(EYE_ORDERS)):
            steps, state = plan_automatic_break(("eye",), state)
            identifiers = [item["id"] for item, _ in steps]
            plans.append(identifiers)
            self.assertEqual(len(steps), 2)
            self.assertEqual(sorted(duration for _, duration in steps), [10, 20])
            self.assertEqual(sum(duration for _, duration in steps), 30)
            self.assertTrue(all(item["kind"] == "eye" for item, _ in steps))
            self.assertEqual(sum(identifier.startswith("distance") for identifier in identifiers), 1)
            self.assertEqual(state["movement"], 0)
        self.assertEqual(len({tuple(plan) for plan in plans}), len(EYE_ORDERS))
        self.assertEqual(state["eye"], 0)

    def test_verified_eye_variants_are_exposed_by_catalog(self):
        expected = {"distance", "distance_window", "distance_room", "blink", "eyes_closed"}
        self.assertTrue(expected.issubset(EXERCISE_MAP))
        self.assertTrue(all(EXERCISE_MAP[key]["kind"] == "eye" for key in expected))

    def test_movement_rotation_offers_exactly_one_exercise_each_time(self):
        state = normalize_rotation(None)
        observed = []
        for expected in MOVEMENT_IDS:
            steps, state = plan_automatic_break(("movement",), state)
            self.assertEqual(len(steps), 1)
            item, duration = steps[0]
            self.assertEqual(item["id"], expected)
            self.assertEqual(duration, item["duration"])
            self.assertGreater(duration, 0)
            self.assertEqual(item["kind"], "movement")
            observed.append(item["id"])
            self.assertEqual(state["eye"], 0)
        self.assertEqual(tuple(observed), MOVEMENT_IDS)
        self.assertEqual(state["movement"], 0)

    def test_combined_plan_contains_eye_pair_and_one_movement(self):
        state = normalize_rotation(None)
        eye, _ = plan_automatic_break(("eye",), state)
        movement, _ = plan_automatic_break(("movement",), state)
        combined, next_state = plan_automatic_break(("eye", "movement"), state)
        self.assertEqual(combined, eye + movement)
        self.assertEqual(len(combined), 3)
        self.assertEqual(next_state["eye"], 1)
        self.assertEqual(next_state["movement"], 1)

    def test_plan_builder_does_not_mutate_rotation_or_catalog(self):
        state = {"version": 2, "eye": 1, "movement": 4}
        state_before = copy.deepcopy(state)
        catalog_before = copy.deepcopy(EXERCISES)
        plan_automatic_break(("eye", "movement"), state)
        self.assertEqual(state, state_before)
        self.assertEqual(EXERCISES, catalog_before)

    def test_json_round_trip_continues_at_next_routine(self):
        state = normalize_rotation(None)
        first, state = plan_automatic_break(("eye", "movement"), state)
        restored = normalize_rotation(json.loads(json.dumps(state)))
        second, _ = plan_automatic_break(("eye", "movement"), restored)
        uninterrupted, _ = plan_automatic_break(("eye", "movement"), state)
        self.assertEqual(second, uninterrupted)
        self.assertNotEqual(first[0][0]["id"], second[0][0]["id"])
        self.assertNotEqual(first[-1][0]["id"], second[-1][0]["id"])


class Clock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value


class BreakDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.clock = Clock()
        self.time_patch = patch("mola.wellness.time.monotonic", self.clock)
        self.time_patch.start()
        self.dialogs = []

    def tearDown(self):
        for dialog in self.dialogs:
            if not dialog.finished_once:
                dialog.close()
            dialog.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.time_patch.stop()

    def make_dialog(self, kinds, **kwargs):
        dialog = BreakDialog(kinds, **kwargs)
        self.dialogs.append(dialog)
        dialog.show()
        self.app.processEvents()
        return dialog

    def test_combined_reminder_shows_both_cards_and_each_can_be_skipped(self):
        dialog = self.make_dialog(("eye", "movement"))
        results = []
        dialog.resolved.connect(results.append)
        self.assertTrue(dialog.selector.isVisible())
        self.assertTrue(dialog.kind_cards["eye"].isVisible())
        self.assertTrue(dialog.kind_cards["movement"].isVisible())

        dialog.kind_actions["eye"]["skip"].click()
        self.app.processEvents()
        self.assertFalse(dialog.kind_cards["eye"].isVisible())
        self.assertTrue(dialog.kind_cards["movement"].isVisible())
        dialog.kind_actions["movement"]["skip"].click()
        self.assertEqual(results, [{"eye": "skipped", "movement": "skipped"}])

    def test_movement_can_be_snoozed_or_acknowledged(self):
        self.assertEqual(MOVEMENT_SNOOZE_SECONDS, 600)
        snoozed = self.make_dialog(("movement",))
        snooze_results = []
        snoozed.resolved.connect(snooze_results.append)
        snoozed.kind_actions["movement"]["snooze"].click()
        self.assertEqual(snooze_results, [{"movement": "snoozed"}])

        acknowledged = self.make_dialog(("movement",))
        acknowledged_results = []
        acknowledged.resolved.connect(acknowledged_results.append)
        acknowledged.kind_actions["movement"]["acknowledged"].click()
        self.assertEqual(acknowledged_results, [{"movement": "acknowledged"}])

    def test_user_can_choose_movement_before_eye(self):
        dialog = self.make_dialog(("eye", "movement"))
        dialog.kind_actions["movement"]["start"].click()
        self.assertEqual(dialog.active_kind, "movement")
        self.assertEqual(dialog.item["kind"], "movement")
        dialog.skip.click()
        self.assertTrue(dialog.selector.isVisible())
        self.assertTrue(dialog.kind_cards["eye"].isVisible())

    def test_automatic_eye_steps_advance_without_next_click_and_keep_animating(self):
        steps, _ = plan_automatic_break(("eye",), None)
        dialog = self.make_dialog(("eye",), planned_steps=steps)
        results = []
        dialog.resolved.connect(results.append)
        dialog.kind_actions["eye"]["start"].click()
        dialog.primary.click()
        self.assertTrue(dialog.animation.timer.isActive())
        self.assertFalse(dialog.primary.isEnabled())
        first_duration = dialog.duration

        self.clock.value += first_duration
        dialog.tick()
        self.assertEqual(dialog.active_position, 1)
        self.assertEqual(dialog.step, dialog.active_indices[1])
        self.assertIsNotNone(dialog.started_at)
        self.assertFalse(dialog.primary.isEnabled())
        self.assertTrue(dialog.animation.timer.isActive())

        self.clock.value += dialog.duration
        dialog.tick()
        self.assertEqual(results, [{"eye": "completed"}])
        self.assertTrue(dialog.finished_once)

    def test_single_movement_waits_for_explicit_completion_after_timer(self):
        dialog = self.make_dialog(("movement",))
        results = []
        dialog.resolved.connect(results.append)
        dialog.kind_actions["movement"]["start"].click()
        self.assertEqual(len(dialog.active_indices), 1)
        dialog.primary.click()
        self.clock.value += dialog.duration
        dialog.tick()
        self.assertTrue(dialog.primary.isEnabled())
        self.assertEqual(results, [])
        dialog.primary.click()
        self.assertEqual(results, [{"movement": "completed"}])

    def test_close_marks_every_unresolved_kind_skipped(self):
        dialog = self.make_dialog(("eye", "movement"))
        results = []
        dialog.resolved.connect(results.append)
        dialog.close()
        self.assertEqual(results, [{"eye": "skipped", "movement": "skipped"}])


if __name__ == "__main__":
    unittest.main()
