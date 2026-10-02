import unittest
from datetime import date

from mission_manager import load_missions
from progress_manager import (
    calculate_mission_progress,
    current_settlement_month,
    encouragement_message,
)


class ProgressManagerTests(unittest.TestCase):
    def test_calculates_current_month_from_calendar_months(self):
        move_in_date = date(2026, 9, 20)

        self.assertEqual(
            current_settlement_month(move_in_date, date(2026, 10, 2)),
            1,
        )
        self.assertEqual(
            current_settlement_month(move_in_date, date(2026, 11, 20)),
            3,
        )
        self.assertEqual(
            current_settlement_month(move_in_date, date(2027, 3, 20)),
            6,
        )
        self.assertEqual(
            current_settlement_month(move_in_date, date(2026, 9, 1)),
            1,
        )

    def test_calculates_current_and_overall_progress_with_actual_stage_sizes(self):
        missions = load_missions()
        completed_states = {mission["ID"]: False for mission in missions}
        month_two = [mission for mission in missions if mission["개월"] == 2]
        month_three = [mission for mission in missions if mission["개월"] == 3]
        for mission in month_two[:2] + month_three[:1]:
            completed_states[mission["ID"]] = True

        month_two_progress = calculate_mission_progress(
            missions,
            completed_states,
            2,
        )
        month_three_progress = calculate_mission_progress(
            missions,
            completed_states,
            3,
        )

        self.assertEqual(
            month_two_progress,
            {
                "overall_completed": 3,
                "overall_total": 26,
                "stage_completed": 2,
                "stage_total": 3,
            },
        )
        self.assertEqual(month_three_progress["stage_total"], 5)
        self.assertEqual(month_three_progress["stage_completed"], 1)

    def test_encouragement_covers_zero_partial_and_complete_for_four_missions(self):
        messages = [encouragement_message(count, 4) for count in range(5)]

        self.assertIn("가장 간단한 것부터", messages[0])
        self.assertIn("첫걸음", messages[1])
        self.assertIn("절반", messages[2])
        self.assertIn("하나만 더", messages[3])
        self.assertIn("4개", messages[4])

    def test_encouragement_scales_for_five_missions_and_empty_stages(self):
        self.assertIn("절반", encouragement_message(3, 5))
        self.assertIn("하나만 더", encouragement_message(4, 5))
        self.assertIn("5개", encouragement_message(5, 5))
        self.assertIn("할 일이 없어요", encouragement_message(0, 0))


if __name__ == "__main__":
    unittest.main()
