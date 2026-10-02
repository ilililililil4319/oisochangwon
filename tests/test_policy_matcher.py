import unittest
from datetime import date

from policy_matcher import LEVELS, evaluate_policy, load_policies, match_policies

PERSONA = {"age": 28, "move_in_date": date(2026, 9, 20), "previous_residence_years": 2, "employed_in_changwon": True}
TODAY = date(2026, 10, 2)


def by_id(results):
    return {r["id"]: r for r in results}


class PolicyMatcherTests(unittest.TestCase):
    def test_all_23_policies_get_one_of_four_levels_sorted(self):
        results = match_policies(PERSONA, TODAY)
        self.assertEqual(len(results), 23)
        self.assertTrue(all(r["level"] in LEVELS for r in results))
        ranks = [LEVELS.index(r["level"]) for r in results]
        self.assertEqual(ranks, sorted(ranks))
        self.assertTrue(all(r["link"].startswith("https://") for r in results))

    def test_persona_core_results(self):
        results = by_id(match_policies(PERSONA, TODAY))
        self.assertEqual(results["P01"]["level"], "조건부 해당 가능")
        self.assertEqual(results["P01"]["eligible_date"], "2027-03-20")
        self.assertIn("180일 이후", results["P01"]["schedule"][0])
        self.assertEqual(results["P06"]["level"], "해당 가능")
        self.assertEqual(results["P07"]["level"], "해당 없음")  # 미취업 대상
        self.assertEqual(results["P05"]["level"], "해당 없음")  # 2025.7.1 이후 계속 거주 미충족
        self.assertNotIn("미취업", " ".join(results["P19"]["reasons"]))  # '무관' 정책

    def test_age_and_unknown_inputs(self):
        older = by_id(match_policies(dict(PERSONA, age=45), TODAY))
        self.assertEqual(older["P03"]["level"], "해당 없음")
        blank = by_id(match_policies({}, TODAY))
        self.assertEqual(blank["P03"]["level"], "직접 확인")
        self.assertEqual(blank["P01"]["level"], "직접 확인")

    def test_no_vehicle_puts_k_pass_first(self):
        results = match_policies(dict(PERSONA, vehicle="없음"), TODAY)
        self.assertEqual(results[0]["id"], "P21")
        self.assertIn("차량이 없어", results[0]["reasons"][0])

    def test_planning_idea_marker_never_shown(self):
        for policy in load_policies():
            result = evaluate_policy(policy, PERSONA, TODAY)
            self.assertNotIn("[서비스 기획 아이디어]", str(result))


if __name__ == "__main__":
    unittest.main()
