import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import unittest
from datetime import date, datetime

from policy_engine import evaluate_p01
from settlement_engine import build_settlement_plan


class SettlementPlanTests(unittest.TestCase):
    def test_builds_expected_milestones_and_dates(self):
        plan = build_settlement_plan(date(2026, 9, 20))

        self.assertEqual(
            [milestone["day"] for milestone in plan["milestones"]],
            [0, 7, 30, 90, 180],
        )
        self.assertEqual(
            [milestone["date"] for milestone in plan["milestones"]],
            [
                "2026-09-20",
                "2026-09-27",
                "2026-10-20",
                "2026-12-19",
                "2027-03-19",
            ],
        )
        self.assertTrue(
            all("day" in milestone and "date" in milestone for milestone in plan["milestones"])
        )

    def test_rejects_missing_or_non_date_inputs(self):
        for invalid_date in (None, "2026-09-20", datetime(2026, 9, 20)):
            with self.subTest(invalid_date=invalid_date):
                with self.assertRaises(TypeError):
                    build_settlement_plan(invalid_date)

    def test_p01_uses_six_calendar_months_not_day_180(self):
        profile = {
            "move_in_date": date(2026, 9, 20),
            "previous_residence_years": 2,
            "employed_in_changwon": True,
        }

        result = evaluate_p01(profile)
        plan = build_settlement_plan(profile["move_in_date"])

        self.assertEqual(result["eligible_date"], "2027-03-20")
        self.assertEqual(plan["milestones"][-1]["date"], "2027-03-19")


if __name__ == "__main__":
    unittest.main()
