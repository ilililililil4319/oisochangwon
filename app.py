import streamlit as st
import streamlit.components.v1 as components
from datetime import date
from pathlib import Path
import os
import re

from agent import DEFAULT_MODELS, MODEL_LABELS, make_client, run_agent
from agent import _items as _agent_items


def load_complaint_channels():
    return _agent_items("complaint_channels.json")


def load_dialects():
    return _agent_items("dialects_core30.json")
from activity_manager import (
    activity_view,
    filter_activities,
    get_activity_filter_options,
    load_activities,
)
from naver_map_links import naver_map_web_url
from policy_engine import evaluate_p01
from policy_matcher import LEVELS, load_policies, match_policies
from mission_manager import group_missions_by_month, load_missions
from policy_resource_manager import load_mission_resources
from progress_manager import (
    calculate_mission_progress,
    current_settlement_month,
    encouragement_message,
)
from settlement_engine import build_settlement_plan
from state_manager import (
    format_korea_timestamp,
    load_mission_notes,
    load_mission_states,
    load_mission_timestamps,
    save_mission_group,
)


MILESTONE_LABELS = {
    0: "전입한 날",
    7: "첫 주",
    30: "한 달쯤 뒤",
    90: "정착 중반",
    180: "여섯 달쯤 뒤",
}
MONTH_LABELS = {
    1: "1개월 차",
    2: "2개월 차",
    3: "3개월 차",
    4: "4개월 차",
    5: "5개월 차",
    6: "6개월 차",
}
PROFILE_FIELD_LABELS = {
    "move_in_date": "창원 전입일",
    "previous_residence_years": "전입 전 다른 지역 거주 기간",
    "employed_in_changwon": "창원 사업장 재직 여부",
}
CITY_YOUTH_POLICY_URL = "https://www.changwon.go.kr/youth/05085/05105/05105.web"
HOME_DISTRICTS = ["의창구", "성산구", "마산합포구", "마산회원구", "진해구"]
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
LOGO_WIDE_PATH = ASSETS_DIR / "logo_wide.png"
LOGO_ICON_PATH = ASSETS_DIR / "logo_icon.png"
LOGO_WIDTH = 560  # PC에서는 560px, 모바일에서는 화면 폭에 맞춰 자동으로 줄어듦
SLOGAN = "창원에서 너의 내일을 응원해!"
CONTACT_EMAIL = "whwnstn9294@gmail.com"
CONTACT_TEXT = f"앱 문의: [{CONTACT_EMAIL}](mailto:{CONTACT_EMAIL})"
DEFAULT_NICKNAME = "코디2026"


# Native heading and caption roles share one small typography layer.
READABILITY_CSS = """
<style>
[data-testid="stMainBlockContainer"] {max-width: 48rem;}
[data-testid="stText"], [data-testid="stMarkdownContainer"] p {
    line-height: 1.6; overflow-wrap: anywhere; white-space: pre-wrap;
}
h2 {font-size: 1.8rem !important; font-weight: 700 !important;}
h3 {font-size: 1.25rem !important; font-weight: 600 !important;}
[data-testid="stExpander"] summary p {font-size: 1.4rem; font-weight: 700; line-height: 1.5;}
[data-testid="stExpander"] [data-testid="stCheckbox"] p {font-size: 1.35rem; font-weight: 600;}
[data-testid="stExpander"] [data-testid="stTextInput"] label p {font-size: .85rem; font-weight: 400;}
[data-testid="stExpander"] [data-testid="stCheckbox"] {margin-top: 1.25rem;}
[data-testid="stLinkButton"], [data-testid="stButton"] {margin-block: .35rem;}
[class*="st-key-policy-card-"] h2 {font-size: 1.3rem !important;}
[data-testid="stChatMessage"] [data-testid="stExpander"] summary p {font-size: 1rem; font-weight: 600;}
/* 로고 톤앤매너: 남색 #063465(기본) · 주황 #FE6A01(강조) */
h1, h2, h3 {color: #063465 !important;}
.st-key-slogan h3 {color: #FE6A01 !important;}
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"] {
    background-color: #063465 !important; border-color: #063465 !important; color: #FFFFFF !important;
}
[data-testid="stBaseButton-primary"]:hover, [data-testid="stBaseButton-primaryFormSubmit"]:hover {
    background-color: #FE6A01 !important; border-color: #FE6A01 !important;
}
[data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-secondaryFormSubmit"], [data-testid="stBaseLinkButton-secondary"] {
    border-color: #9FB0C6 !important; color: #063465 !important; background-color: #FFFFFF !important;
}
[data-testid="stBaseButton-secondary"]:hover, [data-testid="stBaseLinkButton-secondary"]:hover {
    border-color: #FE6A01 !important; color: #FE6A01 !important;
}
[data-testid="stProgress"] [role="progressbar"] > div > div > div {background-color: #FE6A01 !important;}
[data-testid="stSidebar"] {border-right: 3px solid #FE6A01;}
[data-testid="stExpander"] details {border-color: #D5DDE7;}
[data-testid="stExpander"] summary:hover p {color: #FE6A01;}
</style>
"""


def _content_title(value):
    # Headings accept Markdown; escape source text to preserve its literal meaning.
    escaped = re.sub(r"([\\`*_{}\[\]()<>#+.!|~-])", r"\\\1", value)
    st.header(escaped, anchor=False)


def _detail(label, value):
    st.markdown(f"**{label}**")
    st.text(value)


def _schedule_lines(value):
    # Retain the original separators and words; only add line breaks.
    return re.sub(r"([/,;]) +", r"\1\n", value)


def _sync_activity_district():
    selected_home_district = st.session_state["home_district"]
    st.session_state["activity_district"] = (
        selected_home_district
        if selected_home_district in HOME_DISTRICTS
        else "창원 전체"
    )



# --- 화면(page) 구성 -------------------------------------------------------
# 한 번에 한 화면만 그린다. 화면 이동은 버튼의 on_click 콜백이 page 값을 바꾼다.
PAGE_PROFILE = "profile"
PAGE_POLICY = "policy"
PAGE_JOURNEY = "journey"
PAGE_EXPLORE = "explore"
PAGE_ASK = "ask"
PAGE_COMPLAINT = "complaint"
PAGE_DIALECT = "dialect"
# 기획안 핵심기능 ①~④와 같은 이름을 쓴다.
FEATURE_1 = "① 창원 청년 맞춤형 혜택 알림"
FEATURE_2 = "② 창원 생활 정보 안내 및 일정 편성"
FEATURE_3 = "③ 불편사항 행정 접수안내"
FEATURE_4 = "④ 창원 지역말 번역"
ASK_LABEL = "AI 코디에게 물어보기"
FEATURE_2_TABS = {PAGE_JOURNEY: "정착 할 일 · 1~6개월 일정", PAGE_EXPLORE: "창원 생활 정보 둘러보기"}
# 사이드바 메뉴: (page, 버튼 이름)
PAGE_LABELS = {
    PAGE_PROFILE: "내 정보",
    PAGE_ASK: ASK_LABEL,
    PAGE_POLICY: FEATURE_1,
    PAGE_JOURNEY: "└ " + FEATURE_2_TABS[PAGE_JOURNEY],
    PAGE_EXPLORE: "└ " + FEATURE_2_TABS[PAGE_EXPLORE],
    PAGE_COMPLAINT: FEATURE_3,
    PAGE_DIALECT: FEATURE_4,
}
FEATURE_BUTTONS = (
    (PAGE_ASK, f"{ASK_LABEL} (한 문장 질문)", "show-ask"),
    (PAGE_POLICY, FEATURE_1, "show-policy"),
    (PAGE_JOURNEY, FEATURE_2, "show-journey"),
    (PAGE_COMPLAINT, FEATURE_3, "show-complaint"),
    (PAGE_DIALECT, FEATURE_4, "show-dialect"),
)
DISTRICT_PLACEHOLDER = "지역을 선택해 주세요"
EMPLOYMENT_OPTIONS = ("재직 중", "재직 중 아님")
VEHICLE_OPTIONS = ("없음", "있음")
VEHICLE_SUMMARY = {"없음": "차량 없음 · 대중교통·자전거로 이동", "있음": "차량 있음"}
# 실사용자 테스트용: 처음 화면은 빈 칸으로 시작한다.
PROFILE_DEFAULTS = {
    "nickname": "",
    "age": None,
    "move_in_date": None,
    "home_district": DISTRICT_PLACEHOLDER,
    "neighborhood": "",
    "previous_residence_years": None,
    "employment_status": None,
    "vehicle": None,
}
# 시연·팀 검수용 페르소나(코디2026) — 버튼을 눌렀을 때만 채운다.
DEMO_PROFILE = {
    "nickname": DEFAULT_NICKNAME,
    "age": 28,
    "move_in_date": date(2026, 9, 20),
    "home_district": DISTRICT_PLACEHOLDER,
    "neighborhood": "",
    "previous_residence_years": 2,
    "employment_status": EMPLOYMENT_OPTIONS[0],
    "vehicle": "없음",
}
# 화면에 그려지지 않은 위젯 값도 지워지지 않게 지켜 둘 키
PERSISTENT_KEYS = ("activity_district", "activity_category", "activity_selection")
PERSISTENT_PREFIXES = ("mission-progress:", "mission-note:")


def _go(page):
    st.session_state["page"] = page


def _fill_profile(values):
    for key, value in values.items():
        st.session_state[key] = value
    _sync_activity_district()


def _keep_widget_values():
    # Streamlit은 화면에 없는 위젯의 값을 지운다. 매 실행 시작에 값을 다시 넣어 보존한다.
    for key, default in PROFILE_DEFAULTS.items():
        st.session_state[key] = st.session_state.get(key, default)
    for key in list(st.session_state.keys()):
        if key in PERSISTENT_KEYS or str(key).startswith(PERSISTENT_PREFIXES):
            st.session_state[key] = st.session_state[key]


def _back_home_button(position):
    st.button(
        "← 처음으로",
        key=f"go-home-{position}",
        on_click=_go,
        args=(PAGE_PROFILE,),
    )


def _next_feature_button(target_page, label):
    st.divider()
    st.button(
        label,
        key=f"next-{target_page}",
        type="primary",
        on_click=_go,
        args=(target_page,),
    )


st.set_page_config(
    page_title="오이소창원",
    page_icon=str(LOGO_ICON_PATH),
    layout="centered",
)

st.html(READABILITY_CSS)

_keep_widget_values()
st.session_state.setdefault("page", PAGE_PROFILE)

nickname = st.session_state["nickname"]
user_key = nickname.strip()
if not user_key:
    st.session_state["page"] = PAGE_PROFILE
page = st.session_state["page"]

saved_mission_states = load_mission_states(user_key) if user_key else {}
saved_mission_notes = load_mission_notes(user_key) if user_key else {}
saved_mission_timestamps = load_mission_timestamps(user_key) if user_key else {}


# --- ① 내 정보(첫 화면) -----------------------------------------------------
def render_profile_page():
    st.image(str(LOGO_WIDE_PATH), width=LOGO_WIDTH)
    with st.container(key="slogan"):
        st.subheader(SLOGAN, anchor=False)
    st.write(
        "창원에 새로 전입한 청년의 초기 정착을 돕는 코디네이터 Agent입니다."
    )
    st.divider()

    with st.container(horizontal=True, wrap=True):
        st.button(
            f"예시 정보로 채우기 ({DEFAULT_NICKNAME})",
            key="fill-demo",
            on_click=_fill_profile,
            args=(DEMO_PROFILE,),
        )
        st.button(
            "입력 지우기",
            key="clear-profile",
            on_click=_fill_profile,
            args=(PROFILE_DEFAULTS,),
        )
    st.text_input("닉네임", key="nickname", placeholder="실명 대신 쓸 이름 (예: 창원새내기)", max_chars=20)
    st.number_input("나이", min_value=19, max_value=100, key="age", placeholder="만 나이")
    st.date_input("창원 전입일", key="move_in_date", format="YYYY/MM/DD")
    st.selectbox(
        "사는 지역",
        [DISTRICT_PLACEHOLDER, *HOME_DISTRICTS],
        key="home_district",
        on_change=_sync_activity_district,
    )
    st.text_input(
        "동네 (선택)",
        placeholder="예: 상남동",
        max_chars=40,
        key="neighborhood",
    )
    st.number_input(
        "창원 전입 전 타지역 거주기간(년)",
        min_value=0,
        max_value=50,
        key="previous_residence_years",
        placeholder="예: 2",
    )
    st.radio(
        "창원 소재 사업장 재직 여부",
        EMPLOYMENT_OPTIONS,
        key="employment_status",
        horizontal=True,
    )
    st.radio(
        "차량 소지 여부",
        VEHICLE_OPTIONS,
        key="vehicle",
        horizontal=True,
        help="차가 없으면 대중교통 혜택(K-패스)을 먼저 보여 주고, 장소 안내도 대중교통 기준으로 알려 드려요.",
    )

    st.divider()
    st.markdown("**무엇을 확인할까요?**")
    with st.container(horizontal=True, wrap=True):
        for target_page, label, key in FEATURE_BUTTONS:
            st.button(
                label,
                key=key,
                type="primary",
                disabled=not user_key,
                on_click=_go,
                args=(target_page,),
            )
    if not user_key:
        st.info("닉네임을 입력하면 아래 기능을 쓸 수 있어요. 시연할 때는 ‘예시 정보로 채우기’를 눌러 주세요.")


move_in_date = st.session_state["move_in_date"]
home_district = (
    st.session_state["home_district"]
    if st.session_state["home_district"] in HOME_DISTRICTS
    else None
)
neighborhood = st.session_state["neighborhood"] or ""

all_missions = load_missions()
mission_groups = group_missions_by_month(all_missions)
current_month = current_settlement_month(move_in_date) if move_in_date else None
completion_states = {
    mission["ID"]: st.session_state.get(
        f"mission-progress:{user_key}:{mission['ID']}",
        saved_mission_states.get(mission["ID"], False),
    )
    for mission in all_missions
}
progress_summary = (
    calculate_mission_progress(all_missions, completion_states, current_month)
    if current_month
    else None
)
current_group = next(
    (group for group in mission_groups if group["month"] == current_month),
    None,
)


# --- 사이드바: 메뉴 + 진행률 -------------------------------------------------
with st.sidebar:
    st.subheader("메뉴")
    for target_page, label in PAGE_LABELS.items():
        if target_page == PAGE_JOURNEY:
            st.caption(FEATURE_2)
        st.button(
            label,
            key=f"nav-{target_page}",
            type="primary" if page == target_page else "secondary",
            disabled=target_page != PAGE_PROFILE and not user_key,
            on_click=_go,
            args=(target_page,),
            width="stretch",
        )
    st.divider()
    st.subheader("나의 창원 정착 현황")
    st.write(nickname.strip() or "닉네임을 입력해 주세요")
    if home_district:
        st.caption(
            f"{home_district} · {neighborhood.strip()}"
            if neighborhood.strip()
            else home_district
        )
    if st.session_state["vehicle"]:
        st.caption(VEHICLE_SUMMARY[st.session_state["vehicle"]])
    if progress_summary is None:
        st.caption("창원 전입일을 입력하면 정착 단계와 진행률을 보여 드려요.")
    else:
        st.write(f"지금은 창원 생활 {current_month}개월 차예요.")
        st.caption(current_group["theme"])
        st.write(
            f"현재 단계: {progress_summary['stage_completed']} / "
            f"{progress_summary['stage_total']} 완료"
        )
        st.progress(
            progress_summary["stage_completed"] / progress_summary["stage_total"]
            if progress_summary["stage_total"]
            else 0.0
        )
        st.write(
            f"전체 진행: {progress_summary['overall_completed']} / "
            f"{progress_summary['overall_total']} 완료"
        )
        st.progress(
            progress_summary["overall_completed"] / progress_summary["overall_total"]
            if progress_summary["overall_total"]
            else 0.0
        )
    last_saved_at = (
        st.session_state.get("last_saved_at")
        if st.session_state.get("last_saved_nickname") == user_key
        else None
    )
    if last_saved_at is None and saved_mission_timestamps:
        last_saved_at = max(
            saved_mission_timestamps.values(),
            key=lambda value: format_korea_timestamp(value) or "",
        )
    if last_saved_at:
        st.success("진행 상황을 저장했어요.")
        saved_month = (
            st.session_state.get("last_saved_month")
            if st.session_state.get("last_saved_nickname") == user_key
            else None
        )
        if saved_month:
            st.caption(f"저장한 단계: {MONTH_LABELS[saved_month]}")
        formatted_saved_at = format_korea_timestamp(last_saved_at)
        if formatted_saved_at:
            st.caption(f"마지막 저장: {formatted_saved_at} (한국시간)")
    st.divider()
    st.caption(CONTACT_TEXT)


# --- ② 받을 수 있는 지원 -----------------------------------------------------
def _current_profile():
    return {
        "nickname": nickname,
        "age": st.session_state["age"],
        "move_in_date": move_in_date,
        "home_district": home_district,
        "neighborhood": neighborhood.strip(),
        "previous_residence_years": st.session_state["previous_residence_years"],
        "employed_in_changwon": (
            None
            if st.session_state["employment_status"] is None
            else st.session_state["employment_status"] == EMPLOYMENT_OPTIONS[0]
        ),
        "vehicle": st.session_state["vehicle"],
    }


LEVEL_BOXES = {
    "해당 가능": st.success,
    "조건부 해당 가능": st.info,
    "직접 확인": st.warning,
    "해당 없음": st.error,
}
# 지역말·불편 접수 미션 → ③·④ 화면 바로가기
MISSION_FEATURE_PAGES = {
    "M1-5": "dialect", "M2-4": "dialect", "M4-4": "dialect", "M6-3": "dialect",
    "M5-4": "complaint",
}
POLICY_CARDS_SHOWN = 5
POLICY_NAMES = {p["ID"]: p["사업명"] for p in load_policies()}
# 정착 할 일 중 '지원'과 연결된 미션 → 관련 정책(지원 화면 카드)
MISSION_POLICY_IDS = {
    "M1-2": (),
    "M1-3": ("P21",),
    "M2-3": ("P06",),
    "M4-1": ("P20",),
    "M4-2": ("P19", "P11"),
    "M4-3": ("P09",),
    "M6-1": ("P01",),
    "M6-2": ("P03", "P04", "P05"),
}


def _policy_card(match):
    with st.container(border=True, key=f"policy-card-{match['id']}"):
        _content_title(match["name"])
        LEVEL_BOXES[match["level"]](f"[{match['level']}] {match['message']}")
        if match["support"]:
            _detail("지원 내용", match["support"])
        schedule = list(match["schedule"])
        if match["eligible_date"]:
            schedule.insert(0, f"계속 거주 6개월 기준일: {match['eligible_date']}")
        if schedule:
            _detail("신청 시점", "\n".join(schedule))
        if match["reasons"]:
            _detail("판단 이유", "\n".join(f"· {reason}" for reason in match["reasons"]))
        if match["how_to_apply"]:
            _detail("신청 방법", match["how_to_apply"])
        st.link_button("안내·신청 링크 열기", match["link"], key=f"policy-link-{match['id']}")
        st.caption(" · ".join(v for v in (f"{match['checked']} 확인" if match["checked"] else "", match["status"]) if v))


def render_policy_page():
    _back_home_button("policy")
    profile = _current_profile()
    matches = match_policies(profile)
    candidates = [m for m in matches if m["level"] != "해당 없음"]
    excluded = [m for m in matches if m["level"] == "해당 없음"]
    counts = {level: sum(1 for m in matches if m["level"] == level) for level in LEVELS}

    st.caption(f"{nickname}님을 위한 확인 결과")
    st.subheader(FEATURE_1)
    st.markdown("**받을 수 있는 혜택**")
    st.write(" · ".join(f"{level} {count}개" for level, count in counts.items()))
    st.caption(
        f"팀이 검증한 창원·청년 정책 {len(matches)}건과 입력한 정보를 비교했어요. "
        "받을 수 있다고 단정하지 않아요 — 최종 판단은 담당 기관에서 해요."
    )

    for match in candidates[:POLICY_CARDS_SHOWN]:
        _policy_card(match)
    if len(candidates) > POLICY_CARDS_SHOWN:
        with st.expander(f"더 보기 · 다른 지원 {len(candidates) - POLICY_CARDS_SHOWN}개"):
            for match in candidates[POLICY_CARDS_SHOWN:]:
                _policy_card(match)
    if excluded:
        with st.expander(f"해당 없음 {len(excluded)}개 · 이유 보기"):
            for match in excluded:
                _policy_card(match)

    st.link_button(
        "창원시 청년정책 전체 보기",
        CITY_YOUTH_POLICY_URL,
    )
    p01 = evaluate_p01(profile)
    if p01["missing_fields"]:
        missing_labels = [
            PROFILE_FIELD_LABELS.get(field, "추가 정보")
            for field in p01["missing_fields"]
        ]
        st.caption("확인할 항목: " + ", ".join(missing_labels))
    st.caption("조건을 바꾸려면 ‘← 처음으로’에서 내 정보를 고쳐 주세요.")
    _next_feature_button(PAGE_JOURNEY, f"{FEATURE_2} →")


# --- ③ 정착 할 일 ------------------------------------------------------------
def _feature_2_header(current):
    st.subheader(FEATURE_2)
    with st.container(horizontal=True, wrap=True):
        for target_page, label in FEATURE_2_TABS.items():
            st.button(
                label,
                key=f"tab-{target_page}",
                type="primary" if current == target_page else "secondary",
                on_click=_go,
                args=(target_page,),
            )


def render_journey_page():
    _back_home_button("journey")
    _feature_2_header(PAGE_JOURNEY)
    if move_in_date is None:
        st.subheader("창원 정착 일정")
        st.info("정착 일정과 할 일을 만들려면 ‘← 처음으로’에서 창원 전입일을 입력해 주세요.")
        return
    settlement_plan = build_settlement_plan(move_in_date)

    st.subheader("창원 정착 일정")

    for milestone in settlement_plan["milestones"]:
        label = MILESTONE_LABELS[milestone["day"]]
        st.markdown(f"**{label} · {milestone['date']}**")
    st.caption(
        "마지막 일정과 계속 거주 6개월 기준일은 서로 다른 방식으로 계산되어 "
        "날짜가 다를 수 있어요."
    )

    try:
        mission_resources = load_mission_resources()
    except (OSError, ValueError):
        mission_resources = {}
        st.info("할 일 관련 안내를 불러오지 못했어요. 할 일과 기록 저장은 계속 이용할 수 있어요.")

    st.subheader("이번에 할 일 · 1~6개월 정착 여정")
    st.caption("모든 단계는 제목을 눌러 언제든 열어볼 수 있어요. 체크와 내 기록은 ‘이 단계 저장하기’를 눌러 저장해 주세요.")

    for mission_group in mission_groups:
        group_title = (
            f"창원 생활 {MONTH_LABELS[mission_group['month']]} · "
            f"{mission_group['theme']} · {len(mission_group['missions'])}개"
        )
        if mission_group["month"] == current_month:
            group_title += " · 지금"
        with st.expander(
            group_title,
            expanded=mission_group["month"] == current_month,
        ):
            stage_missions = mission_group["missions"]
            if mission_group["month"] == current_month:
                current_completion_states = {
                    mission["ID"]: st.session_state.get(
                        f"mission-progress:{user_key}:{mission['ID']}",
                        saved_mission_states.get(mission["ID"], False),
                    )
                    for mission in all_missions
                }
                stage_progress = calculate_mission_progress(
                    all_missions,
                    current_completion_states,
                    current_month,
                )
                st.caption(
                    encouragement_message(
                        stage_progress["stage_completed"],
                        len(stage_missions),
                    )
                )

            for mission in mission_group["missions"]:
                mission_id = mission["ID"]
                widget_key = f"mission-progress:{user_key}:{mission_id}"
                note_key = f"mission-note:{user_key}:{mission_id}"
                if widget_key not in st.session_state:
                    st.session_state[widget_key] = saved_mission_states.get(
                        mission_id,
                        False,
                    )
                if note_key not in st.session_state:
                    st.session_state[note_key] = saved_mission_notes.get(
                        mission_id,
                        "",
                    )
                st.checkbox(
                    mission["미션"],
                    key=widget_key,
                )
                st.caption(f"완료 기준: {mission['완료 기준']}")
                resource = mission_resources.get(mission_id)
                feature_page = MISSION_FEATURE_PAGES.get(mission_id)
                if feature_page:
                    st.button(
                        f"{PAGE_LABELS[feature_page]} 열기",
                        key=f"to-feature-{mission_id}",
                        on_click=_go,
                        args=(feature_page,),
                    )
                if mission_id in MISSION_POLICY_IDS:
                    # 할 일은 '무엇을 할까'만 — 지원 내용·대상 여부는 지원 화면 카드로 연결
                    related = [POLICY_NAMES[pid] for pid in MISSION_POLICY_IDS[mission_id] if pid in POLICY_NAMES]
                    st.caption(
                        f"지원 내용·대상 여부는 ‘{FEATURE_1}’에서 확인해요"
                        + (f" ({', '.join(related)})" if related else "")
                    )
                    with st.container(horizontal=True, wrap=True):
                        st.button(
                            "혜택 카드 보기",
                            key=f"to-policy-{mission_id}",
                            on_click=_go,
                            args=(PAGE_POLICY,),
                        )
                        for link in (resource or {}).get("official_links", []):
                            st.link_button(f"신청·안내 링크 · {link['label']}", link["url"])
                elif resource:
                    st.text(resource["summary"])
                    _detail("신청기간·이용 일정", resource["application_period"])
                    for link in resource["official_links"]:
                        st.link_button(
                            f"{resource['title']} · {link['label']}",
                            link["url"],
                        )
                st.text_input(
                    "내 기록 (선택)",
                    key=note_key,
                    max_chars=300,
                )

            save_key = f"save-stage:{user_key}:{mission_group['month']}"
            if st.button(
                "이 단계 저장하기",
                key=save_key,
                disabled=not user_key,
            ):
                stage_progress_to_save = {
                    mission["ID"]: {
                        "completed": st.session_state[
                            f"mission-progress:{user_key}:{mission['ID']}"
                        ],
                        "note": st.session_state[
                            f"mission-note:{user_key}:{mission['ID']}"
                        ],
                    }
                    for mission in stage_missions
                }
                st.session_state["last_saved_at"] = save_mission_group(
                    user_key,
                    stage_progress_to_save,
                )
                st.session_state["last_saved_nickname"] = user_key
                st.session_state["last_saved_month"] = mission_group["month"]
                st.rerun()

            stage_timestamps = [
                formatted
                for mission in stage_missions
                if (
                    formatted := format_korea_timestamp(
                        saved_mission_timestamps.get(mission["ID"])
                    )
                )
            ]
            if stage_timestamps:
                st.caption(f"마지막 저장: {max(stage_timestamps)} (한국시간)")
    _next_feature_button(PAGE_EXPLORE, f"{FEATURE_2_TABS[PAGE_EXPLORE]} →")


# --- ④ 창원 둘러보기 ----------------------------------------------------------
def render_explore_page():
    _back_home_button("explore")
    _feature_2_header(PAGE_EXPLORE)
    st.subheader("창원에서 해볼 것")
    st.write("동네와 관심 분야를 골라 가볼 곳과 참여할 일을 찾아보세요.")

    try:
        activities = load_activities()
        activity_options = get_activity_filter_options(activities)
        district_options = ["창원 전체", *activity_options["districts"]]
        default_activity_district = (
            home_district
            if home_district in district_options
            else "창원 전체"
        )
        st.session_state.setdefault("activity_district", default_activity_district)
        if st.session_state["activity_district"] not in district_options:
            st.session_state["activity_district"] = "창원 전체"
        selected_district = st.selectbox(
            "어느 지역에서 찾을까요?",
            district_options,
            key="activity_district",
        )
        selected_category = st.selectbox(
            "어떤 활동을 찾으세요?",
            ["모든 분야", *activity_options["categories"]],
            key="activity_category",
        )
        filtered_activities = filter_activities(
            activities,
            district=(
                None if selected_district == "창원 전체" else selected_district
            ),
            category=(
                None if selected_category == "모든 분야" else selected_category
            ),
        )

        st.caption(f"둘러볼 수 있는 활동 {len(filtered_activities)}개")
        if not filtered_activities:
            st.info("조건에 맞는 활동을 찾지 못했어요. 다른 지역이나 분야를 골라보세요.")

        if filtered_activities:
            activity_by_id = {activity["ID"]: activity for activity in filtered_activities}
            if st.session_state.get("activity_selection") not in activity_by_id:
                st.session_state.pop("activity_selection", None)
            selected_activity_id = st.selectbox(
                "어떤 곳을 볼까요?",
                list(activity_by_id),
                format_func=lambda activity_id: (
                    f"{activity_by_id[activity_id]['이름']} · "
                    f"{activity_by_id[activity_id]['생활권(구)']}"
                ),
                key="activity_selection",
            )
            app_name = st.context.url or "http://localhost:8501"
            item = activity_view(activity_by_id[selected_activity_id], app_name)

            _content_title(item["name"])
            introduction = item.get("introduction")
            if isinstance(introduction, str) and introduction.strip():
                st.text(introduction)
            st.caption(f"{item['district']} · {item['category']}")
            st.caption(f"관심 분야: {item['interests']}")
            _detail("운영시간", _schedule_lines(item["schedule"]))
            if item["start_date"] or item["end_date"]:
                period = " ~ ".join(
                    value
                    for value in (item["start_date"], item["end_date"])
                    if value
                )
                _detail("기간", period)
            _detail("참여 방법", item["participation"])
            _detail("대상", item["audience"])
            st.caption(f"{item['last_checked']} 기준으로 확인했어요.")
            st.caption("방문 전 운영시간을 한 번 더 확인해 주세요.")

            st.subheader("장소 안내")
            if item["official_url"]:
                st.link_button(
                    item["official_link_label"],
                    item["official_url"],
                )

            st.subheader("이동")
            no_car = st.session_state["vehicle"] == "없음"
            if no_car:
                st.info("차가 없으니 대중교통 경로로 안내해요. 시내버스를 자주 탄다면 K-패스로 교통비 일부를 돌려받을 수 있어요.")
            st.link_button(
                "네이버 지도에서 보기",
                naver_map_web_url(activity_by_id[selected_activity_id]),
                type="primary" if no_car else "secondary",
            )
            if no_car:
                st.button(
                    "K-패스 혜택 카드 보기",
                    key="explore-kpass",
                    on_click=_go,
                    args=(PAGE_POLICY,),
                )
            st.text(
                "검색 결과에서 장소와 지역을 확인해 주세요. "
                "장소를 확인한 뒤 출발지를 현재 위치로 정하고 "
                "대중교통 길찾기를 선택해 주세요."
            )
    except (OSError, ValueError):
        st.info(
            "창원 활동 정보를 불러오지 못했어요. "
            "지원 확인과 정착 할 일은 계속 이용할 수 있어요."
        )
    _next_feature_button(PAGE_COMPLAINT, f"{FEATURE_3} →")


# --- ⑤ AI에게 물어보기 ---------------------------------------------------------
ASK_EXAMPLES = (
    "내가 받을 수 있는 지원 알려줘",
    "이번 주말 버스로 갈 만한 야경 명소 추천해 줘",
    "‘욕봤데이’가 무슨 뜻이에요?",
    "집 앞 가로등이 며칠째 꺼져 있어요",
)
MODE_LABELS = {
    "llm": "AI 답변",
    "rule": "기본 안내(AI 미연결·대체)",
    "emergency": "안전 안내(긴급)",
    "crisis": "안전 안내(위기)",
}


def _setting(name):
    try:
        value = st.secrets.get(name)
    except Exception:  # secrets 파일이 없으면 환경변수만 본다
        value = None
    return value or os.environ.get(name)


def llm_settings():
    provider = (_setting("LLM_PROVIDER") or "").strip().lower() or None
    if provider is None:
        if _setting("ANTHROPIC_API_KEY"):
            provider = "anthropic"
        elif _setting("OPENAI_API_KEY"):
            provider = "openai"
    key_name = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}.get(provider)
    api_key = _setting(key_name) if key_name else None
    if not api_key:
        return None, None, None
    return provider, api_key, _setting("LLM_MODEL") or DEFAULT_MODELS[provider]


@st.cache_resource(show_spinner=False)
def _llm_client(provider, api_key):
    return make_client(provider, api_key)


def _queue_question(text):
    st.session_state["ask_pending"] = text


def _ask_agent(question):
    provider, api_key, model = llm_settings()
    client = _llm_client(provider, api_key) if provider else None
    with st.spinner("필요한 자료를 찾아보고 있어요…"):
        result = run_agent(question, _current_profile(), provider=provider, client=client, model=model)
    return {
        "question": question,
        "answer": result.answer,
        "mode": result.mode,
        "model": MODEL_LABELS.get(result.model, result.model),
        "verified": result.verified,
        "steps": result.steps,
        "links": result.links,
    }


def _render_agent_item(item, key_prefix):
    with st.chat_message("user"):
        st.text(item["question"])
    with st.chat_message("assistant"):
        st.text(item["answer"])
        badge = MODE_LABELS[item["mode"]]
        if item["mode"] == "llm":
            badge += f" · {item['model']}"
        badge += " · 검증 통과" if item["verified"] else " · 검증 필요"
        st.caption(badge)
        for link_index, (label, url) in enumerate(item.get("links", [])):
            st.link_button(label, url, key=f"{key_prefix}-link-{link_index}")
        with st.expander("Agent 실행 기록 보기"):
            for number, step in enumerate(item["steps"], start=1):
                st.text(f"{number}. [{step['단계']}] {step['내용']}")


def _ai_status_caption():
    provider, _, model = llm_settings()
    if provider:
        st.caption(f"AI 연결됨: {MODEL_LABELS.get(model, model)} · 팀이 검증한 자료로만 답해요.")
    else:
        st.caption("AI 모델이 연결되지 않아 기본 안내(키워드 규칙)로 답해요.")


def render_ask_page():
    _back_home_button("ask")
    st.subheader(ASK_LABEL)
    provider, api_key, model = llm_settings()
    if provider:
        st.caption(f"AI 연결됨: {MODEL_LABELS.get(model, model)} · 팀이 검증한 자료(정책·장소·지역말·접수 창구)로만 답해요.")
    else:
        st.caption("AI 모델이 연결되지 않아 기본 안내(키워드 규칙)로 답해요.")
    st.caption("실명·연락처 같은 개인정보는 입력하지 마세요. 질문은 답변을 만들기 위해 AI 모델로 전송돼요.")

    st.markdown("**이렇게 물어보세요**")
    with st.container(horizontal=True, wrap=True):
        for index, example in enumerate(ASK_EXAMPLES):
            st.button(example, key=f"ask-example-{index}", on_click=_queue_question, args=(example,))

    history = st.session_state.setdefault("ask_history", [])
    question = st.chat_input("창원 정착에 관해 한 문장으로 물어보세요", key="ask_input")
    question = question or st.session_state.pop("ask_pending", None)
    if question:
        history.append(_ask_agent(question))

    for index, item in enumerate(history):
        _render_agent_item(item, f"ask-{index}")
    if history:
        st.button("대화 지우기", key="ask-clear", on_click=lambda: st.session_state.update(ask_history=[]))


# --- ③ 불편사항 행정 접수안내 ---------------------------------------------------
COMPLAINT_EXAMPLES = (
    "집 앞 가로등이 며칠째 꺼져 있어요",
    "출퇴근 버스 배차 간격이 너무 길어요",
    "창원 청년 정책 아이디어를 제안하고 싶어요",
    "요즘 너무 외롭고 우울해요",
)
COMPLAINT_BOXES = {"긴급": st.error, "위기": st.error, "높음": st.warning, "보통": st.info, "제안": st.success, "마음 건강": st.info}


def _queue_complaint(text):
    st.session_state["complaint_pending"] = text


def render_complaint_page():
    _back_home_button("complaint")
    st.subheader(FEATURE_3)
    st.write("불편한 상황을 한 문장으로 적으면 AI가 긴급도를 판단하고 알맞은 접수 창구를 안내해요.")
    _ai_status_caption()
    st.caption("민원을 대신 접수하거나 개인정보를 받지 않아요. 화재·사고 같은 긴급 상황은 바로 112·119에 신고하세요.")
    with st.container(horizontal=True, wrap=True):
        for index, example in enumerate(COMPLAINT_EXAMPLES):
            st.button(example, key=f"complaint-example-{index}", on_click=_queue_complaint, args=(example,))
    with st.form("complaint-form", clear_on_submit=True, border=False):
        text = st.text_input("어떤 불편이 있나요?", placeholder="예: 우리 동네 인도 블록이 깨져서 위험해요", max_chars=200)
        submitted = st.form_submit_button("접수 창구 찾기", type="primary")
    question = (text if submitted and text.strip() else None) or st.session_state.pop("complaint_pending", None)
    if question:
        st.session_state["complaint_result"] = _ask_agent(f"[불편사항 접수 안내] {question}")
        st.session_state["complaint_result"]["question"] = question
    if st.session_state.get("complaint_result"):
        _render_agent_item(st.session_state["complaint_result"], "complaint")

    with st.expander("단계별 접수 창구 한눈에 보기"):
        for item in load_complaint_channels():
            COMPLAINT_BOXES.get(item["단계"], st.info)(f"[{item['단계']}] {item['예시']}")
            st.text(item["안내"] + "\n연락처: " + ", ".join(item["연락처"]))
        st.caption("단계 구분은 서비스 기획 기준이며, 연락처는 창원시 누리집과 2026-09-29 창원시청 통화로 팀이 확인했어요.")
    _next_feature_button(PAGE_DIALECT, f"{FEATURE_4} →")


# --- ④ 창원 지역말 번역 --------------------------------------------------------
def _queue_dialect(text):
    st.session_state["dialect_pending"] = text


def render_dialect_page():
    _back_home_button("dialect")
    st.subheader(FEATURE_4)
    st.write("직장·식당·병원에서 들은 창원(경남) 말을 적으면 뜻과 쓰임을 알려 드려요.")
    _ai_status_caption()
    st.caption("뜻은 ‘문헌 기준 뜻’이에요(토박이 검수 생략). 사전에 없는 말은 ‘AI 추정 - 사람 검수 필요’로 표시해요.")
    dialects = load_dialects()
    demo = [d for d in dialects if d.get("시연 사용")][:6]
    with st.container(horizontal=True, wrap=True):
        for index, item in enumerate(demo):
            st.button(item["표현"], key=f"dialect-example-{index}", on_click=_queue_dialect, args=(item["표현"],))
    with st.form("dialect-form", clear_on_submit=True, border=False):
        text = st.text_input("들은 말", placeholder="예: 단디 해래이", max_chars=60)
        submitted = st.form_submit_button("뜻 찾기", type="primary")
    expression = (text if submitted and text.strip() else None) or st.session_state.pop("dialect_pending", None)
    if expression:
        result = _ask_agent(f"창원 지역말 ‘{expression.strip()}’이(가) 무슨 뜻이에요?")
        result["question"] = expression.strip()
        st.session_state["dialect_result"] = result
    if st.session_state.get("dialect_result"):
        _render_agent_item(st.session_state["dialect_result"], "dialect")

    with st.expander(f"핵심 지역말 {len(dialects)}개 한눈에 보기"):
        for item in dialects:
            st.markdown(f"**{item['표현']}**")
            st.text(f"{item['표준어 뜻']} · {item.get('사용 상황') or ''}")
        st.caption("출처: 우리말샘·국립국어원 온라인가나다 등(문헌 기준 뜻)")
    _next_feature_button(PAGE_ASK, f"{ASK_LABEL} →")


PAGE_RENDERERS = {
    PAGE_COMPLAINT: render_complaint_page,
    PAGE_DIALECT: render_dialect_page,
    PAGE_ASK: render_ask_page,
    PAGE_PROFILE: render_profile_page,
    PAGE_POLICY: render_policy_page,
    PAGE_JOURNEY: render_journey_page,
    PAGE_EXPLORE: render_explore_page,
}
PAGE_RENDERERS.get(page, render_profile_page)()

st.divider()
st.caption(CONTACT_TEXT)


def _scroll_to_top_on_page_change():
    # 아래쪽 버튼으로 화면을 바꾸면 스크롤이 그대로 남으므로, 화면이 바뀐 경우에만 맨 위로 올린다.
    if st.session_state.get("rendered_page") == page:
        return
    st.session_state["rendered_page"] = page
    st.session_state["page_change_count"] = st.session_state.get("page_change_count", 0) + 1
    components.html(
        "<script>"
        f"/* {st.session_state['page_change_count']} */"
        "const main = window.parent.document.querySelector('[data-testid=\"stMain\"]');"
        "if (main) { main.scrollTo({top: 0}); }"
        "window.parent.scrollTo({top: 0});"
        "</script>",
        height=0,
    )


_scroll_to_top_on_page_change()
