import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

from mission_manager import group_missions_by_month, load_missions
from policy_matcher import match_policies
from schedule_export import build_ics, build_report_html, build_schedule_events

LABELS = {0: "전입한 날", 7: "첫 주", 30: "정착 1~2개월", 90: "정착 3-5개월", 180: "정착 6개월 이후"}
PROFILE = {
    "nickname": "테스트", "age": 27, "move_in_date": date(2026, 9, 1), "home_district": "의창구",
    "neighborhood": "", "previous_residence_years": 2, "job_type": "직장인",
    "employed_in_changwon": True, "vehicle": "없음",
}


def _events():
    matches = match_policies(PROFILE, today=date(2026, 10, 3))
    groups = group_missions_by_month(load_missions())
    return matches, groups, build_schedule_events(date(2026, 9, 1), LABELS, groups, matches)


class ScheduleExportTests(unittest.TestCase):
    def test_events_cover_milestones_months_and_dated_policies_only(self):
        matches, groups, events = _events()
        kinds = [event["kind"] for event in events]
        self.assertEqual(kinds.count("milestone"), 5)
        self.assertEqual(kinds.count("missions"), 6)
        self.assertIn("[창원 정착] 정착 1~2개월", [event["title"] for event in events])
        self.assertIn(date(2026, 10, 1), [event["date"] for event in events if event["title"].endswith("정착 1~2개월")])
        policy_titles = {event["title"] for event in events if event["kind"] == "policy"}
        allowed = {f"[혜택 확인] {m['name']}" for m in matches if m["level"] in ("해당 가능", "조건부 해당 가능")}
        self.assertTrue(policy_titles)
        self.assertTrue(policy_titles <= allowed)
        self.assertEqual([e["date"] for e in events], sorted(e["date"] for e in events))

    def test_ics_is_valid_and_folded(self):
        _, _, events = _events()
        data = build_ics(events, now=datetime(2026, 10, 3, 10, tzinfo=ZoneInfo("Asia/Seoul")))
        text = data.decode("utf-8")
        self.assertTrue(text.startswith("BEGIN:VCALENDAR\r\n"))
        self.assertTrue(text.endswith("END:VCALENDAR\r\n"))
        self.assertEqual(text.count("BEGIN:VEVENT"), len(events))
        self.assertIn("DTSTART;VALUE=DATE:20261001", text)
        self.assertIn("TRIGGER:-PT15H", text)
        for line in text.split("\r\n"):
            self.assertLessEqual(len(line.encode("utf-8")), 75)
        self.assertNotIn("테스트", text)  # 닉네임은 넣지 않는다

    def test_report_has_sections_without_nickname_and_escapes_notes(self):
        matches, groups, events = _events()
        report = build_report_html(
            {"move_in_date": "2026-09-01", "job_type": "직장인", "age": 27, "vehicle": "없음"},
            32, {"overall_completed": 1, "overall_total": 24, "stage_completed": 1, "stage_total": 4},
            groups, {"M1-1": True}, {"M1-1": "<script>x</script>"}, matches, events,
            generated_at=datetime(2026, 10, 3, 10, tzinfo=ZoneInfo("Asia/Seoul")),
        ).decode("utf-8")
        for heading in ("나의 조건", "정착 할 일 진행", "다가오는 일정", "나에게 맞는 혜택"):
            self.assertIn(heading, report)
        self.assertIn("정착 33일째", report)
        self.assertIn("&lt;script&gt;", report)
        self.assertNotIn("<script>", report)
        self.assertNotIn("테스트", report)


if __name__ == "__main__":
    unittest.main()
