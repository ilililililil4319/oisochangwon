import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
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
        self.assertEqual(len(results), len(load_policies()))
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

    def test_job_type_split(self):
        worker = by_id(match_policies(dict(PERSONA, job_type="직장인"), TODAY))
        owner = by_id(match_policies(dict(PERSONA, job_type="자영업", employed_in_changwon=True), TODAY))
        student = by_id(match_policies(dict(PERSONA, job_type="학생", employed_in_changwon=False), TODAY))
        other = by_id(match_policies(dict(PERSONA, job_type="기타", employed_in_changwon=False), TODAY))
        # 기업노동자 전입지원금: '근무하는 노동자' 대상(창원시 공고) → 직장인만 판정 대상, 자영업(사업주)·학생·기타는 해당 없음
        self.assertEqual(worker["P01"]["level"], "조건부 해당 가능")
        self.assertEqual(owner["P01"]["level"], "해당 없음")
        self.assertIn("자영업", " ".join(owner["P01"]["reasons"]))
        self.assertEqual(student["P01"]["level"], "해당 없음")
        self.assertEqual(other["P01"]["level"], "해당 없음")
        # '재직' 대상 사업에서 자영업은 기관 확인, 미취업 대상 사업에서 학생은 재학생 여부 확인
        self.assertEqual(owner["P09"]["level"], "직접 확인")
        self.assertEqual(student["P07"]["level"], "직접 확인")
        self.assertNotEqual(other["P07"]["level"], "해당 없음")

    def test_transfer_student_support_p32(self):
        student = by_id(match_policies(dict(PERSONA, job_type="학생", employed_in_changwon=False), TODAY))
        worker = by_id(match_policies(dict(PERSONA, job_type="직장인"), TODAY))
        short = by_id(match_policies(dict(PERSONA, job_type="학생", employed_in_changwon=False, previous_residence_years=0), TODAY))
        self.assertEqual(student["P32"]["level"], "해당 가능")
        self.assertEqual(worker["P32"]["level"], "해당 없음")
        self.assertEqual(short["P32"]["level"], "해당 없음")
        self.assertEqual(by_id(match_policies(PERSONA, TODAY))["P32"]["level"], "직접 확인")

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
