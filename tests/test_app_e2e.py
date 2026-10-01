import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import state_manager
import activity_manager
from policy_engine import evaluate_p01
from state_manager import load_mission_states
from streamlit.testing.v1 import AppTest
from activity_manager import activity_view, filter_activities, load_activities


APP_FILE = Path(__file__).resolve().parents[1] / "app.py"


def _visible_text(app):
    visible_values = []
    element_types = (
        "title",
        "header",
        "subheader",
        "markdown",
        "text",
        "caption",
        "success",
        "info",
        "warning",
        "error",
        "button",
        "checkbox",
        "expander",
        "text_input",
        "number_input",
        "date_input",
        "selectbox",
        "link_button",
    )
    for element_type in element_types:
        elements = app.get(element_type) if element_type == "link_button" else getattr(app, element_type, [])
        for element in elements:
            for attribute in ("label", "value"):
                value = getattr(element, attribute, None)
                if isinstance(value, str):
                    visible_values.append(value)
    return "\n".join(visible_values)


class ApplicationE2ETests(unittest.TestCase):
    def test_representative_profile_renders_policy_timeline_and_all_missions(self):
        with TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "storage" / "progress.sqlite3"
            with patch.object(state_manager, "DB_PATH", database):
                app = AppTest.from_file(str(APP_FILE)).run()
                app.button[0].click().run()

                self.assertFalse(app.exception)
                rendered_text = _visible_text(app)
                self.assertIn("조금 뒤 신청할 수 있어요", rendered_text)
                self.assertIn("받을 수 있는 지원", rendered_text)
                self.assertIn("창원 정착 일정", rendered_text)
                self.assertIn("이번에 할 일", rendered_text)
                self.assertIn("2027-03-20", rendered_text)
                self.assertIn("2027-03-19", rendered_text)
                for internal_term in (
                    "eligible_now",
                    "eligible_later",
                    "needs_info",
                    "not_eligible",
                    "P01",
                    "mission_id",
                    "SQLite",
                    "JSON",
                    "API",
                    "LLM",
                    "DB",
                    "Policy Tool",
                    "Local Activity Tool",
                    "Dialect Tool",
                    "Complaint Tool",
                    "Mission Tool",
                    "status",
                    "D+",
                    "180일",
                    "M1-1",
                    "M6-4",
                    "mission",
                    "Tool",
                    "app.py",
                    "policy_engine.py",
                    "mission_manager.py",
                    "settlement_engine.py",
                    "state_manager.py",
                    "requirements.txt",
                    "is_service_idea",
                    "연결 기능",
                    "서비스 목표",
                    "TypeError",
                    "ValueError",
                    "KeyError",
                ):
                    self.assertNotIn(internal_term.casefold(), rendered_text.casefold())
                mission_widgets = [
                    item
                    for item in app.checkbox
                    if item.key and item.key.startswith("mission-progress:")
                ]
                self.assertEqual(len(mission_widgets), 26)
                self.assertEqual(
                    len(
                        {
                            item.key
                            for item in mission_widgets
                        }
                    ),
                    26,
                )

    def test_ineligible_profile_still_renders_policy_result(self):
        with TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "storage" / "progress.sqlite3"
            with patch.object(state_manager, "DB_PATH", database):
                app = AppTest.from_file(str(APP_FILE)).run()
                app.number_input[1].set_value(0).run()
                app.button[0].click().run()

                self.assertFalse(app.exception)
                self.assertIn(
                    "현재 조건으로는 신청 대상이 아니에요",
                    _visible_text(app),
                )

    def test_missing_policy_input_is_reported_by_policy_engine(self):
        result = evaluate_p01(
            {
                "move_in_date": None,
                "previous_residence_years": 2,
                "employed_in_changwon": True,
            }
        )

        self.assertEqual(result["status"], "needs_info")
        self.assertEqual(result["missing_fields"], ["move_in_date"])

    def test_activity_recommendations_filter_by_real_district_and_category(self):
        with TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "storage" / "progress.sqlite3"
            with patch.object(state_manager, "DB_PATH", database):
                app = AppTest.from_file(str(APP_FILE)).run()
                app.button[0].click().run()
                app.selectbox(key="activity_district").select("성산구").run()
                app.selectbox(key="activity_category").select("문화생활").run()

                self.assertFalse(app.exception)
                expected = filter_activities(
                    load_activities(),
                    district="성산구",
                    category="문화생활",
                )
                expected_labels = {
                    f"{item['이름']} · {item['생활권(구)']}"
                    for item in expected
                }
                activity_selector = app.selectbox(key="activity_selection")
                self.assertTrue(expected_labels)
                self.assertEqual(set(activity_selector.options), expected_labels)
                self.assertIn(expected[0]["이름"], [item.value for item in app.text])
                self.assertEqual(
                    len(
                        [
                            item
                            for item in app.checkbox
                            if item.key
                            and item.key.startswith("mission-progress:")
                        ]
                    ),
                    26,
                )

    def test_activity_data_failure_does_not_hide_p0_results(self):
        with TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "storage" / "progress.sqlite3"
            with patch.object(state_manager, "DB_PATH", database):
                with patch.object(
                    activity_manager,
                    "load_activities",
                    side_effect=ValueError("invalid data"),
                ):
                    app = AppTest.from_file(str(APP_FILE)).run()
                    app.button[0].click().run()

                self.assertFalse(app.exception)
                visible_text = _visible_text(app)
                self.assertIn("조금 뒤 신청할 수 있어요", visible_text)
                self.assertIn(
                    "지원 확인과 정착 할 일은 계속 이용할 수 있어요",
                    visible_text,
                )
                self.assertNotIn("ValueError", visible_text)

    def test_youth_policy_and_activity_links_use_their_verified_labels(self):
        with TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "storage" / "progress.sqlite3"
            with patch.object(state_manager, "DB_PATH", database):
                app = AppTest.from_file(str(APP_FILE)).run()
                app.button[0].click().run()

                self.assertFalse(app.exception)
                links = {
                    (item.label, item.url)
                    for item in app.get("link_button")
                }
                self.assertIn(
                    (
                        "창원시 청년정책 전체 보기",
                        "https://www.changwon.go.kr/youth/05085/05105/05105.web",
                    ),
                    links,
                )
                first_activity = load_activities()[0]
                self.assertIn(
                    ("공식 안내 보기", first_activity["공식 URL"].split()[0]),
                    links,
                )
                self.assertIn(
                    ("네이버 지도에서 보기", "https://map.naver.com/p/"),
                    links,
                )
                app_search_links = [
                    item.url
                    for item in app.get("link_button")
                    if item.label == "네이버 지도 앱에서 장소 찾기"
                ]
                self.assertEqual(len(app_search_links), 1)
                self.assertTrue(app_search_links[0].startswith("nmap://search?"))
                self.assertNotIn("lat=", app_search_links[0])
                self.assertNotIn("lng=", app_search_links[0])

    def test_untrusted_and_missing_activity_urls_are_not_official_buttons(self):
        source_activities = load_activities()
        source_by_id = {activity["ID"]: activity for activity in source_activities}

        for activity_id in ("A98", "A126", "A323", "A56", "A134"):
            with self.subTest(activity_id=activity_id):
                with TemporaryDirectory() as temp_dir:
                    database = Path(temp_dir) / "storage" / "progress.sqlite3"
                    test_activity = dict(source_by_id[activity_id])
                    with patch.object(state_manager, "DB_PATH", database):
                        with patch.object(
                            activity_manager,
                            "load_activities",
                            return_value=[test_activity],
                        ):
                            app = AppTest.from_file(str(APP_FILE)).run()
                            app.button[0].click().run()

                    self.assertFalse(app.exception)
                    links = app.get("link_button")
                    self.assertFalse(
                        any(item.label in {"공식 안내 보기", "공식 SNS 보기"} for item in links)
                    )
                    self.assertTrue(
                        any(item.label == "네이버 지도에서 보기" for item in links)
                    )

    def test_activity_text_preserves_markdown_special_characters(self):
        source_activity = dict(load_activities()[0])
        source_activity.update(
            {
                "ID": "QA-SPECIAL-TEXT",
                "이름": "온천 ~~장소~~ <상세> _확인_",
                "일정·운영시간": (
                    "온천 06:00~23:00 / 인피니티풀 10:00~21:00"
                ),
                "참여 방법": "예약 ~~후~~ 확인 <안내>",
                "대상": "누구나 *가능*",
            }
        )

        with TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "storage" / "progress.sqlite3"
            with patch.object(state_manager, "DB_PATH", database):
                with patch.object(
                    activity_manager,
                    "load_activities",
                    return_value=[source_activity],
                ):
                    app = AppTest.from_file(str(APP_FILE)).run()
                    app.button[0].click().run()

            self.assertFalse(app.exception)
            rendered_text = [item.value for item in app.text]
            self.assertIn("온천 ~~장소~~ <상세> _확인_", rendered_text)
            self.assertIn(
                "운영시간: 온천 06:00~23:00 / 인피니티풀 10:00~21:00",
                rendered_text,
            )
            self.assertIn("참여 방법: 예약 ~~후~~ 확인 <안내>", rendered_text)
            self.assertIn("대상: 누구나 *가능*", rendered_text)

    def test_mission_progress_persists_for_same_nickname_only(self):
        with TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "storage" / "progress.sqlite3"
            with patch.object(state_manager, "DB_PATH", database):
                first_session = AppTest.from_file(str(APP_FILE)).run()
                first_session.button[0].click().run()
                first_session.checkbox(key="mission-progress:코디세이:M1-1").check().run()

                self.assertFalse(first_session.exception)
                self.assertTrue(
                    load_mission_states("코디세이", database)["M1-1"]
                )

                restored_session = AppTest.from_file(str(APP_FILE)).run()
                self.assertFalse(restored_session.exception)
                self.assertTrue(
                    restored_session.checkbox(
                        key="mission-progress:코디세이:M1-1"
                    ).value
                )
                self.assertFalse(
                    restored_session.checkbox(
                        key="mission-progress:코디세이:M1-2"
                    ).value
                )

                restored_session.text_input[0].set_value("다른 사용자").run()
                self.assertFalse(restored_session.exception)
                self.assertFalse(
                    restored_session.checkbox(
                        key="mission-progress:다른 사용자:M1-1"
                    ).value
                )
                self.assertEqual(
                    load_mission_states("다른 사용자", database),
                    {},
                )


if __name__ == "__main__":
    unittest.main()
