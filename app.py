import streamlit as st
from datetime import date

from activity_manager import (
    activity_view,
    filter_activities,
    get_activity_filter_options,
    load_activities,
)
from policy_engine import evaluate_p01
from mission_manager import group_missions_by_month, load_missions
from settlement_engine import build_settlement_plan
from state_manager import load_mission_states, save_mission_state


MILESTONE_LABELS = {
    0: "전입한 날",
    7: "첫 주",
    30: "한 달쯤 뒤",
    90: "정착 중반",
    180: "여섯 달쯤 뒤",
}
MONTH_LABELS = {
    1: "처음 한 달",
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


def _save_mission_checkbox(nickname, mission_id, widget_key):
    save_mission_state(
        nickname,
        mission_id,
        st.session_state[widget_key],
    )


st.set_page_config(
    page_title="오이소창원",
    page_icon="🌱",
    layout="centered",
)

st.title("🌱 오이소창원")
st.subheader("창원 생활, 하나씩 준비해요")

st.write(
    "내 상황에 맞는 지원과 이사 후 챙길 일을 확인할 수 있어요."
)

st.divider()

nickname = st.text_input("닉네임", value="코디세이")
user_key = nickname.strip()
saved_mission_states = load_mission_states(user_key) if user_key else {}
if saved_mission_states:
    st.session_state["show_policy_results"] = True

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

show_policy_results = st.button(
    "지원과 할 일 확인하기",
    type="primary",
    disabled=not user_key,
)
if show_policy_results:
    st.session_state["show_policy_results"] = True

if not user_key:
    st.info("할 일 진행 상황을 이어 보려면 닉네임을 입력해 주세요.")

if user_key and st.session_state.get("show_policy_results", False):

    profile = {
        "nickname": nickname,
        "age": age,
        "move_in_date": move_in_date,
        "previous_residence_years": previous_residence_years,
        "employed_in_changwon": employed_in_changwon,
    }

    result = evaluate_p01(profile)

    st.divider()
    st.subheader(f"{nickname}님을 위한 확인 결과")
    st.subheader("받을 수 있는 지원")
    st.markdown(f"**{result['policy_name']}**")

    status = result["status"]

    if status == "eligible_now":
        st.success("현재 신청할 수 있어요.")

    elif status == "eligible_later":
        st.info("조금 뒤 신청할 수 있어요.")

    elif status == "needs_info":
        st.warning("정보를 조금 더 입력해 주세요.")

    elif status == "not_eligible":
        st.error("현재 조건으로는 신청 대상이 아니에요.")

    st.write(f"**확인 내용:** {result['reason']}")

    if result["eligible_date"]:
        st.write(
            f"**계속 거주 6개월 기준일:** "
            f"{result['eligible_date']}"
        )

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

    st.subheader("이번에 할 일")
    st.caption("체크한 내용은 닉네임과 함께 저장돼 다시 열어도 확인할 수 있어요.")

    mission_groups = group_missions_by_month(load_missions())
    for mission_group in mission_groups:
        group_title = (
            f"{MONTH_LABELS[mission_group['month']]} · "
            f"{mission_group['theme']} · {len(mission_group['missions'])}개"
        )
        with st.expander(
            group_title,
            expanded=mission_group["month"] == 1,
        ):
            for mission in mission_group["missions"]:
                mission_id = mission["ID"]
                widget_key = f"mission-progress:{user_key}:{mission_id}"
                if widget_key not in st.session_state:
                    st.session_state[widget_key] = saved_mission_states.get(
                        mission_id,
                        False,
                    )
                st.checkbox(
                    mission["미션"],
                    key=widget_key,
                    on_change=_save_mission_checkbox,
                    args=(user_key, mission_id, widget_key),
                )
                st.caption(f"완료 기준: {mission['완료 기준']}")

    st.divider()
    st.subheader("창원에서 해볼 것")
    st.write("동네와 관심 분야를 골라 가볼 곳과 참여할 일을 찾아보세요.")

    try:
        activities = load_activities()
        activity_options = get_activity_filter_options(activities)
        selected_district = st.selectbox(
            "어느 지역에서 찾을까요?",
            ["창원 전체", *activity_options["districts"]],
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

            st.text(item["name"])
            st.text(f"{item['district']} · {item['category']}")
            st.text(f"관심 분야: {item['interests']}")
            st.text(f"운영시간: {item['schedule']}")
            if item["start_date"] or item["end_date"]:
                period = " ~ ".join(
                    value
                    for value in (item["start_date"], item["end_date"])
                    if value
                )
                st.text(f"기간: {period}")
            st.text(f"참여 방법: {item['participation']}")
            st.text(f"대상: {item['audience']}")
            st.text(f"{item['last_checked']} 기준으로 확인했어요.")
            st.text("방문 전 운영시간을 한 번 더 확인해 주세요.")

            st.subheader("장소 안내")
            if item["official_url"]:
                st.link_button(
                    item["official_link_label"],
                    item["official_url"],
                )

            st.subheader("이동")
            st.link_button("네이버 지도에서 보기", item["naver_map_url"])
            st.link_button(
                "네이버 지도 앱에서 장소 찾기",
                item["naver_map_search_app_url"],
            )
            st.text(
                "장소를 확인한 뒤 출발지를 현재 위치로 정하고 "
                "대중교통 길찾기를 선택해 주세요."
            )
    except (OSError, ValueError):
        st.info(
            "창원 활동 정보를 불러오지 못했어요. "
            "지원 확인과 정착 할 일은 계속 이용할 수 있어요."
        )