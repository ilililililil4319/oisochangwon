import unittest
from datetime import date
from urllib.parse import unquote
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import state_manager
import activity_manager
import progress_manager
from policy_engine import evaluate_p01
from state_manager import (
    format_korea_timestamp,
    load_mission_notes,
    load_mission_states,
    load_mission_timestamps,
)
from streamlit.testing.v1 import AppTest
from activity_manager import (
    activity_view,
    classify_activity_url,
    filter_activities,
    load_activities,
)


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


def _show_both(app):
    app.button(key="show-policy").click().run()
    app.button(key="show-journey").click().run()


class ApplicationE2ETests(unittest.TestCase):
    def setUp(self):
        calculate_month = progress_manager.current_settlement_month
        clock_patch = patch.object(
            progress_manager, "current_settlement_month",
            side_effect=lambda move_in_date: calculate_month(move_in_date, date(2026, 10, 2)),
        )
        clock_patch.start()
        self.addCleanup(clock_patch.stop)

    def test_typography_roles_and_literal_schedule_breaks(self):
        activity = dict(load_activities()[0])
        activity["일정·운영시간"] = "교육동 평일 10:00~20:00, 토 10:00~17:00 / 다목적동 하절기 09:00~20:00, 동절기 09:00~18:00"
        with TemporaryDirectory() as temp_dir:
            with patch.object(state_manager, "DB_PATH", Path(temp_dir) / "progress.sqlite3"), patch.object(activity_manager, "load_activities", return_value=[activity]):
                app = AppTest.from_file(str(APP_FILE)).run()
                _show_both(app)
                self.assertFalse(app.exception)
                self.assertIn("기업노동자 전입지원금", [h.value for h in app.header])
                self.assertIn("받을 수 있는 지원", [h.value for h in app.subheader])
                self.assertIn("**운영시간**", [m.value for m in app.markdown])
                self.assertIn("**참여 방법**", [m.value for m in app.markdown])
                self.assertIn("**대상**", [m.value for m in app.markdown])
                rendered_schedule = next(t.value for t in app.text if "교육동 평일" in t.value)
                self.assertIn("\n", rendered_schedule)
                self.assertEqual(rendered_schedule.replace("\n", " "), activity["일정·운영시간"])
                self.assertTrue(any(c.value.startswith("완료 기준:") for c in app.caption))
                self.assertTrue(any("기준으로 확인했어요" in c.value for c in app.caption))
                self.assertFalse(any("가장 간단한 것부터" in i.value for i in app.info))
                self.assertTrue(any("가장 간단한 것부터" in c.value for c in app.caption))
                self.assertEqual(len([c for c in app.checkbox if c.key and c.key.startswith("mission-progress:")]), 26)

    def test_initial_view_hides_results_even_with_saved_records(self):
        with TemporaryDirectory() as temp_dir:
            with patch.object(state_manager, "DB_PATH", Path(temp_dir) / "progress.sqlite3"):
                state_manager.save_mission_group("코디세이", {"M1-1": {"completed": True, "note": "기존 기록"}})
                app = AppTest.from_file(str(APP_FILE)).run()
                self.assertFalse(app.exception)
                self.assertEqual([b.label for b in app.button], ["받을 수 있는 지원 확인하기", "나의 정착 할 일 확인하기"])
                self.assertNotIn("지원과 할 일 확인하기", _visible_text(app))
                self.assertEqual(len(app.expander), 0)
                self.assertFalse(any("확인 결과" in h.value for h in app.subheader))
                self.assertFalse(any("창원에서 해볼 것" in h.value for h in app.subheader))

    def test_policy_button_shows_only_policy_and_keeps_view_on_rerun(self):
        with TemporaryDirectory() as temp_dir:
            with patch.object(state_manager, "DB_PATH", Path(temp_dir) / "progress.sqlite3"):
                app = AppTest.from_file(str(APP_FILE)).run()
                app.button(key="show-policy").click().run()
                self.assertFalse(app.exception)
                self.assertIn("조금 뒤 신청할 수 있어요", _visible_text(app))
                self.assertEqual(len(app.expander), 0)
                self.assertTrue(any(l.url == "https://www.changwon.go.kr/youth/05085/05105/05105.web" for l in app.get("link_button")))
                app.number_input[1].set_value(0).run()
                self.assertIn("현재 조건으로는 신청 대상이 아니에요", _visible_text(app))
                self.assertEqual(len(app.expander), 0)

    def test_journey_button_shows_only_journey_and_preserves_drafts_with_policy(self):
        with TemporaryDirectory() as temp_dir:
            with patch.object(state_manager, "DB_PATH", Path(temp_dir) / "progress.sqlite3"):
                app = AppTest.from_file(str(APP_FILE)).run()
                app.button(key="show-journey").click().run()
                self.assertFalse(app.exception)
                self.assertEqual(len(app.expander), 6)
                self.assertTrue(app.expander[0].proto.expanded)
                self.assertFalse(any("확인 결과" in h.value for h in app.subheader))
                app.checkbox(key="mission-progress:코디세이:M1-1").check().run()
                app.text_input(key="mission-note:코디세이:M1-1").set_value("저장 전 기록").run()
                app.button(key="show-policy").click().run()
                self.assertEqual(len(app.expander), 6)
                self.assertTrue(app.checkbox(key="mission-progress:코디세이:M1-1").value)
                self.assertEqual(app.text_input(key="mission-note:코디세이:M1-1").value, "저장 전 기록")
                app.button(key="save-stage:코디세이:1").click().run()
                self.assertEqual(load_mission_notes("코디세이")["M1-1"], "저장 전 기록")
                self.assertTrue(load_mission_states("코디세이")["M1-1"])
                self.assertIn("조금 뒤 신청할 수 있어요", _visible_text(app))

    def test_neutral_home_district_and_filter_sync_after_results(self):
        with TemporaryDirectory() as temp_dir:
            with patch.object(state_manager, "DB_PATH", Path(temp_dir) / "progress.sqlite3"):
                app = AppTest.from_file(str(APP_FILE)).run()
                self.assertEqual(app.selectbox(key="home_district").value, "지역을 선택해 주세요")
                _show_both(app)
                self.assertEqual(app.selectbox(key="activity_district").value, "창원 전체")
                app.selectbox(key="home_district").select("성산구").run()
                self.assertFalse(app.exception)
                self.assertEqual(app.selectbox(key="activity_district").value, "성산구")
                app.selectbox(key="home_district").select("지역을 선택해 주세요").run()
                self.assertEqual(app.selectbox(key="activity_district").value, "창원 전체")

    def test_resources_render_safely_and_failure_preserves_missions(self):
        with TemporaryDirectory() as temp_dir:
            with patch.object(state_manager, "DB_PATH", Path(temp_dir) / "progress.sqlite3"):
                app = AppTest.from_file(str(APP_FILE)).run()
                _show_both(app)
                self.assertFalse(app.exception)
                urls = [item.proto.url for item in app.get("link_button")]
                self.assertIn("https://sakers.kbl.or.kr/", urls)
                self.assertFalse(any("changdongartvillage.kr" in url for url in urls))
                self.assertNotIn("unverified", _visible_text(app))
                with patch("policy_resource_manager.load_mission_resources", side_effect=ValueError("invalid")):
                    app.run()
                self.assertFalse(app.exception)
                self.assertEqual(len([c for c in app.checkbox if c.key and c.key.startswith("mission-progress:")]), 26)

    def test_saved_stage_does_not_leak_to_another_nickname(self):
        with TemporaryDirectory() as temp_dir:
            with patch.object(state_manager, "DB_PATH", Path(temp_dir) / "progress.sqlite3"):
                state_manager.save_mission_group("다른 사용자", {"M2-1": {"completed": True}})
                app = AppTest.from_file(str(APP_FILE)).run()
                _show_both(app)
                app.button(key="save-stage:코디세이:1").click().run()
                self.assertEqual(app.session_state["last_saved_nickname"], "코디세이")
                app.text_input[0].set_value("다른 사용자").run()
                self.assertFalse(app.exception)
                self.assertFalse(any("저장한 단계:" in c.value for c in app.sidebar.caption))

    def test_representative_profile_renders_policy_timeline_and_all_missions(self):
        with TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "storage" / "progress.sqlite3"
            with patch.object(state_manager, "DB_PATH", database):
                app = AppTest.from_file(str(APP_FILE)).run()
                _show_both(app)

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
                _show_both(app)

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
                _show_both(app)
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
                self.assertIn(expected[0]["이름"], [item.value.replace("\\", "") for item in app.header])
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
                    _show_both(app)

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
                _show_both(app)

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
                selected_activity_id = app.selectbox(key="activity_selection").value
                selected_activity = next(
                    activity
                    for activity in load_activities()
                    if activity["ID"] == selected_activity_id
                )
                source_link = classify_activity_url(selected_activity["공식 URL"])
                if source_link["is_official"]:
                    self.assertIn(
                        (source_link["label"], source_link["url"]),
                        links,
                    )
                else:
                    self.assertFalse(
                        any(label == "공식 안내 보기" for label, _ in links)
                    )
                self.assertIn(
                    ("네이버 지도에서 보기", activity_view(selected_activity, "http://localhost:8501")["naver_map_url"]),
                    links,
                )
                map_links = [
                    item.url for item in app.get("link_button")
                    if item.label.startswith("네이버 지도")
                ]
                self.assertEqual(len(map_links), 1)
                self.assertTrue(map_links[0].startswith("https://map.naver.com/p/search/"))
                self.assertIn(selected_activity["이름"], unquote(map_links[0]))
                self.assertIn(activity_view(selected_activity, "http://localhost:8501")["introduction"], [t.value for t in app.text])
                self.assertFalse(any(item.url.startswith("nmap://") for item in app.get("link_button")))

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
                            _show_both(app)

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
                    _show_both(app)

            self.assertFalse(app.exception)
            rendered_text = [item.value for item in app.text]
            self.assertIn(r"온천 \~\~장소\~\~ \<상세\> \_확인\_", [item.value for item in app.header])
            self.assertIn(
                "온천 06:00~23:00 /\n인피니티풀 10:00~21:00",
                rendered_text,
            )
            self.assertIn("예약 ~~후~~ 확인 <안내>", rendered_text)
            self.assertIn("누구나 *가능*", rendered_text)

    def test_mission_progress_persists_for_same_nickname_only(self):
        with TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "storage" / "progress.sqlite3"
            with patch.object(state_manager, "DB_PATH", database):
                first_session = AppTest.from_file(str(APP_FILE)).run()
                _show_both(first_session)
                first_session.checkbox(key="mission-progress:코디세이:M1-1").check().run()
                first_session.button(key="save-stage:코디세이:1").click().run()

                self.assertFalse(first_session.exception)
                self.assertTrue(
                    load_mission_states("코디세이", database)["M1-1"]
                )

                restored_session = AppTest.from_file(str(APP_FILE)).run()
                restored_session.button(key="show-journey").click().run()
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

    def test_profile_defaults_activity_filter_and_shows_current_stage(self):
        with TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "storage" / "progress.sqlite3"
            with patch.object(state_manager, "DB_PATH", database):
                app = AppTest.from_file(str(APP_FILE)).run()
                app.text_input[0].set_value("단계 확인 사용자").run()
                app.selectbox(key="home_district").select("성산구").run()
                app.text_input(key="neighborhood").set_value("상남동").run()
                app.date_input[0].set_value(date(2026, 8, 20)).run()

                sidebar_text = "\n".join(
                    [item.value for item in app.sidebar.markdown]
                    + [item.value for item in app.sidebar.caption]
                )
                self.assertIn("창원 생활 2개월 차", sidebar_text)
                self.assertIn("성산구 · 상남동", sidebar_text)
                self.assertIn("0 / 4 완료", sidebar_text)
                self.assertIn("0 / 26 완료", sidebar_text)

                _show_both(app)
                self.assertFalse(app.exception)
                self.assertEqual(
                    app.selectbox(key="activity_district").value,
                    "성산구",
                )
                current_stage = next(
                    item
                    for item in app.expander
                    if "창원 생활 2개월 차" in item.label
                )
                self.assertTrue(current_stage.proto.expanded)

    def test_all_six_month_titles_and_only_current_month_default_expansion(self):
        with TemporaryDirectory() as temp_dir:
            with patch.object(state_manager, "DB_PATH", Path(temp_dir) / "progress.sqlite3"):
                for current_month in range(1, 7):
                    with self.subTest(current_month=current_month):
                        with patch.object(progress_manager, "current_settlement_month", return_value=current_month):
                            app = AppTest.from_file(str(APP_FILE)).run()
                            _show_both(app)
                        self.assertFalse(app.exception)
                        stages = list(app.expander)
                        self.assertEqual(len(stages), 6)
                        for month, stage in enumerate(stages, start=1):
                            self.assertIn(f"창원 생활 {month}개월 차", stage.label)
                            self.assertEqual(stage.proto.expanded, month == current_month)
                            self.assertEqual(" · 지금" in stage.label, month == current_month)
                        self.assertEqual(len([c for c in app.checkbox if c.key and c.key.startswith("mission-progress:")]), 26)

    def test_past_and_future_stage_records_survive_month_change_and_restore(self):
        nickname = "여정 기록 사용자"
        with TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "progress.sqlite3"
            with patch.object(state_manager, "DB_PATH", database):
                app = AppTest.from_file(str(APP_FILE)).run()
                app.text_input[0].set_value(nickname).run()
                app.date_input[0].set_value(date(2026, 8, 20)).run()
                _show_both(app)
                # In month 2, month 1 is past and month 6 is future.
                for month, mission_id in ((1, "M1-1"), (6, "M6-1")):
                    app.checkbox(key=f"mission-progress:{nickname}:{mission_id}").check().run()
                    app.text_input(key=f"mission-note:{nickname}:{mission_id}").set_value(f"{month}개월 기록").run()
                    app.button(key=f"save-stage:{nickname}:{month}").click().run()
                app.date_input[0].set_value(date(2026, 3, 20)).run()
                self.assertFalse(app.exception)
                self.assertTrue(app.expander[5].proto.expanded)
                app.checkbox(key=f"mission-progress:{nickname}:M1-1").uncheck().run()
                app.text_input(key=f"mission-note:{nickname}:M1-1").set_value("과거 기록 수정").run()
                app.button(key=f"save-stage:{nickname}:1").click().run()
                restored = AppTest.from_file(str(APP_FILE)).run()
                restored.text_input[0].set_value(nickname).run()
                restored.button(key="show-journey").click().run()
                restored.date_input[0].set_value(date(2026, 3, 20)).run()
                self.assertFalse(restored.exception)
                self.assertEqual(len(restored.expander), 6)
                self.assertFalse(restored.checkbox(key=f"mission-progress:{nickname}:M1-1").value)
                self.assertEqual(restored.text_input(key=f"mission-note:{nickname}:M1-1").value, "과거 기록 수정")
                self.assertTrue(restored.checkbox(key=f"mission-progress:{nickname}:M6-1").value)
                self.assertEqual(restored.text_input(key=f"mission-note:{nickname}:M6-1").value, "6개월 기록")
                self.assertIn("마지막 저장:", "\n".join(c.value for c in restored.sidebar.caption))
                self.assertIn("1 / 26 완료", "\n".join(m.value for m in restored.sidebar.markdown))
                self.assertEqual(load_mission_states("다른 사용자", database), {})

    def test_stage_note_and_check_save_only_on_explicit_button_and_restore(self):
        nickname = "기록 복원 사용자"
        database = None
        with TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "storage" / "progress.sqlite3"
            with patch.object(state_manager, "DB_PATH", database):
                app = AppTest.from_file(str(APP_FILE)).run()
                app.text_input[0].set_value(nickname).run()
                app.date_input[0].set_value(date(2026, 8, 20)).run()
                _show_both(app)

                checkbox_key = f"mission-progress:{nickname}:M2-1"
                note_key = f"mission-note:{nickname}:M2-1"
                app.checkbox(key=checkbox_key).check().run()
                app.text_input(key=note_key).set_value(
                    "10/2 상남동 방문 ~~완료~~ <기록>"
                ).run()

                self.assertEqual(load_mission_states(nickname, database), {})
                self.assertEqual(load_mission_notes(nickname, database), {})

                app.button(key=f"save-stage:{nickname}:2").click().run()
                self.assertFalse(app.exception)
                self.assertTrue(load_mission_states(nickname, database)["M2-1"])
                self.assertEqual(
                    load_mission_notes(nickname, database)["M2-1"],
                    "10/2 상남동 방문 ~~완료~~ <기록>",
                )
                saved_at = load_mission_timestamps(nickname, database)["M2-1"]
                self.assertTrue(saved_at.endswith("+09:00"))
                self.assertTrue(
                    any(
                        format_korea_timestamp(saved_at) in item.value
                        for item in app.sidebar.caption
                    )
                )

            with patch.object(state_manager, "DB_PATH", database):
                restored = AppTest.from_file(str(APP_FILE)).run()
                restored.text_input[0].set_value(nickname).run()
                restored.button(key="show-journey").click().run()
                restored.date_input[0].set_value(date(2026, 8, 20)).run()

                self.assertFalse(restored.exception)
                self.assertTrue(
                    restored.checkbox(key=checkbox_key).value
                )
                self.assertEqual(
                    restored.text_input(key=note_key).value,
                    "10/2 상남동 방문 ~~완료~~ <기록>",
                )


if __name__ == "__main__":
    unittest.main()
