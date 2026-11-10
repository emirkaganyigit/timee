"""Deterministic coverage, duration, and persistence contracts for break plans."""

import copy
from collections import Counter
import json
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from mola.content import EXERCISES
from mola.wellness import SHORT_MOVEMENT_IDS, normalize_rotation, plan_automatic_break


class RotationTests(unittest.TestCase):
    def test_missing_or_non_mapping_rotation_uses_defaults(self):
        expected = {"version": 1, "eye": 0, "movement": 0}
        for value in (None, {}, [], "invalid", 5, True):
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
        original = {"version": 1, "eye": 7, "movement": 18, "unrelated": "preserve caller"}
        before = copy.deepcopy(original)
        result = normalize_rotation(original)
        self.assertEqual(result, {"version": 1, "eye": 1, "movement": 3})
        self.assertEqual(original, before)

    def test_eye_plans_alternate_but_always_include_distance_break(self):
        state = normalize_rotation(None)
        plans = []
        for _ in range(3):
            steps, state = plan_automatic_break(("eye",), state)
            plans.append([item["id"] for item, _ in steps])
            self.assertEqual(sum(duration for _, duration in steps), 30)
            self.assertEqual([duration for item, duration in steps if item["id"] == "distance"], [20])
            self.assertTrue(all(item["kind"] == "eye" for item, _ in steps))
            self.assertEqual(state["movement"], 0)
        self.assertEqual(plans, [["distance", "blink"], ["blink", "distance"], ["distance", "blink"]])

    def test_movement_cycle_is_varied_balanced_and_exactly_five_minutes(self):
        self.assertEqual(set(SHORT_MOVEMENT_IDS), {"shoulders", "hands", "chest", "sitstand", "calf"})
        self.assertEqual(len(SHORT_MOVEMENT_IDS), 5)
        state = normalize_rotation(None)
        firsts, counts, plans = [], Counter(), []
        for _ in range(5):
            steps, state = plan_automatic_break(("movement",), state)
            self.assertEqual(len(steps), 4)
            self.assertEqual(sum(duration for _, duration in steps), 300)
            self.assertTrue(all(duration > 0 for _, duration in steps))
            self.assertTrue(all(item["kind"] == "movement" for item, _ in steps))
            short_ids = [item["id"] for item, _ in steps[:-1]]
            self.assertEqual(len(set(short_ids)), 3)
            self.assertTrue(set(short_ids).issubset(set(SHORT_MOVEMENT_IDS)))
            self.assertEqual(steps[-1][0]["id"], "screen_rest")
            counts.update(short_ids)
            firsts.append(short_ids[0])
            plans.append(steps)
            self.assertEqual(state["eye"], 0)
        self.assertEqual(set(firsts), set(SHORT_MOVEMENT_IDS))
        self.assertEqual(set(counts.values()), {3})
        self.assertEqual(state["movement"], 0)
        sixth, _ = plan_automatic_break(("movement",), state)
        self.assertEqual(sixth, plans[0])

    def test_movement_cursors_advance_by_three_and_wrap(self):
        state = normalize_rotation(None)
        positions = []
        for _ in range(5):
            _, state = plan_automatic_break(("movement",), state)
            positions.append(state["movement"])
        self.assertEqual(positions, [3, 1, 4, 2, 0])

    def test_combined_plan_orders_eye_before_full_movement_sequence(self):
        state = normalize_rotation(None)
        eye, _ = plan_automatic_break(("eye",), state)
        movement, _ = plan_automatic_break(("movement",), state)
        combined, next_state = plan_automatic_break(("eye", "movement"), state)
        self.assertEqual(combined, eye + movement)
        self.assertEqual(sum(duration for _, duration in combined), 330)
        self.assertEqual(next_state["eye"], 1)
        self.assertEqual(next_state["movement"], 3)

    def test_plan_builder_does_not_mutate_rotation_or_catalog(self):
        state = {"version": 1, "eye": 1, "movement": 4}
        state_before = copy.deepcopy(state)
        catalog_before = copy.deepcopy(EXERCISES)
        plan_automatic_break(("eye", "movement"), state)
        self.assertEqual(state, state_before)
        self.assertEqual(EXERCISES, catalog_before)
        walk = next(item for item in EXERCISES if item["id"] == "walk")
        self.assertEqual(walk["duration"], 300)

    def test_json_round_trip_continues_at_next_routine(self):
        state = normalize_rotation(None)
        first, state = plan_automatic_break(("eye", "movement"), state)
        restored = normalize_rotation(json.loads(json.dumps(state)))
        second, _ = plan_automatic_break(("eye", "movement"), restored)
        uninterrupted, _ = plan_automatic_break(("eye", "movement"), state)
        self.assertEqual(second, uninterrupted)
        self.assertNotEqual(first[0][0]["id"], second[0][0]["id"])
        self.assertNotEqual(first[2][0]["id"], second[2][0]["id"])


if __name__ == "__main__":
    unittest.main()
