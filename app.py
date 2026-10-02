import streamlit as st
from datetime import date
from pathlib import Path
import re

from activity_manager import (
    activity_view,
    filter_activities,
    get_activity_filter_options,
    load_activities,
)
from naver_map_links import naver_map_web_url
from policy_engine import evaluate_p01
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
SLOGAN = "창원에서 너의 내일을 응원해!"
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


st.set_page_config(
    page_title="오이소창원",
    page_icon=str(LOGO_ICON_PATH),
    layout="centered",
)

st.html(READABILITY_CSS)

st.image(str(LOGO_WIDE_PATH), width=360)
st.subheader(SLOGAN, anchor=False)

st.write(
    "창원에 새로 전입한 청년의 초기 정착을 돕는 코디네이터 Agent입니다."
)

st.divider()

nickname = st.text_input("닉네임", value=DEFAULT_NICKNAME)
user_key = nickname.strip()
saved_mission_states = load_mission_states(user_key) if user_key else {}
saved_mission_notes = load_mission_notes(user_key) if user_key else {}
saved_mission_timestamps = load_mission_timestamps(user_key) if user_key else {}

age = st.number_input(
    "나이",
    min_value=19,
    max_value=100,
    value=28,
)

move_in_date = st.date_input(
    "창원 전입일",
    value=date(2026, 9, 20),
)

home_district = st.selectbox(
    "사는 지역",
    ["지역을 선택해 주세요", *HOME_DISTRICTS],
    key="home_district",
    on_change=_sync_activity_district,
)
home_district = home_district if home_district in HOME_DISTRICTS else None
neighborhood = st.text_input(
    "동네 (선택)",
    placeholder="예: 상남동",
    max_chars=40,
    key="neighborhood",
)

previous_residence_years = st.number_input(
    "창원 전입 전 타지역 거주기간(년)",
    min_value=0,
    max_value=50,
    value=2,
)

employed_in_changwon = st.checkbox(
    "현재 창원 소재 사업장에 재직 중입니다.",
    value=True,
)

all_missions = load_missions()
mission_groups = group_missions_by_month(all_missions)
current_month = current_settlement_month(move_in_date)
completion_states = {
    mission["ID"]: st.session_state.get(
        f"mission-progress:{user_key}:{mission['ID']}",
        saved_mission_states.get(mission["ID"], False),
    )
    for mission in all_missions
}
progress_summary = calculate_mission_progress(
    all_missions,
    completion_states,
    current_month,
)
current_group = next(
    group for group in mission_groups if group["month"] == current_month
)

with st.sidebar:
    st.subheader("나의 창원 정착 현황")
    st.write(nickname.strip() or "닉네임을 입력해 주세요")
    if home_district:
        st.caption(
            f"{home_district} · {neighborhood.strip()}"
            if neighborhood.strip()
            else home_district
        )
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

st.session_state.setdefault("show_policy_results", False)
st.session_state.setdefault("show_journey", False)
with st.container(horizontal=True, wrap=True):
    if st.button(
        "받을 수 있는 지원 확인하기",
        key="show-policy",
        type="primary",
        disabled=not user_key,
    ):
        st.session_state["show_policy_results"] = True
    if st.button(
        "나의 정착 할 일 확인하기",
        key="show-journey",
        type="primary",
        disabled=not user_key,
    ):
        st.session_state["show_journey"] = True

if not user_key:
    st.info("할 일 진행 상황을 이어 보려면 닉네임을 입력해 주세요.")

if user_key and st.session_state["show_policy_results"]:

    profile = {
        "nickname": nickname,
        "age": age,
        "move_in_date": move_in_date,
        "home_district": home_district,
        "neighborhood": neighborhood.strip(),
        "previous_residence_years": previous_residence_years,
        "employed_in_changwon": employed_in_changwon,
    }

    result = evaluate_p01(profile)

    st.divider()
    st.caption(f"{nickname}님을 위한 확인 결과")
    st.subheader("받을 수 있는 지원")
    _content_title(result["policy_name"])

    status = result["status"]

    if status == "eligible_now":
        st.success("현재 신청할 수 있어요.")

    elif status == "eligible_later":
        st.info("조금 뒤 신청할 수 있어요.")

    elif status == "needs_info":
        st.warning("정보를 조금 더 입력해 주세요.")

    elif status == "not_eligible":
        st.error("현재 조건으로는 신청 대상이 아니에요.")

    if result["eligible_date"]:
        _detail("신청 시점", f"계속 거주 6개월 기준일: {result['eligible_date']}")
    _detail("핵심 조건", result["reason"])

    st.link_button(
        "창원시 청년정책 전체 보기",
        CITY_YOUTH_POLICY_URL,
    )

    if result["missing_fields"]:
        missing_labels = [
            PROFILE_FIELD_LABELS.get(field, "추가 정보")
            for field in result["missing_fields"]
        ]
        st.caption(
            "확인할 항목: "
            + ", ".join(missing_labels)
        )

if user_key and st.session_state["show_journey"]:

    settlement_plan = build_settlement_plan(move_in_date)

    st.divider()
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
                if resource:
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

    st.divider()
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
            st.link_button(
                "네이버 지도에서 보기",
                naver_map_web_url(activity_by_id[selected_activity_id]),
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