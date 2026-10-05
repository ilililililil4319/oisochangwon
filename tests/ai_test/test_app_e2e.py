import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
import unittest
from datetime import date
from urllib.parse import unquote
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import state_manager
import activity_manager
import progress_manager
from naver_map_links import map_search_name
from policy_engine import evaluate_p01
from policy_matcher import load_policies
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


APP_FILE = Path(__file__).resolve().parents[2] / "app.py"


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


def _demo_app():
    # 시연 페르소나(코디2026)를 채운 상태에서 시작한다.
    app = AppTest.from_file(str(APP_FILE)).run()
    app.button(key="show-profile").click().run()
    app.button(key="fill-demo").click().run()
    return app


def app_module_help():
    import ast
    tree = ast.parse(APP_FILE.read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "PROFILE_FIELD_HELP")
    return ast.literal_eval(node.value)


def _visit(app, page):
    app.button(key=f"nav-{page}").click().run()


def _page_text(app, page):
    _visit(app, page)
    return _visible_text(app)


class ApplicationE2ETests(unittest.TestCase):
    def setUp(self):
        calculate_month = progress_manager.current_settlement_month
        clock_patch = patch.object(
            progress_manager, "current_settlement_month",
            side_effect=lambda move_in_date: calculate_month(move_in_date, date(2026, 10, 2)),
        )
        clock_patch.start()
        self.addCleanup(clock_patch.stop)

    def test_brand_logo_slogan_and_default_nickname(self):
        with TemporaryDirectory() as temp_dir:
            with patch.object(state_manager, "DB_PATH", Path(temp_dir) / "progress.sqlite3"):
                app = AppTest.from_file(str(APP_FILE)).run()
                self.assertFalse(app.exception)
                self.assertEqual(app.session_state["page"], "home")
                home_text = _visible_text(app)
                for section in ("이 서비스가 하는 일", "오이소창원은 이렇게 일해요", "나의 조건 입력하고 시작하기", "예시 화면이에요", "이용 참고사항", "문의"):
                    self.assertIn(section, home_text)
                # 기본 이용과 선택 이메일 수집 범위를 홈 신뢰 안내에서 확인한다.
                trust = next(c.value for c in app.caption if "🔒 기본 이용에는" in c.value)
                self.assertIn("기본 이용에는 실명·연락처가 필요 없어요", trust)
                self.assertIn("이메일 알림을 신청할 때만 이메일 주소를 받아요", trust)
                feature_keys = [b.key for b in app.main.button if b.key in ("show-policy", "show-journey", "show-complaint", "show-dialect")]
                self.assertEqual(len(feature_keys), 4)
                self.assertNotIn("내 정보", home_text)
                # ‘이렇게 일해요’ (10/3 실사용자 피드백): AI 동그라미 표시 없음, 단계 이름
                flow = next(m.value for m in app.markdown if "flow-row" in m.value)
                self.assertNotIn("ai-tag", flow)
                for step in ("2. AI 분석 · 조건 비교", "4. AI 맞춤 결과 안내", "5. 일정 저장 및 알림(선택)"):
                    self.assertIn(step, flow)
                self.assertNotIn("팀이 확인한", flow)
                # 조건 입력 전: 누를 수 없는 물어보기 버튼 대신 잠금 안내만 (10/3 팀 자체 테스트 모바일)
                self.assertNotIn("show-ask", [b.key for b in app.main.button])
                self.assertIn("🔒 조건 입력 후 열려요", [c.value for c in app.main.caption])
                self.assertEqual(len(app.get("image")), 1)
                self.assertFalse(app.button(key="show-profile").disabled)
                self.assertTrue(all(b.disabled for b in app.main.button if b.key and b.key.startswith("show-") and b.key != "show-profile"))
                app.button(key="show-profile").click().run()
                self.assertEqual(app.text_input[0].value, "")
                self.assertIsNone(app.number_input[0].value)
                self.assertIsNone(app.date_input[0].value)
                self.assertIsNone(app.radio(key="employment_status").value)
                self.assertTrue(all(b.disabled for b in app.main.button if b.key and b.key.startswith("show-")))
                self.assertIn("창원 전입일을 입력하면", "\n".join(c.value for c in app.sidebar.caption))
                app.button(key="fill-demo").click().run()
                self.assertEqual(app.text_input[0].value, "코디2026")
                self.assertIn("코디2026님, 준비됐어요.", _visible_text(app))
                self.assertFalse(any(b.disabled for b in app.main.button if b.key and b.key.startswith("show-")))
                app.button(key="go-home-profile").click().run()
                self.assertEqual(len(app.get("image")), 1)
                self.assertIn("창원에서 너의 내일을 응원해!", [h.value for h in app.subheader])
                self.assertFalse(any("🌱" in t.value for t in app.title))
                # 승인된 한 문장 가치제안을 유지하고 반복 초대 문구는 제거한다.
                hero = next(m.value for m in app.markdown if "첫 180일 동안 챙길" in m.value)
                self.assertIn("창원에 새로 전입한 청년이 첫 180일 동안 챙길 혜택과 할 일을 안내해요.", hero)
                self.assertNotIn("함께 떠나볼까요?", hero)
                self.assertNotIn("<br>", hero)
                home = _visible_text(app)
                self.assertNotIn("문의 whwnstn9294", home)
                self.assertNotIn("앱 이용 문의", home)  # 화면 아래 ‘앱 문의’ 한 곳에만
                self.assertIn("정책 24건·정착 할 일 26개·생활 정보 60곳·지역말 2,181개·접수 창구 6곳", home)
                self.assertIn("차량 소지 여부", home)
                # 10/4: 저장 안내는 첫 화면에서 빼고 혜택 화면 저장 버튼 아래로 옮김
                self.assertNotIn("회원가입을 하지 않기 때문에 다시 접속하면 이전 내용이 사라질 수 있어요.", home)
                self.assertEqual(app.button(key="show-profile").label, "나의 조건 확인·수정")
                self.assertIn("먼저 나의 조건을 확인하면 필요한 정보를 맞춤 안내해 드려요", _visible_text(app))
        assets = APP_FILE.parent / "assets"
        for name in ("logo_wide.png", "logo_icon.png"):
            self.assertTrue((assets / name).is_file(), name)

    def test_feature_pages_switch_one_at_a_time_and_keep_values(self):
        with TemporaryDirectory() as temp_dir:
            with patch.object(state_manager, "DB_PATH", Path(temp_dir) / "progress.sqlite3"):
                app = _demo_app()
                app.text_input[0].set_value("화면 전환 사용자").run()
                app.selectbox(key="home_district").select("진해구").run()
                app.text_input(key="neighborhood").set_value("석동").run()
                for key, page, marker in (
                    ("show-policy", "policy", "받을 수 있는 혜택"),
                    ("show-journey", "journey", "이번에 할 일"),
                    ("show-complaint", "complaint", "③ 불편사항 행정 접수안내"),
                    ("show-dialect", "dialect", "④ 창원 지역말 번역"),
                ):
                    with self.subTest(page=page):
                        _visit(app, "profile")
                        app.button(key=key).click().run()
                        self.assertFalse(app.exception)
                        self.assertEqual(app.session_state["page"], page)
                        text = _visible_text(app)
                        self.assertIn(marker, text)
                        self.assertFalse(any(t.key == "neighborhood" for t in app.text_input))
                        self.assertEqual(len(app.date_input), 0)
                        self.assertEqual(len(app.get("image")), 0)
                        others = {"① 창원 청년 맞춤형 혜택 알림": "policy", "이번에 할 일": "journey", "③ 불편사항 행정 접수안내": "complaint", "④ 창원 지역말 번역": "dialect"}
                        for other_marker, other_page in others.items():
                            if other_page != page:
                                self.assertNotIn(other_marker, "\n".join(h.value for h in app.main.subheader))
                app.button(key="go-home-dialect").click().run()
                self.assertEqual(app.session_state["page"], "home")
                _visit(app, "profile")
                self.assertEqual(app.text_input[0].value, "화면 전환 사용자")
                self.assertEqual(app.selectbox(key="home_district").value, "진해구")
                self.assertEqual(app.text_input(key="neighborhood").value, "석동")
                self.assertIn("진해구 · 석동", "\n".join(c.value for c in app.sidebar.caption))

    def test_next_feature_buttons_and_empty_nickname_locks_menu(self):
        with TemporaryDirectory() as temp_dir:
            with patch.object(state_manager, "DB_PATH", Path(temp_dir) / "progress.sqlite3"):
                app = _demo_app()
                app.button(key="show-policy").click().run()
                app.button(key="next-journey").click().run()
                self.assertEqual(app.session_state["page"], "journey")
                app.button(key="next-explore").click().run()
                self.assertEqual(app.session_state["page"], "explore")
                app.button(key="next-complaint").click().run()
                self.assertEqual(app.session_state["page"], "complaint")
                app.button(key="next-dialect").click().run()
                self.assertEqual(app.session_state["page"], "dialect")
                app.button(key="next-ask").click().run()
                self.assertEqual(app.session_state["page"], "ask")
                _visit(app, "profile")
                app.text_input[0].set_value("  ").run()
                self.assertTrue(all(b.disabled for b in app.main.button if b.key.startswith("show-")))
                self.assertTrue(app.button(key="nav-journey").disabled)
                self.assertFalse(app.button(key="nav-profile").disabled)

    def test_profile_field_help_is_visible_without_clicking(self):
        # 10/3 사용자 테스트: ‘?’를 눌러야 보이던 설명을 칸 아래에 항상 보이게
        with TemporaryDirectory() as temp_dir:
            with patch.object(state_manager, "DB_PATH", Path(temp_dir) / "progress.sqlite3"):
                app = AppTest.from_file(str(APP_FILE)).run()
                _visit(app, "profile")
                # 문장마다 줄바꿈("  \n")해서 보여 주므로 비교할 때는 띄어쓰기로 맞춤
                captions = [" ".join(c.value.replace("  \n", " ").split()) for c in app.main.caption]
                for text in app_module_help().values():
                    self.assertIn(" ".join(text.replace("  \n", " ").split()), captions)
                self.assertTrue(any("1년 이상 주민등록을 두고 살았어야" in c for c in captions))
                widgets = list(app.text_input) + list(app.number_input) + list(app.date_input) + list(app.selectbox) + list(app.radio)
                self.assertFalse([w.label for w in widgets if getattr(w, "help", None)])

    def test_contact_email_once_at_bottom_of_every_page(self):
        # 10/3 이혜경: 문의 이메일은 중복 없이 화면 맨 아래 한 곳에만 (사이드바·홈 본문에는 없음)
        contact = "앱 문의: [whwnstn9294@gmail.com](mailto:whwnstn9294@gmail.com)"
        with TemporaryDirectory() as temp_dir:
            with patch.object(state_manager, "DB_PATH", Path(temp_dir) / "progress.sqlite3"):
                app = AppTest.from_file(str(APP_FILE)).run()
                _visit(app, "profile")
                app.button(key="fill-demo").click().run()
                for page in ("home", "profile", "policy", "journey", "explore", "complaint", "dialect", "ask"):
                    with self.subTest(page=page):
                        _visit(app, page)
                        self.assertFalse(app.exception)
                        main_captions = [c.value for c in app.main.caption]
                        self.assertEqual(main_captions[-1], contact)
                        texts = [c.value for c in app.sidebar.caption] + main_captions[:-1] + [m.value for m in app.markdown]
                        self.assertFalse(any("whwnstn9294" in x for x in texts))

    def test_ask_page_answers_with_rule_fallback_links_and_log(self):
        with TemporaryDirectory() as temp_dir:
            with patch.object(state_manager, "DB_PATH", Path(temp_dir) / "progress.sqlite3"), \
                    patch.dict("os.environ", {"ANTHROPIC_API_KEY": "", "OPENAI_API_KEY": "", "LLM_PROVIDER": ""}):
                app = _demo_app()
                app.button(key="show-ask").click().run()
                self.assertFalse(app.exception)
                self.assertIn("AI 모델이 연결되지 않아", _visible_text(app))
                app.button(key="ask-example-0").click().run()
                self.assertFalse(app.exception)
                text = _visible_text(app)
                self.assertIn("기업노동자 전입지원금", text)
                self.assertIn("기본 안내", text)
                self.assertTrue(any(l.url == "https://www.changwon.go.kr/youth/05085/05105/05105.web" for l in app.get("link_button")))
                self.assertEqual(len(app.expander), 1)
                app.chat_input(key="ask_input").set_value("월세 지원 있어?").run()
                self.assertIn("청년월세", _visible_text(app))
                self.assertEqual(len(app.expander), 2)
                app.chat_input(key="ask_input").set_value("집에 불이 났어요").run()
                self.assertIn("119", _visible_text(app))
                _visit(app, "policy")
                _visit(app, "ask")
                self.assertEqual(len(app.expander), 3)
                app.button(key="ask-clear").click().run()
                self.assertEqual(len(app.expander), 0)

    def test_policy_page_shows_five_cards_then_more_and_excluded(self):
        with TemporaryDirectory() as temp_dir:
            with patch.object(state_manager, "DB_PATH", Path(temp_dir) / "progress.sqlite3"):
                app = _demo_app()
                _visit(app, "policy")
                self.assertFalse(app.exception)
                # 해당 없음 카드는 ‘공식 안내 보기’(신청 권유 없음, 10/3 팀 자체 테스트 D-6)
                link_keys = [l for l in app.get("link_button") if l.label in ("안내·신청 링크 열기", "공식 안내 보기")]
                self.assertEqual(len(link_keys), len(load_policies()))
                self.assertEqual(len([l for l in app.get("link_button") if l.label == "공식 안내 보기"]), 7)
                labels = [e.label for e in app.expander]
                self.assertTrue(any(label.startswith("더 보기") for label in labels))
                self.assertTrue(any(label.startswith("해당 없음") for label in labels))
                text = _visible_text(app)
                self.assertIn("해당 가능", text)
                self.assertIn("단정하지 않아요", text)

    def test_journey_policy_missions_link_to_support_cards(self):
        with TemporaryDirectory() as temp_dir:
            with patch.object(state_manager, "DB_PATH", Path(temp_dir) / "progress.sqlite3"):
                app = _demo_app()
                _visit(app, "journey")
                text = _visible_text(app)
                self.assertIn("‘창원 청년 맞춤형 혜택 알림’에서 확인해요", text)
                self.assertNotIn("현재 앱에서 입력한 정보로 확인하는 창원 전입 지원입니다.", text)
                app.button(key="to-policy-M1-3").click().run()
                self.assertEqual(app.session_state["page"], "policy")

    def test_complaint_and_dialect_pages_use_agent_and_reference_lists(self):
        with TemporaryDirectory() as temp_dir:
            with patch.object(state_manager, "DB_PATH", Path(temp_dir) / "progress.sqlite3"), \
                    patch.dict("os.environ", {"ANTHROPIC_API_KEY": "", "OPENAI_API_KEY": "", "LLM_PROVIDER": ""}):
                app = _demo_app()
                app.button(key="show-complaint").click().run()
                self.assertFalse(app.exception)
                self.assertIn("③ 불편사항 행정 접수안내", [h.value for h in app.subheader])
                app.button(key="complaint-example-0").click().run()
                text = _visible_text(app)
                self.assertIn("[높음]", text)
                self.assertIn("1899-1111", text)
                self.assertIn("**단계별 접수 창구**", [m.value for m in app.markdown])
                app.button(key="show-dialect").click().run() if False else _visit(app, "dialect")
                self.assertIn("④ 창원 지역말 번역", [h.value for h in app.subheader])
                app.button(key="dialect-example-0").click().run()
                self.assertIn("문헌 기준 뜻", _visible_text(app))
                self.assertTrue(any("핵심 지역말 30개" in e.label for e in app.expander))

    def test_feature_2_tabs_and_mission_shortcuts(self):
        with TemporaryDirectory() as temp_dir:
            with patch.object(state_manager, "DB_PATH", Path(temp_dir) / "progress.sqlite3"):
                app = _demo_app()
                app.button(key="show-journey").click().run()
                self.assertIn("② 창원 생활 정보 안내 및 일정 편성", [h.value for h in app.subheader])
                app.button(key="tab-explore").click().run()
                self.assertEqual(app.session_state["page"], "explore")
                app.button(key="tab-journey").click().run()
                app.button(key="to-feature-M1-5").click().run()
                self.assertEqual(app.session_state["page"], "dialect")

    def test_missions_follow_job_type(self):
        with TemporaryDirectory() as temp_dir:
            with patch.object(state_manager, "DB_PATH", Path(temp_dir) / "progress.sqlite3"):
                app = _demo_app()
                _visit(app, "journey")
                worker_text = _visible_text(app)
                self.assertIn("4개월 차 · 일·생활 연결", worker_text)
                self.assertIn("(재직자) 우리 회사가 근로자 휴가지원사업에 참여하는지 확인하기", [c.label for c in app.checkbox])
                for job, theme, mission in (
                    ("학생", "4개월 차 · 일·생활 연결", "전입 대학(원)생 생활안정지원(월 6만원) 신청 조건 확인하기"),
                    ("기타", "4개월 차 · 일·생활 연결", "청년 면접수당·자격증 시험 응시료 지원 신청하기"),
                    ("자영업", "4개월 차 · 일·생활 연결", "청년 스포츠 패스 다음 모집 공고에서 자영업 참여 가능 여부 확인하기"),
                ):
                    with self.subTest(job=job):
                        _visit(app, "profile")
                        app.radio(key="employment_status").set_value(job).run()
                        _visit(app, "journey")
                        self.assertFalse(app.exception)
                        labels = [c.label for c in app.checkbox]
                        self.assertIn(mission, labels)
                        self.assertFalse(any(label.startswith("(재직자)") or label.startswith("(중소기업 재직자)") for label in labels))
                        self.assertFalse(any(label.startswith("기업노동자 전입 지원금 신청하기") for label in labels))
                        self.assertIn(theme, _visible_text(app))

    def test_journey_calendar_report_and_opt_in_email(self):
        import email_alerts
        with TemporaryDirectory() as temp_dir:
            with patch.object(state_manager, "DB_PATH", Path(temp_dir) / "progress.sqlite3"), \
                    patch.object(email_alerts, "DB_PATH", Path(temp_dir) / "alerts.sqlite3"), \
                    patch.dict("os.environ", {key: "" for key in email_alerts.SMTP_KEYS}):
                app = _demo_app()
                _visit(app, "journey")
                self.assertFalse(app.exception)
                text = _visible_text(app)
                for label in ("정착 1~2개월", "정착 3-5개월", "정착 6개월 이후"):
                    self.assertIn(label, " ".join(m.value for m in app.markdown))
                for old in ("한 달쯤 뒤", "정착 중반", "여섯 달쯤 뒤"):
                    self.assertNotIn(old, " ".join(m.value for m in app.markdown))
                downloads = [element.proto.label for element in app.get("download_button")]
                self.assertEqual(downloads, ["📅 캘린더에 저장", "📄 정착 리포트 저장"])
                self.assertEqual(app.button(key="email-open-journey").label, "✉️ 이메일 알림 신청")
                # 켜지 않으면 이메일 입력칸이 없다
                self.assertNotIn("alert_email", [t.key for t in app.text_input])
                # 켜도 발송 설정이 없으면 이메일을 받지 않는다
                app.button(key="email-open-journey").click().run()
                self.assertNotIn("alert_email", [t.key for t in app.text_input])
                self.assertTrue(any("이메일을 받지 않아요" in info.value for info in app.info))
                self.assertEqual(email_alerts.count_subscriptions(Path(temp_dir) / "alerts.sqlite3"), 0)
                self.assertIn("일정 저장·알림", text)

    def test_policy_page_save_buttons_open_email_form_on_journey(self):
        import email_alerts
        with TemporaryDirectory() as temp_dir:
            with patch.object(state_manager, "DB_PATH", Path(temp_dir) / "progress.sqlite3"), \
                    patch.object(email_alerts, "DB_PATH", Path(temp_dir) / "alerts.sqlite3"), \
                    patch.dict("os.environ", {key: "" for key in email_alerts.SMTP_KEYS}):
                app = _demo_app()
                _visit(app, "policy")
                self.assertFalse(app.exception)
                labels = [element.proto.label for element in app.get("download_button")]
                self.assertEqual(labels, ["📅 캘린더에 저장", "📄 정착 리포트 저장"])
                app.button(key="email-open-policy").click().run()
                self.assertEqual(app.session_state["page"], "journey")
                self.assertTrue(any("이메일을 받지 않아요" in info.value for info in app.info))
                app.button(key="email-close").click().run()
                self.assertFalse(any("이메일을 받지 않아요" in info.value for info in app.info))
                text = _visible_text(app)
                self.assertNotIn("AI 코디", text)

    def test_email_alert_needs_both_consents_and_can_be_removed(self):
        import email_alerts
        smtp_env = {"SMTP_HOST": "smtp.example.com", "SMTP_PORT": "587", "SMTP_USER": "u",
                    "SMTP_PASSWORD": "p", "SMTP_FROM": "noreply@example.com"}
        sent = []
        with TemporaryDirectory() as temp_dir:
            alerts_db = Path(temp_dir) / "alerts.sqlite3"
            with patch.object(state_manager, "DB_PATH", Path(temp_dir) / "progress.sqlite3"), \
                    patch.object(email_alerts, "DB_PATH", alerts_db), \
                    patch.object(email_alerts, "send_message", lambda config, message, *a: sent.append(message)), \
                    patch.object(email_alerts, "send_due_alerts", lambda *a, **k: 0), \
                    patch.dict("os.environ", smtp_env):
                app = _demo_app()
                _visit(app, "journey")
                app.button(key="email-open-journey").click().run()
                submit = next(b for b in app.button if b.label == "알림 신청하기")
                app.text_input(key="alert_email").input("user@example.com")
                app.checkbox(key="alert_consent_privacy").check()
                submit.click().run()
                self.assertTrue(any("모두 동의" in e.value for e in app.error))
                self.assertEqual(email_alerts.count_subscriptions(alerts_db), 0)
                self.assertEqual(sent, [])
                app.checkbox(key="alert_consent_receive").check()
                next(b for b in app.button if b.label == "알림 신청하기").click().run()
                self.assertFalse(app.exception)
                self.assertEqual(email_alerts.count_subscriptions(alerts_db), 1)
                self.assertEqual(len(sent), 1)
                self.assertTrue(any("신청했어요" in m.value for m in app.success))
                self.assertEqual(app.text_input(key="alert_email").value, "")
                app.text_input(key="unsubscribe_email").input("user@example.com")
                next(b for b in app.button if b.label == "알림 해지·이메일 삭제").click().run()
                self.assertEqual(email_alerts.count_subscriptions(alerts_db), 0)
                self.assertTrue(any("삭제했어요" in m.value for m in app.success))

    def test_vehicle_choice_changes_policy_order_explore_and_sidebar(self):
        with TemporaryDirectory() as temp_dir:
            with patch.object(state_manager, "DB_PATH", Path(temp_dir) / "progress.sqlite3"):
                app = _demo_app()
                self.assertEqual(app.radio(key="vehicle").value, "없음")
                self.assertIn("차량 없음 · 대중교통·자전거로 이동", [c.value for c in app.sidebar.caption])
                _visit(app, "policy")
                self.assertIn("K", app.header[0].value)  # K-패스가 맨 앞
                _visit(app, "explore")
                self.assertIn("대중교통 경로로 안내해요", _visible_text(app))
                app.button(key="explore-kpass").click().run()
                self.assertEqual(app.session_state["page"], "policy")
                _visit(app, "profile")
                app.radio(key="vehicle").set_value("있음").run()
                self.assertIn("차량 있음", [c.value for c in app.sidebar.caption])
                _visit(app, "policy")
                self.assertNotIn("K", app.header[0].value)
                _visit(app, "explore")
                self.assertNotIn("대중교통 경로로 안내해요", _visible_text(app))

    def test_buttons_have_no_numbers_and_car_only_place_warning(self):
        with TemporaryDirectory() as temp_dir:
            with patch.object(state_manager, "DB_PATH", Path(temp_dir) / "progress.sqlite3"):
                app = _demo_app()
                labels = [b.label for b in app.button]
                self.assertFalse(any(label[:1] in "①②③④" for label in labels))
                _visit(app, "explore")
                app.selectbox(key="activity_selection").select("A326").run()
                text = _visible_text(app)
                self.assertIn("차량으로 가는 것을 권장해요", text)
                self.assertNotIn("대중교통 경로로 안내해요", text)

    def test_clear_profile_and_journey_needs_move_in_date(self):
        with TemporaryDirectory() as temp_dir:
            with patch.object(state_manager, "DB_PATH", Path(temp_dir) / "progress.sqlite3"):
                app = _demo_app()
                app.button(key="clear-profile").click().run()
                self.assertEqual(app.text_input[0].value, "")
                self.assertIsNone(app.date_input[0].value)
                app.text_input[0].set_value("새 사용자").run()
                app.button(key="show-journey").click().run()
                self.assertFalse(app.exception)
                self.assertIn("창원 전입일을 입력해 주세요", _visible_text(app))
                self.assertEqual(len(app.expander), 0)
                _visit(app, "policy")
                self.assertIn("정보를 조금 더 입력해 주세요", _visible_text(app))
                _visit(app, "explore")
                self.assertFalse(app.exception)
                self.assertIn("창원에서 해볼 것", _visible_text(app))

    def test_typography_roles_and_literal_schedule_breaks(self):
        activity = dict(load_activities()[0])
        activity["일정·운영시간"] = "교육동 평일 10:00~20:00, 토 10:00~17:00 / 다목적동 하절기 09:00~20:00, 동절기 09:00~18:00"
        with TemporaryDirectory() as temp_dir:
            with patch.object(state_manager, "DB_PATH", Path(temp_dir) / "progress.sqlite3"), patch.object(activity_manager, "load_activities", return_value=[activity]):
                app = _demo_app()
                _visit(app, "policy")
                self.assertFalse(app.exception)
                self.assertIn("기업노동자 전입지원금", [h.value for h in app.header])
                self.assertIn("① 창원 청년 맞춤형 혜택 알림", [h.value for h in app.subheader])
                _visit(app, "explore")
                self.assertIn("**운영시간**", [m.value for m in app.markdown])
                self.assertIn("**참여 방법**", [m.value for m in app.markdown])
                self.assertIn("**대상**", [m.value for m in app.markdown])
                rendered_schedule = next(t.value for t in app.text if "교육동 평일" in t.value)
                self.assertIn("\n", rendered_schedule)
                self.assertEqual(rendered_schedule.replace("\n", " "), activity["일정·운영시간"])
                self.assertTrue(any("기준으로 확인했어요" in c.value for c in app.caption))
                _visit(app, "journey")
                self.assertTrue(any(c.value.startswith("완료 기준:") for c in app.caption))
                self.assertFalse(any("가장 간단한 것부터" in i.value for i in app.info))
                self.assertTrue(any("가장 간단한 것부터" in c.value for c in app.caption))
                self.assertEqual(len([c for c in app.checkbox if c.key and c.key.startswith("mission-progress:")]), 26)

    def test_changdong_activity_renders_with_current_and_missing_introduction(self):
        target = next(a for a in load_activities() if a["ID"] == "A40")
        self.assertEqual(target["이름"], "창동예술촌 '창동쪽샘길' 플리마켓·아트클래스")
        original_view = activity_manager.activity_view
        for legacy_view in (False, True):
            with self.subTest(legacy_view=legacy_view), TemporaryDirectory() as temp_dir:
                def convert(activity, app_name):
                    view = original_view(activity, app_name)
                    if legacy_view:
                        view.pop("introduction")
                    return view
                with patch.object(state_manager, "DB_PATH", Path(temp_dir) / "progress.sqlite3"), patch.object(activity_manager, "activity_view", side_effect=convert):
                    app = _demo_app()
                    _visit(app, "explore")
                    app.selectbox(key="activity_selection").select("A40").run()
                    self.assertFalse(app.exception)
                    self.assertTrue(any("창동쪽샘길" in h.value for h in app.header))
                    self.assertIn(target["대상"], [t.value for t in app.text])
                    self.assertTrue(any(l.label == "네이버 지도에서 보기" for l in app.get("link_button")))
                    if not legacy_view:
                        self.assertIn(original_view(target, "http://localhost:8501")["introduction"], [t.value for t in app.text])

    def test_initial_view_hides_results_even_with_saved_records(self):
        with TemporaryDirectory() as temp_dir:
            with patch.object(state_manager, "DB_PATH", Path(temp_dir) / "progress.sqlite3"):
                state_manager.save_mission_group("코디2026", {"M1-1": {"completed": True, "note": "기존 기록"}})
                app = _demo_app()
                self.assertFalse(app.exception)
                self.assertEqual([b.label for b in app.main.button], ["← 처음으로", "예시 정보로 채우기 (코디2026)", "입력 지우기", "내 맞춤 혜택 확인하기 →", "정착 일정 만들기", "오이소창원에게 바로 물어보기", "불편사항 행정 접수안내", "창원 지역말 번역"])
                self.assertEqual([b.label for b in app.sidebar.button], ["홈", "조건 입력 · 완료", "맞춤 혜택 · 해당 가능 4건", "정착 일정 · 이번 단계 1/5", "생활 정보", "불편사항", "지역말", "오이소창원에게 물어보기"])
                self.assertEqual(len(app.get("image")), 0)
                self.assertNotIn("지원과 할 일 확인하기", _visible_text(app))
                self.assertEqual(len(app.expander), 0)
                self.assertFalse(any("확인 결과" in h.value for h in app.subheader))
                self.assertFalse(any("창원에서 해볼 것" in h.value for h in app.subheader))

    def test_policy_button_shows_only_policy_and_keeps_view_on_rerun(self):
        with TemporaryDirectory() as temp_dir:
            with patch.object(state_manager, "DB_PATH", Path(temp_dir) / "progress.sqlite3"):
                app = _demo_app()
                app.button(key="show-policy").click().run()
                self.assertFalse(app.exception)
                self.assertIn("조금 뒤 신청할 수 있어요", _visible_text(app))
                self.assertFalse(any("창원 생활" in e.label for e in app.expander))
                self.assertTrue(any(l.url == "https://www.changwon.go.kr/youth/05085/05105/05105.web" for l in app.get("link_button")))
                self.assertEqual(len(app.number_input), 0)
                self.assertNotIn("창원에서 해볼 것", _visible_text(app))
                app.run()
                self.assertIn("조금 뒤 신청할 수 있어요", _visible_text(app))
                _visit(app, "profile")
                app.number_input[1].set_value(0).run()
                _visit(app, "policy")
                self.assertIn("현재 조건으로는 신청 대상이 아니에요", _visible_text(app))
                self.assertFalse(any("창원 생활" in e.label for e in app.expander))

    def test_journey_button_shows_only_journey_and_preserves_drafts_with_policy(self):
        with TemporaryDirectory() as temp_dir:
            with patch.object(state_manager, "DB_PATH", Path(temp_dir) / "progress.sqlite3"):
                app = _demo_app()
                app.button(key="show-journey").click().run()
                self.assertFalse(app.exception)
                self.assertEqual(len(app.expander), 6)
                self.assertFalse(app.expander[0].proto.expanded)
                self.assertFalse(any("확인 결과" in h.value for h in app.subheader))
                app.checkbox(key="mission-progress:코디2026:M1-1").check().run()
                app.text_input(key="mission-note:코디2026:M1-1").set_value("저장 전 기록").run()
                _visit(app, "policy")
                self.assertFalse(any("창원 생활" in e.label for e in app.expander))
                self.assertIn("조금 뒤 신청할 수 있어요", _visible_text(app))
                _visit(app, "journey")
                self.assertEqual(len(app.expander), 6)
                self.assertNotIn("조금 뒤 신청할 수 있어요", _visible_text(app))
                self.assertTrue(app.checkbox(key="mission-progress:코디2026:M1-1").value)
                self.assertEqual(app.text_input(key="mission-note:코디2026:M1-1").value, "저장 전 기록")
                app.button(key="save-stage:코디2026:1").click().run()
                self.assertEqual(load_mission_notes("코디2026")["M1-1"], "저장 전 기록")
                self.assertTrue(load_mission_states("코디2026")["M1-1"])

    def test_neutral_home_district_and_filter_sync_after_results(self):
        with TemporaryDirectory() as temp_dir:
            with patch.object(state_manager, "DB_PATH", Path(temp_dir) / "progress.sqlite3"):
                app = _demo_app()
                self.assertEqual(app.selectbox(key="home_district").value, "지역을 선택해 주세요")
                _visit(app, "explore")
                self.assertEqual(app.selectbox(key="activity_district").value, "창원 전체")
                _visit(app, "profile")
                app.selectbox(key="home_district").select("성산구").run()
                _visit(app, "explore")
                self.assertFalse(app.exception)
                self.assertEqual(app.selectbox(key="activity_district").value, "성산구")
                _visit(app, "profile")
                app.selectbox(key="home_district").select("지역을 선택해 주세요").run()
                _visit(app, "explore")
                self.assertEqual(app.selectbox(key="activity_district").value, "창원 전체")

    def test_resources_render_safely_and_failure_preserves_missions(self):
        with TemporaryDirectory() as temp_dir:
            with patch.object(state_manager, "DB_PATH", Path(temp_dir) / "progress.sqlite3"):
                app = _demo_app()
                _visit(app, "journey")
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
                app = _demo_app()
                _visit(app, "journey")
                app.button(key="save-stage:코디2026:1").click().run()
                self.assertEqual(app.session_state["last_saved_nickname"], "코디2026")
                _visit(app, "profile")
                app.text_input[0].set_value("다른 사용자").run()
                self.assertFalse(app.exception)
                self.assertFalse(any("저장한 단계:" in c.value for c in app.sidebar.caption))

    def test_representative_profile_renders_policy_timeline_and_all_missions(self):
        with TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "storage" / "progress.sqlite3"
            with patch.object(state_manager, "DB_PATH", database):
                app = _demo_app()
                rendered_text = "\n".join(
                    _page_text(app, page) for page in ("profile", "explore", "policy", "journey")
                )

                self.assertFalse(app.exception)
                self.assertIn("조금 뒤 신청할 수 있어요", rendered_text)
                self.assertIn("받을 수 있는 혜택", rendered_text)
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
                    "M1-1",
                    "M6-5",
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
                app = _demo_app()
                app.number_input[1].set_value(0).run()
                _visit(app, "policy")

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
                app = _demo_app()
                _visit(app, "explore")
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
                _visit(app, "journey")
                _visit(app, "explore")
                self.assertEqual(app.selectbox(key="activity_district").value, "성산구")
                self.assertEqual(app.selectbox(key="activity_category").value, "문화생활")

    def test_explore_first_place_is_kpop_festival(self):
        # 10/4 이혜경: 생활 정보 첫 화면의 첫 장소·‘자세히 볼 곳’은 2026 창원 K-POP 월드페스티벌 · 성산구
        with TemporaryDirectory() as temp_dir:
            with patch.object(state_manager, "DB_PATH", Path(temp_dir) / "progress.sqlite3"):
                app = _demo_app()
                _visit(app, "explore")
                self.assertFalse(app.exception)
                selector = app.selectbox(key="activity_selection")
                self.assertEqual(selector.value, "A143")
                self.assertEqual(selector.options[0], "2026 창원 K-POP 월드페스티벌 · 성산구")
                self.assertIn("2026 창원 K-POP 월드페스티벌", [h.value.replace("\\", "") for h in app.header])

    def test_detail_selection_matches_detail_after_filter_change(self):
        # 10/3 팀 자체 테스트 G-2: 전체에서 북 페스타를 본 뒤 성산구·야경 산책으로 바꾸면 선택창과 상세가 같은 장소
        with TemporaryDirectory() as temp_dir:
            with patch.object(state_manager, "DB_PATH", Path(temp_dir) / "progress.sqlite3"):
                app = _demo_app()
                _visit(app, "explore")
                first = app.selectbox(key="activity_selection").options[0]
                app.selectbox(key="activity_selection").set_value(app.selectbox(key="activity_selection").value).run()
                app.selectbox(key="activity_district").select("성산구").run()
                app.selectbox(key="activity_category").select("야경·산책").run()
                self.assertFalse(app.exception)
                selector = app.selectbox(key="activity_selection")
                chosen = next(a for a in load_activities() if a["ID"] == selector.value)
                self.assertEqual(chosen["생활권(구)"], "성산구")
                self.assertIn(chosen["이름"], [h.value.replace("\\", "") for h in app.header])
                self.assertEqual(selector.options[0], f"{chosen['이름']} · {chosen['생활권(구)']}")
                self.assertTrue(first)

    def test_activity_data_failure_does_not_hide_p0_results(self):
        with TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "storage" / "progress.sqlite3"
            with patch.object(state_manager, "DB_PATH", database):
                with patch.object(
                    activity_manager,
                    "load_activities",
                    side_effect=ValueError("invalid data"),
                ):
                    app = _demo_app()
                    visible_text = _page_text(app, "explore")
                    visible_text += _page_text(app, "policy")

                self.assertFalse(app.exception)
                self.assertIn("조금 뒤 신청할 수 있어요", visible_text)
                self.assertIn(
                    "지원 확인과 정착 할 일은 계속 이용할 수 있어요",
                    visible_text,
                )
                self.assertNotIn("ValueError", visible_text)

    def test_map_button_ignores_stale_activity_view_home_url(self):
        original_view = activity_manager.activity_view

        def stale_view(activity, app_name):
            return dict(original_view(activity, app_name), naver_map_url="https://map.naver.com/p/")

        activities = load_activities()
        # Civic gym is not in the curated 58: use a named fixture without adding data.
        civic = dict(activities[0], 이름="시민생활체육관", **{"생활권(구)": "성산구"})
        samples = [civic] + [a for a in activities if a["이름"] in ("스파더스페이스", "경남도립미술관", "스펀지파크(청년문화예술복합공간)", "창동예술촌 '창동쪽샘길' 플리마켓·아트클래스")]
        self.assertEqual(len(samples), 5)
        for activity in samples:
            with self.subTest(name=activity["이름"]), TemporaryDirectory() as temp_dir:
                with patch.object(state_manager, "DB_PATH", Path(temp_dir) / "progress.sqlite3"), patch.object(
                    activity_manager, "activity_view", side_effect=stale_view
                ), patch.object(activity_manager, "load_activities", return_value=[activity]):
                    app = _demo_app()
                    _visit(app, "explore")
                    self.assertFalse(app.exception)
                    link = next(x for x in app.get("link_button") if x.label == "네이버 지도에서 보기")
                    self.assertTrue(link.url.startswith("https://map.naver.com/p/search/"))
                    self.assertEqual(unquote(link.url.split("/p/search/", 1)[1]),
                                     f'{map_search_name(activity["이름"])} 창원')

    def test_youth_policy_and_activity_links_use_their_verified_labels(self):
        with TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "storage" / "progress.sqlite3"
            with patch.object(state_manager, "DB_PATH", database):
                app = _demo_app()
                _visit(app, "policy")

                self.assertFalse(app.exception)
                self.assertIn(
                    (
                        "창원시 청년정책 전체 보기",
                        "https://www.changwon.go.kr/youth/05085/05105/05105.web",
                    ),
                    {(item.label, item.url) for item in app.get("link_button")},
                )
                _visit(app, "explore")
                links = {
                    (item.label, item.url)
                    for item in app.get("link_button")
                }
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
                self.assertIn(map_search_name(selected_activity["이름"]), unquote(map_links[0]))
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
                            app = _demo_app()
                            _visit(app, "explore")

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
                    app = _demo_app()
                    _visit(app, "explore")

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
                first_session = _demo_app()
                _visit(first_session, "journey")
                first_session.checkbox(key="mission-progress:코디2026:M1-1").check().run()
                first_session.button(key="save-stage:코디2026:1").click().run()

                self.assertFalse(first_session.exception)
                self.assertTrue(
                    load_mission_states("코디2026", database)["M1-1"]
                )

                restored_session = _demo_app()
                restored_session.button(key="show-journey").click().run()
                self.assertFalse(restored_session.exception)
                self.assertTrue(
                    restored_session.checkbox(
                        key="mission-progress:코디2026:M1-1"
                    ).value
                )
                self.assertFalse(
                    restored_session.checkbox(
                        key="mission-progress:코디2026:M1-2"
                    ).value
                )

                _visit(restored_session, "profile")
                restored_session.text_input[0].set_value("다른 사용자").run()
                _visit(restored_session, "journey")
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
                app = _demo_app()
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
                self.assertIn("0 / 3 완료", sidebar_text)
                self.assertIn("0 / 26 완료", sidebar_text)

                _visit(app, "explore")
                self.assertFalse(app.exception)
                self.assertEqual(
                    app.selectbox(key="activity_district").value,
                    "성산구",
                )
                _visit(app, "journey")
                current_stage = next(
                    item
                    for item in app.expander
                    if "2개월 차" in item.label
                )
                self.assertFalse(current_stage.proto.expanded)

    def test_all_six_month_titles_and_all_default_collapsed(self):
        with TemporaryDirectory() as temp_dir:
            with patch.object(state_manager, "DB_PATH", Path(temp_dir) / "progress.sqlite3"):
                for current_month in range(1, 7):
                    with self.subTest(current_month=current_month):
                        with patch.object(progress_manager, "current_settlement_month", return_value=current_month):
                            app = _demo_app()
                            _visit(app, "journey")
                        self.assertFalse(app.exception)
                        stages = list(app.expander)
                        self.assertEqual(len(stages), 6)
                        for month, stage in enumerate(stages, start=1):
                            self.assertTrue(stage.label.startswith(f"{month}개월 차 · "))
                            self.assertFalse(stage.proto.expanded)
                            self.assertEqual(" · 지금" in stage.label, month == current_month)
                        self.assertEqual(len([c for c in app.checkbox if c.key and c.key.startswith("mission-progress:")]), 26)

    def test_past_and_future_stage_records_survive_month_change_and_restore(self):
        nickname = "여정 기록 사용자"
        with TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "progress.sqlite3"
            with patch.object(state_manager, "DB_PATH", database):
                app = _demo_app()
                app.text_input[0].set_value(nickname).run()
                app.date_input[0].set_value(date(2026, 8, 20)).run()
                _visit(app, "journey")
                # In month 2, month 1 is past and month 6 is future.
                for month, mission_id in ((1, "M1-1"), (6, "M6-1")):
                    app.checkbox(key=f"mission-progress:{nickname}:{mission_id}").check().run()
                    app.text_input(key=f"mission-note:{nickname}:{mission_id}").set_value(f"{month}개월 기록").run()
                    app.button(key=f"save-stage:{nickname}:{month}").click().run()
                _visit(app, "profile")
                app.date_input[0].set_value(date(2026, 3, 20)).run()
                _visit(app, "journey")
                self.assertFalse(app.exception)
                self.assertFalse(app.expander[5].proto.expanded)
                app.checkbox(key=f"mission-progress:{nickname}:M1-1").uncheck().run()
                app.text_input(key=f"mission-note:{nickname}:M1-1").set_value("과거 기록 수정").run()
                app.button(key=f"save-stage:{nickname}:1").click().run()
                restored = _demo_app()
                restored.text_input[0].set_value(nickname).run()
                restored.date_input[0].set_value(date(2026, 3, 20)).run()
                restored.button(key="show-journey").click().run()
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
                app = _demo_app()
                app.text_input[0].set_value(nickname).run()
                app.date_input[0].set_value(date(2026, 8, 20)).run()
                _visit(app, "journey")

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
                restored = _demo_app()
                restored.text_input[0].set_value(nickname).run()
                restored.date_input[0].set_value(date(2026, 8, 20)).run()
                restored.button(key="show-journey").click().run()

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
