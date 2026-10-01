import streamlit as st
from datetime import date

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