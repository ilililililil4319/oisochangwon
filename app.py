import html
import json
import streamlit as st
import streamlit.components.v1 as components
from datetime import date, datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import os
import re
import sys

# 개발 파일(모듈)은 src/ 폴더에 있다. 배포 시작 파일 app.py는 저장소 맨 위에 둔다.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

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
from mission_manager import group_missions_by_month, load_missions, personalize_missions
from policy_resource_manager import load_mission_resources
from progress_manager import (
    calculate_mission_progress,
    current_settlement_month,
    encouragement_message,
)
from settlement_engine import build_settlement_plan
from schedule_export import build_ics, build_report_html, build_schedule_events
import email_alerts
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
    30: "정착 1~2개월",
    90: "정착 3-5개월",
    180: "정착 6개월 이후",
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
# 첫 화면 위쪽 왼쪽 끝 작은 로고(남색 배경용 흰 글자 버전, 원본 로고 색만 바꿈) (10/4 이혜경: 로고 줄여서 한쪽 끝으로)
LOGO_LIGHT_PATH = ASSETS_DIR / "logo_wide_light.png"
LOGO_WIDTH = 168
SLOGAN = "창원에서 너의 내일을 응원해!"
POLICY_COUNT = len(load_policies())
def _safe_count(loader):
    # 데이터 파일을 읽지 못해도 홈 화면은 떠야 하므로, 실패하면 숫자만 빼고 안내한다.
    try:
        return len(loader())
    except Exception:
        return None


MISSION_COUNT = _safe_count(load_missions)
ACTIVITY_COUNT = _safe_count(load_activities)
CHANNEL_COUNT = _safe_count(load_complaint_channels)
DIALECT_COUNT = _safe_count(
    lambda: {item["표현"].replace(" ", "") for item in _agent_items("dialects_core30.json") + _agent_items("dialects_ext.json")}
)
# 회원가입 없이 저장되는 방식 안내(홈·정착 일정 화면)
POLICY_SAVE_HELP = (
    "회원가입이 없어 다시 접속하면 내용이 사라질 수 있어요. "
    "📅 캘린더(해당 가능·조건부 혜택 확인일 포함)나 📄 정착 리포트로 내 기기에 저장해 두세요. "
    "✉️ 이메일 알림은 선택이고, 신청할 때만 개인정보 수집·이용과 수신 동의를 받아요."
)
SAVE_HELP = (
    "회원가입을 하지 않기 때문에 다시 접속하면 이전 내용이 사라질 수 있어요. "
    "오래 보관하려면 ‘📅 캘린더에 저장’이나 ‘📄 정착 리포트 저장’으로 내 기기에 저장해 두는 게 가장 확실해요. "
    "이메일 일정 알림은 선택 사항이고, 원할 때만 개인정보 수집·이용 동의와 이메일 수신 동의를 받은 뒤 보내 드려요."
)
DEFAULT_NICKNAME = "코디2026"


# 문장이 여러 개인 안내는 문장마다 줄을 바꿔 읽기 쉽게 (10/3 실사용자 피드백: 글자 끊김)
_SENTENCE_BREAK = re.compile(r"(?<=[요다]\.) (?=\S)|(?<=[요까]\?) (?=\S)")


def _lines(text):
    return _SENTENCE_BREAK.sub("  \n", text) if isinstance(text, str) else text


def _caption(body, *args, **kwargs):
    return st.caption(_lines(body), *args, **kwargs)


# Native heading and caption roles share one small typography layer.
READABILITY_CSS = """
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css');
/* 한글 줄바꿈: 낱말 중간에서 끊지 않고 띄어쓰기에서 바꿈, 긴 URL만 필요할 때 끊음 */
.stApp p, .stApp li, .stApp label, .stApp span, .stApp td, .stApp th, .stApp button, .stApp h1, .stApp h2, .stApp h3,
.stApp [data-testid="stCaptionContainer"], .stApp .flow-box {word-break: keep-all; overflow-wrap: break-word;}
[data-testid="stMainBlockContainer"] {max-width: 100%; padding: 3.2rem 2.5rem 2rem 2.5rem;}
/* 내용은 가운데 최대 1200px, 배경 띠만 화면 끝까지 */
[class*="st-key-page-"]:not(.st-key-page-home), .st-key-home-hero-inner, .st-key-home-body {max-width: 1200px; margin-left: auto !important; margin-right: auto !important; width: 100%;}
.st-key-home-hero-band {margin-left: -2.5rem !important; width: calc(100% + 5rem) !important; max-width: none !important;
    background: #EEF4FB; border-bottom: 1px solid #D5DDE7; padding: 1.4rem 2.5rem 1.6rem; box-sizing: border-box; margin-top: -1rem;}
.st-key-home-hero-band .st-key-slogan h3 {font-size: 1.55rem !important;}
.st-key-home-hero-band [data-testid="stMarkdownContainer"] p {font-size: 1.12rem;}
.st-key-hero-cta [data-testid="stBaseButton-primary"] {background-color: #FE6A01 !important; border-color: #FE6A01 !important; min-height: 3.1rem; padding: 0 1.6rem;}
.st-key-hero-cta [data-testid="stBaseButton-primary"] p {font-size: 1.08rem; font-weight: 700;}
.st-key-hero-example, .st-key-hero-progress {background: #FFFFFF; border: 1px solid #D5DDE7; border-left: 5px solid #2E9E6B; border-radius: 14px; padding: 1rem 1.3rem;}
[class*="st-key-home-card-"] {background: #FFFFFF; border: 1px solid #D5DDE7; border-top: 4px solid #063465; border-radius: 14px; padding: 1rem 1.1rem; min-height: 14rem; justify-content: space-between;}
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:disabled {background: #F5F8FC !important; border: 1px dashed #9FB0C6 !important; opacity: 1;}
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:disabled p {color: #5A6E88 !important;}
@media (max-width: 640px) {[class*="st-key-home-card-"] {min-height: 0;}}
[class*="st-key-home-card-"] [data-testid="stBaseButton-secondary"]:disabled {background: #F5F8FC !important; border: 1px dashed #9FB0C6 !important; color: #3F5672 !important; opacity: 1;}
[class*="st-key-home-card-"] [data-testid="stBaseButton-secondary"]:disabled p {color: #3F5672 !important;}
[class*="st-key-level-count-"] {border-radius: 12px; padding: .6rem .9rem; border: 1px solid #D5DDE7; background: #FFFFFF; border-top-width: 4px; gap: .1rem;}
[class*="st-key-level-count-"] .lvl-name {font-weight: 700; font-size: .95rem;}
[class*="st-key-level-count-"] .lvl-num {font-size: 2rem; font-weight: 800; color: #063465; line-height: 1.3;}
[class*="st-key-level-count-"] .lvl-hint {font-size: .8rem; color: #5A6E88; padding-bottom: .5rem;}
@media (max-width: 640px) {
    .st-key-level-counts [data-testid="stHorizontalBlock"] {flex-flow: row wrap !important; gap: .5rem !important;}
    .st-key-level-counts [data-testid="stColumn"] {width: calc(50% - .25rem) !important; flex: 1 1 calc(50% - .25rem) !important; min-width: calc(50% - .25rem) !important;}
    [class*="st-key-level-count-"] .lvl-num {font-size: 1.6rem;}
}
[class*="st-key-policy-card-"] .pc-label {font-weight: 700; margin-top: .3rem;}
[class*="st-key-policy-card-"] .pc-body {margin-bottom: .5rem;}
.st-key-level-count-level-ok {border-top-color: #2E9E6B;}
.st-key-level-count-level-cond {border-top-color: #063465;}
.st-key-level-count-level-check {border-top-color: #FE6A01;}
.st-key-level-count-level-no {border-top-color: #9FB0C6;}
[class*="st-key-policy-card-"] {border-radius: 14px !important;}
[class*="st-key-policy-card-"] [data-testid="stHeadingWithActionElements"] h2 {font-size: 1.35rem !important; padding: .2rem 0 0 0 !important;}
.st-key-journey-summary {background: #EEF4FB; border: 1px solid #C9D8EA; border-left: 5px solid #2E9E6B; border-radius: 14px; padding: .9rem 1.3rem;}
.st-key-journey-summary h3 {font-size: 1.35rem !important; color: #063465; padding: 0 !important;}
.st-key-journey-tools {border: 1px solid #D5DDE7; border-radius: 14px; padding: 1rem 1.3rem; background: #FFFFFF;}
.st-key-email-alert {max-width: 760px; border-top: 1px dashed #D5DDE7; padding-top: .7rem;}
[class*="st-key-save-row-"] {gap: .6rem; align-items: center !important;}
.st-key-complaint-input, .st-key-dialect-input {background: #F7F9FC; border: 1px solid #D5DDE7; border-radius: 14px; padding: 1rem 1.2rem;}
.st-key-complaint-result, .st-key-dialect-result {border: 1px solid #D5DDE7; border-left: 5px solid #FE6A01; border-radius: 14px; padding: .8rem 1rem; background: #FFFFFF;}
[class*="st-key-save-row-"] [data-testid="stElementContainer"] {margin: 0 !important;}
.st-key-email-alert {scroll-margin-top: 90px;}
[class*="st-key-milestone-"] {border-radius: 12px; padding: .5rem .8rem; border: 1px solid #D5DDE7; background: #FFFFFF; gap: .1rem;}
[class*="st-key-milestone-"][class*="-done"] {background: #F3F8F5; border-color: #D6E9DE;}
[class*="st-key-milestone-"][class*="-next"] {border: 2px solid #FE6A01;}
[class*="st-key-activity-card-"] {border-radius: 14px !important;}
[class*="st-key-activity-card-"] [data-testid="stBaseButton-tertiary"] p {text-decoration: underline; text-underline-offset: 3px; color: #063465;}
.st-key-explore-filters {background: #F5F8FC; border: 1px solid #D5DDE7; border-radius: 14px; padding: .8rem 1.1rem;}
[class*="st-key-profile-group-"] {background: #FFFFFF; border: 1px solid #D5DDE7; border-radius: 14px; padding: 1rem 1.2rem; height: 100%;}
.st-key-profile-next {background: #EEF4FB; border: 1px solid #C9D8EA; border-left: 5px solid #FE6A01; border-radius: 14px; padding: 1.1rem 1.4rem; margin-top: .8rem;}
.st-key-profile-next h3 {font-size: 1.3rem !important; color: #063465;}
.st-key-profile-next-main [data-testid="stBaseButton-primary"]:not(:disabled) {background-color: #FE6A01 !important; border-color: #FE6A01 !important;}
.st-key-profile-next-main button {min-height: 2.9rem; padding: 0 1.3rem;}
.st-key-profile-next [data-testid="stBaseButton-secondary"]:disabled, .st-key-profile-next [data-testid="stBaseButton-primary"]:disabled {background: #F5F8FC !important; border: 1px dashed #9FB0C6 !important; opacity: 1;}
.st-key-profile-next button:disabled p {color: #5A6E88 !important;}
.st-key-profile-next-more [data-testid="stBaseButton-tertiary"] p {text-decoration: underline; text-underline-offset: 3px;}
.st-key-profile-next-more > [data-testid="stElementContainer"] {width: auto !important; flex: 0 0 auto !important;}
.st-key-profile-next-more > [data-testid="stElementContainer"] {width: auto !important; flex: 0 0 auto !important;}
@media (max-width: 640px) {
    .st-key-profile-next-main > [data-testid="stElementContainer"], .st-key-profile-next-main .stButton, .st-key-profile-next-main button {width: 100% !important; max-width: 100% !important; flex: 1 1 100% !important;}
    .st-key-profile-next-more {gap: .2rem 1rem !important;}
}
.flow-row {display: flex; align-items: stretch; gap: .35rem; margin: .2rem 0 .3rem;}
.flow-box {flex: 1 1 0; min-width: 0; min-height: 6.2rem; display: flex; flex-direction: column; gap: .3rem;
    background: #F3F8F5; border: 1px solid #D6E9DE; border-radius: 12px; padding: .75rem .9rem; color: #063465;}
.flow-box b {font-size: .98rem;}
.flow-box span {font-size: .85rem; color: #4D5B6A; line-height: 1.45;}
.st-key-hero-cta-help p.cta-help {margin: .6rem 0 0; padding: .55rem .8rem; border-left: 3px solid #FE6A01; background: #FFF6EF;
    border-radius: 0 8px 8px 0; color: #063465; font-size: 1.02rem; line-height: 1.5;}
.flow-box.flow-ai {background: #EEF3FA; border-color: #B9CCE4;}
.flow-arrow {flex: 0 0 auto; align-self: center; color: #FE6A01; font-weight: 700; font-size: 1.3rem;}
@media (max-width: 640px) {
    .flow-row {flex-direction: column; gap: .15rem;}
    .flow-box {flex: 0 0 auto; min-height: 0;}
    .flow-arrow {transform: rotate(90deg); line-height: 1;}
}
.st-key-home-body {padding-top: 1.2rem;}
@media (max-width: 640px) {
    .st-key-home-hero-band {margin-left: -1rem !important; width: calc(100% + 2rem) !important; padding: 1rem 1rem 1.2rem;}
    .st-key-hero-cta [data-testid="stBaseButton-primary"] {width: 100%;}
}
@media (max-width: 640px) {[data-testid="stMainBlockContainer"] {padding-left: 1rem; padding-right: 1rem;}}
/* 화면 전체 폭으로 퍼지는 색 띠 */
.st-key-band-hero, .st-key-band-notes {margin-left: -2.5rem !important; width: calc(100% + 5rem) !important; max-width: none !important; padding: 1.6rem 2.5rem; box-sizing: border-box;}
.st-key-band-hero {background: linear-gradient(120deg, #E6EEF8 0%, #F3F6FB 55%, #FFF1E6 100%);}
.st-key-band-notes {background: #F2F5F9; border-top: 3px solid #FE6A01;}
@media (max-width: 640px) {.st-key-band-hero, .st-key-band-notes {margin-left: -1rem !important; width: calc(100% + 2rem) !important; padding: 1.2rem 1rem;}}
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
@media (hover: hover) {
[data-testid="stBaseButton-primary"]:hover, [data-testid="stBaseButton-primaryFormSubmit"]:hover {
    background-color: #FE6A01 !important; border-color: #FE6A01 !important;
}
[data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-secondaryFormSubmit"], [data-testid="stBaseLinkButton-secondary"] {
    border-color: #9FB0C6 !important; color: #063465 !important; background-color: #FFFFFF !important;
}
[data-testid="stBaseButton-secondary"]:hover, [data-testid="stBaseLinkButton-secondary"]:hover {
    border-color: #FE6A01 !important; color: #FE6A01 !important;
}
[data-testid="stExpander"] summary:hover p {color: #FE6A01;}
}
/* 처음 화면: 여백에 색 · 큰 글씨 · 큰 버튼 */
.st-key-home-buttons {background: #EEF3F9; border-radius: 1.1rem; padding: 1.2rem;}
.st-key-home-guide {background: #FFF6EE; border-radius: 1.1rem; padding: 1.2rem 1.4rem;}
.st-key-start-card {background: #FFFFFF; border: 2px solid #FE6A01; border-radius: .9rem; padding: .9rem 1rem;}
[class*="st-key-how-to-"], [class*="st-key-feature-summary-"] {background: #FFFFFF; border-radius: .8rem; padding: .6rem .9rem; border: 1px solid #F3DCC8;}
.st-key-home-buttons [data-testid="stMarkdownContainer"] p, .st-key-home-guide [data-testid="stMarkdownContainer"] p {font-size: 1.08rem;}
.st-key-home-buttons [data-testid="stCaptionContainer"], .st-key-home-guide [data-testid="stCaptionContainer"] {font-size: .98rem;}
.st-key-home-buttons button, .st-key-profile-features button {min-height: 3.2rem;}
.st-key-home-buttons button p, .st-key-profile-features button p {font-size: 1.08rem !important; font-weight: 600;}
/* 첫 화면: 색 배경으로 구역 나누기 · 큰 글자 · 큰 기능 버튼 */
@media (min-width: 1024px) { html {font-size: 17px;} }
.st-key-band-hero [data-testid="stMarkdownContainer"] p {font-size: 1.05rem;}
.st-key-start-card {background: #FFF4EC; border-left: 6px solid #FE6A01; border-radius: 14px; padding: 1rem 1.4rem;}
[class*="st-key-feature-card-"] {background: #F5F8FC; border: 1px solid #D5DDE7; border-radius: 14px; padding: .9rem 1rem; height: 100%;}
.st-key-feature-grid [data-testid="stBaseButton-primary"] {min-height: 3.6rem;}
.st-key-feature-grid [data-testid="stBaseButton-primary"] p {font-size: 1.12rem; font-weight: 700;}
.st-key-ai-banner {background: #063465; border-radius: 14px; padding: 1rem 1.4rem;}
.st-key-ai-banner p, .st-key-ai-banner [data-testid="stCaptionContainer"], .st-key-ai-banner [data-testid="stCaptionContainer"] p {color: #FFFFFF !important;}
.st-key-ai-banner [data-testid="stBaseButton-secondary"] {background-color: #FE6A01 !important; border-color: #FE6A01 !important; color: #FFFFFF !important;}
.st-key-ai-banner [data-testid="stBaseButton-secondary"] p {color: #FFFFFF !important; font-weight: 700;}
.st-key-ai-banner [data-testid="stBaseButton-secondary"]:disabled {background-color: #5B7393 !important; border-color: #5B7393 !important;}
/* 잠긴(비활성) 버튼은 흐리게 */
[data-testid="stBaseButton-primary"]:disabled {
    background-color: #C9D3E0 !important; border-color: #C9D3E0 !important; color: #FFFFFF !important; cursor: not-allowed;
}
[data-testid="stBaseButton-secondary"]:disabled {color: #A9B4C2 !important; border-color: #D5DDE7 !important;}
/* 터치 화면: 누르는 순간만 주황 */
[data-testid="stBaseButton-primary"]:active, [data-testid="stBaseButton-primaryFormSubmit"]:active {
    background-color: #FE6A01 !important; border-color: #FE6A01 !important;
}
/* 모바일: 큰 제목·할 일 글씨를 한 줄에 가깝게 */
@media (max-width: 640px) {
    h2 {font-size: 1.45rem !important;}
    [data-testid="stExpander"] summary p {font-size: .98rem; line-height: 1.4;}
    [data-testid="stExpander"] [data-testid="stCheckbox"] p {font-size: 1.1rem;}
}
[data-testid="stProgress"] [role="progressbar"] > div > div > div {background-color: #2E9E6B !important;}
[data-testid="stProgress"] [role="progressbar"] div[style*="translateX"] {background-color: #2E9E6B !important;}
.st-key-home-body [data-testid="stExpander"] summary p {font-size: 1rem; font-weight: 600;}
.st-key-home-hero-band [data-testid="stColumn"] {padding-top: .6rem; padding-bottom: .6rem;}
[data-testid="stSidebar"] {border-right: 3px solid #FE6A01;}
[data-testid="stExpander"] details {border-color: #D5DDE7;}
.st-key-home-ask-row {background: #F7F9FC; border: 1px solid #D5DDE7; border-radius: 12px; padding: .8rem 1rem; gap: .35rem; margin-top: .4rem;}
.st-key-home-ask-row [data-testid="stCaptionContainer"] p {font-size: .82rem;}
/* 10/3 UI: 화면 맨 위 흰 띠(Streamlit 공유·별표·편집·GitHub·메뉴 버튼) 숨김 — 왼쪽 메뉴 열기(>>) 버튼만 남김 */
[data-testid="stHeader"] {background: transparent !important; box-shadow: none !important;}
/* 투명한 머리 띠가 ‘← 처음으로’ 버튼 클릭을 가로채지 않게 (10/4 이혜경: 처음으로가 안 눌림) */
[data-testid="stHeader"], [data-testid="stHeader"] * {pointer-events: none !important;}
[data-testid="stHeader"] [data-testid="stExpandSidebarButton"], [data-testid="stHeader"] [data-testid="stExpandSidebarButton"] * {pointer-events: auto !important;}
[data-testid="stToolbarActions"], [data-testid="stAppDeployButton"], [data-testid="stMainMenu"], [data-testid="stDecoration"] {display: none !important;}
[data-testid="stMainBlockContainer"] {padding-top: 1.2rem !important;}
.st-key-home-hero-band {margin-top: -1.2rem !important; padding-top: 2.4rem !important;}
/* 10/3 UI 다듬기 2차(기능 변경 없음): 휴대폰 빈 공간·버튼 줄바꿈 줄이기 */

@media (max-width: 640px) {
    .st-key-home-hero-inner [data-testid="stHorizontalBlock"] {gap: .9rem !important;}
    .st-key-home-hero-band {padding-bottom: 1rem;}
    [class*="st-key-tab-"] button {padding: .3rem .65rem; min-height: 2.4rem;}
    [class*="st-key-tab-"] button p {font-size: .84rem;}
    .st-key-journey-summary [data-testid="stHorizontalBlock"] {gap: .4rem !important;}
    [class*="st-key-milestone-"] {padding: .55rem .9rem; gap: .2rem;}
    [data-testid="stMainBlockContainer"] {padding-top: 3rem !important;}
    [data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-primary"] {min-height: 2.6rem;}
}
/* 10/4: 신뢰 안내와 위 안내 상자 사이 간격, 생활 정보 필터 선택칸을 흰색+테두리로 구분 */
.st-key-hero-trust {margin-top: .55rem;}
.st-key-explore-filters [data-testid="stSelectbox"] > div > div {background: #FFFFFF !important; border: 1px solid #9FB0C6 !important; border-radius: .6rem;}
.st-key-explore-filters [data-testid="stSelectbox"] > div > div:hover {border-color: #063465 !important;}
/* 10/3 UX/UI 다듬기(기능 변경 없음): 글자 대비·섹션 제목·간격 통일 */
/* 10/3 첫 화면 다듬기(이혜경 요청): 파란 영역 15% 줄이기·소개 3줄 간격·버튼과 구분·현황 카드·기능 카드 여백 */
.st-key-home-hero-band {padding-top: 1.6rem !important; padding-bottom: 1.1rem !important;}
.st-key-home-hero-band [data-testid="stColumn"] {padding-top: .3rem; padding-bottom: .3rem;}
.st-key-home-hero-band .st-key-slogan h3 {font-size: 1.4rem !important; padding-bottom: .2rem;}
.st-key-hero-intro {gap: .15rem; margin-bottom: 1.1rem;}
.st-key-hero-intro p {font-size: 1.05rem !important; line-height: 1.8;}
p.hero-lines {line-height: 1.9; margin: 0 0 1rem;}
.st-key-hero-cta-help p.cta-help {margin-top: .2rem;}
/* 예시·현황 카드: 글자 겹침 없게 원래 간격으로 (10/4) */
.st-key-hero-progress, .st-key-hero-example {padding: 1rem 1.3rem !important; gap: .6rem !important;}
/* ‘이렇게 일해요’ 상자와 ‘이 서비스가 하는 일’ 카드: 같은 높이·여백·모서리 (10/4) */
[class*="st-key-home-card-"] {padding: .9rem 1rem !important; min-height: 11rem !important; border-radius: 14px !important;}
.flow-box {min-height: 9.5rem !important; padding: .9rem 1rem !important; border-radius: 14px !important; box-sizing: border-box;}
.flow-box b {font-size: 1.02rem !important;}
.flow-box span {font-size: .9rem !important;}
@media (max-width: 640px) {.flow-box {min-height: 0 !important;}}
@media (max-width: 640px) {[class*="st-key-home-card-"] {min-height: 0 !important;}}
.sec-title.sec-gap {margin-top: 2.4rem;}

[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {color: #4D5B6A;}
.stApp [data-testid="stCaptionContainer"] p {line-height: 1.6;}
.stApp p.sec-title {font-size: 1.4rem !important; font-weight: 700; color: #063465; margin: 1.6rem 0 .5rem;}
.st-key-hero-cta-help {margin-bottom: .45rem;}
.st-key-hero-cta-help p {line-height: 1.7;}
.st-key-agent-flow {margin-bottom: .8rem;}
.st-key-page-policy [data-testid="stExpander"] summary p, .st-key-page-explore [data-testid="stExpander"] summary p,
.st-key-page-dialect [data-testid="stExpander"] summary p, .st-key-page-complaint [data-testid="stExpander"] summary p
    {font-size: 1.05rem; font-weight: 600;}

/* ===== 10/4 첫 화면 새 디자인(이혜경: 젊고 감각적으로, 로고는 작게 한쪽 끝) — 기능·문구는 그대로 ===== */
.stApp, .stApp button, .stApp input, .stApp textarea {font-family: "Pretendard Variable", Pretendard, "Noto Sans KR", -apple-system, sans-serif !important;}
.st-key-home-hero-band {position: relative; overflow: hidden; border-radius: 0 0 28px 28px;
    background: radial-gradient(circle at 88% 12%, rgba(254,106,1,.38) 0, rgba(254,106,1,0) 32%),
                radial-gradient(circle at 8% 100%, rgba(46,158,107,.28) 0, rgba(46,158,107,0) 30%),
                linear-gradient(135deg, #041F3D 0%, #063465 52%, #0B4C8C 100%) !important;
    margin-top: -2.3rem !important; padding-top: 2.4rem !important; padding-bottom: 2.4rem !important;}
.st-key-home-topbar {padding: .2rem 0 1.4rem; border-bottom: 1px solid rgba(255,255,255,.12); margin-bottom: 1.6rem;}
.st-key-home-topbar [data-testid="stImage"] img {width: 168px !important; height: auto;}
.top-pill {display: inline-block; padding: .35rem .85rem; border-radius: 999px; font-size: .82rem; font-weight: 600;
    color: #FFFFFF; background: rgba(255,255,255,.10); border: 1px solid rgba(255,255,255,.22); letter-spacing: -.01em;}
.hero-eyebrow {display: inline-block; padding: .3rem .75rem; border-radius: 999px; font-size: .8rem; font-weight: 700;
    color: #FFB98A; background: rgba(254,106,1,.14); border: 1px solid rgba(254,106,1,.45); letter-spacing: .02em;}
.st-key-home-hero-band .st-key-slogan h3 {font-size: clamp(1.9rem, 3.6vw, 2.9rem) !important; font-weight: 800 !important;
    line-height: 1.22 !important; letter-spacing: -.03em; padding: .5rem 0 .4rem !important;
    background: linear-gradient(92deg, #FFFFFF 0%, #FFFFFF 55%, #FFB98A 100%); -webkit-background-clip: text; background-clip: text;
    -webkit-text-fill-color: transparent; color: #FFFFFF;}
.st-key-hero-intro p, .st-key-hero-intro p b {color: rgba(255,255,255,.86) !important;}
.st-key-hero-intro p b {color: #FFFFFF !important;}
.st-key-hero-cta [data-testid="stBaseButton-primary"] {border-radius: 999px !important; min-height: 3.2rem; padding: 0 1.8rem;
    box-shadow: 0 10px 28px rgba(254,106,1,.40); transition: transform .15s ease, box-shadow .15s ease;}
.st-key-hero-cta [data-testid="stBaseButton-primary"]:hover {transform: translateY(-2px); box-shadow: 0 14px 32px rgba(254,106,1,.5);}
.st-key-hero-cta [data-testid="stBaseButton-tertiary"] {border: 1px solid rgba(255,255,255,.35) !important; border-radius: 999px !important;
    padding: .55rem 1.2rem !important; min-height: 3.2rem;}
.st-key-hero-cta [data-testid="stBaseButton-tertiary"] p {color: #FFFFFF !important; font-weight: 600;}
.st-key-hero-cta [data-testid="stBaseButton-tertiary"]:hover {background: rgba(255,255,255,.10) !important;}
.st-key-hero-cta-help p.cta-help {background: rgba(255,255,255,.08) !important; border-left: 3px solid #FE6A01 !important;
    color: rgba(255,255,255,.92) !important; border-radius: 0 12px 12px 0; backdrop-filter: blur(6px);}
.st-key-hero-trust [data-testid="stCaptionContainer"] p {color: rgba(255,255,255,.66) !important;}
.st-key-hero-example, .st-key-hero-progress {background: rgba(255,255,255,.97) !important; border: none !important;
    border-radius: 22px !important; box-shadow: 0 24px 60px rgba(2,16,34,.38); padding: 1.6rem 1.5rem 1.4rem !important; position: relative; overflow: hidden;}
.st-key-hero-example::before, .st-key-hero-progress::before {content: ""; position: absolute; left: 0; right: 0; top: 0;
    height: 5px; background: linear-gradient(90deg, #FE6A01, #2E9E6B);}
.st-key-hero-example p.hero-lines {line-height: 2.05;}
/* 아래 영역: 카드형·둥근 모서리·부드러운 그림자 */
.stApp p.sec-title {font-weight: 800 !important; letter-spacing: -.02em; display: flex; align-items: center; gap: .55rem;}
.stApp p.sec-title::before {content: ""; width: 6px; height: 1.2em; border-radius: 3px; background: linear-gradient(180deg, #FE6A01, #063465);}
.flow-box {border-radius: 18px !important; background: #FFFFFF !important; border: 1px solid #E3E9F1 !important;
    box-shadow: 0 6px 18px rgba(6,52,101,.06);}
.flow-box.flow-ai {background: linear-gradient(160deg, #F1F5FF 0%, #FFFFFF 70%) !important; border-color: #C9D7F0 !important;}
.flow-box b {color: #063465;}
.flow-arrow {color: #FE6A01;}
[class*="st-key-home-card-"] {border: 1px solid #E3E9F1 !important; border-top: 1px solid #E3E9F1 !important; border-radius: 18px !important;
    box-shadow: 0 6px 18px rgba(6,52,101,.06); position: relative; overflow: hidden; transition: transform .15s ease, box-shadow .15s ease;}
[class*="st-key-home-card-"]::before {content: ""; position: absolute; left: 0; right: 0; top: 0; height: 4px; background: linear-gradient(90deg, #063465, #FE6A01);}
[class*="st-key-home-card-"]:hover {transform: translateY(-3px); box-shadow: 0 14px 30px rgba(6,52,101,.12);}
.st-key-home-ask-row {border-radius: 18px !important; background: linear-gradient(120deg, #FFF4EB 0%, #F4F7FC 100%) !important; border: 1px solid #F3D9C6 !important;}
@media (max-width: 640px) {
    .st-key-home-hero-band {margin-top: -4rem !important; padding-top: 3.6rem !important; border-radius: 0 0 22px 22px;}
    .st-key-home-topbar {padding-bottom: 1rem; margin-bottom: 1.1rem; flex-wrap: nowrap !important; gap: .5rem !important;}
    .st-key-home-topbar > div {width: auto !important; flex: 0 1 auto !important;}
    .st-key-home-topbar [data-testid="stImage"] img {width: 132px !important;}
    .top-pill {font-size: .72rem; padding: .28rem .65rem;}
    .st-key-hero-cta [data-testid="stBaseButton-tertiary"] {width: 100%;}
}
@media (max-width: 380px) {.top-pill {display: none;}}

/* ===== 10/4 세부 화면 새 디자인(첫 화면과 같은 컨셉): 남색 머리 띠 · 연한 배경 위 흰 카드 · 둥근 버튼 ===== */
[class*="st-key-page-hero-"]:not([class*="st-key-page-hero-top-"]) {position: relative; overflow: hidden; border-radius: 26px;
    padding: 1.1rem 1.8rem 1.7rem !important; margin: .2rem 0 1.4rem; gap: .45rem !important;
    background: radial-gradient(circle at 92% 0%, rgba(254,106,1,.36) 0, rgba(254,106,1,0) 34%),
                radial-gradient(circle at 0% 100%, rgba(46,158,107,.26) 0, rgba(46,158,107,0) 32%),
                linear-gradient(135deg, #041F3D 0%, #063465 55%, #0B4C8C 100%);
    box-shadow: 0 18px 44px rgba(4,31,61,.22);}
[class*="st-key-page-hero-top-"] {padding-bottom: .7rem; margin-bottom: .5rem; border-bottom: 1px solid rgba(255,255,255,.12);}
span.page-hero-logo {display: block; width: 132px; height: 33px; background-size: contain; background-repeat: no-repeat; background-position: right center;}
[class*="st-key-page-hero-"] [data-testid="stHeading"] h3 {color: #FFFFFF !important; font-size: clamp(1.5rem, 2.6vw, 2.1rem) !important;
    font-weight: 800 !important; letter-spacing: -.03em; line-height: 1.25; padding: .35rem 0 .1rem !important;}
p.page-hero-desc {color: rgba(255,255,255,.82) !important; font-size: 1.02rem; line-height: 1.7; margin: .35rem 0 0;}
p.page-hero-desc b {color: #FFFFFF;}
[class*="st-key-page-hero-top-"] [data-testid="stBaseButton-secondary"] {background: rgba(255,255,255,.08) !important;
    border: 1px solid rgba(255,255,255,.3) !important; border-radius: 999px !important; min-height: 2.3rem; padding: .2rem 1rem;}
[class*="st-key-page-hero-top-"] [data-testid="stBaseButton-secondary"] p {color: #FFFFFF !important; font-weight: 600;}
[class*="st-key-page-hero-top-"] [data-testid="stBaseButton-secondary"]:hover {background: rgba(255,255,255,.18) !important;}
.st-key-feature2-tabs {margin-top: .6rem;}
.st-key-feature2-tabs button {border-radius: 999px !important; min-height: 2.5rem; padding: .3rem 1.1rem !important;}
.st-key-feature2-tabs [data-testid="stBaseButton-secondary"] {background: rgba(255,255,255,.08) !important; border: 1px solid rgba(255,255,255,.3) !important;}
.st-key-feature2-tabs [data-testid="stBaseButton-secondary"] p {color: #FFFFFF !important;}
.st-key-feature2-tabs [data-testid="stBaseButton-primary"] {background: #FE6A01 !important; border-color: #FE6A01 !important; box-shadow: 0 8px 20px rgba(254,106,1,.35);}
/* 본문: 연한 배경 위에 흰 카드 */
[class*="st-key-page-"]:not(.st-key-page-home):not([class*="st-key-page-hero"]) [data-testid="stHeading"] h3 {color: #063465; font-weight: 800; letter-spacing: -.02em;}
[class*="st-key-policy-card-"], [class*="st-key-activity-card-"], [class*="st-key-channel-"], [class*="st-key-level-count-"],
.st-key-journey-summary, [class*="st-key-milestone-"], .st-key-complaint-input, .st-key-profile-next
    {background: #FFFFFF !important; border: 1px solid #E3E9F1 !important; border-radius: 18px !important;
     box-shadow: 0 6px 18px rgba(6,52,101,.06);}
[class*="st-key-policy-card-"]:hover, [class*="st-key-activity-card-"]:hover {box-shadow: 0 14px 30px rgba(6,52,101,.12); transform: translateY(-2px);
    transition: transform .15s ease, box-shadow .15s ease;}
.st-key-level-count-level-ok {border-top: 4px solid #2E9E6B !important;}
.st-key-level-count-level-cond {border-top: 4px solid #063465 !important;}
.st-key-level-count-level-check {border-top: 4px solid #FE6A01 !important;}
[class*="st-key-page-"]:not(.st-key-page-home) [data-testid="stExpander"] details {background: #FFFFFF; border-radius: 16px !important; border-color: #E3E9F1 !important;}
[class*="st-key-page-"]:not(.st-key-page-home) [data-testid="stBaseButton-primary"] {border-radius: 999px !important; box-shadow: 0 8px 18px rgba(6,52,101,.18);}
[class*="st-key-page-"]:not(.st-key-page-home) [data-testid="stBaseButton-secondary"] {border-radius: 999px !important;}
[class*="st-key-page-"]:not(.st-key-page-home) [data-testid="stTextInput"] input, [class*="st-key-page-"]:not(.st-key-page-home) [data-testid="stNumberInput"] input,
[class*="st-key-page-"]:not(.st-key-page-home) [data-testid="stDateInput"] input {background: #FFFFFF !important;}
[class*="st-key-page-"]:not(.st-key-page-home) [data-testid="stForm"] {background: #FFFFFF; border: 1px solid #E3E9F1; border-radius: 18px;}
@media (max-width: 640px) {
    [class*="st-key-page-hero-"]:not([class*="st-key-page-hero-top-"]) {padding: .9rem 1.1rem 1.3rem !important; border-radius: 20px;}
    span.page-hero-logo {width: 104px; height: 26px;}
}
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
PAGE_HOME = "home"
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
ASK_LABEL = "오이소창원에게 물어보기"
# 앱 문의: 여러 곳에 중복으로 보이던 것을 정리해 화면 맨 아래 한 곳에만 (10/3 이혜경)
CONTACT_EMAIL = "whwnstn9294@gmail.com"
CONTACT_TEXT = f"앱 문의: [{CONTACT_EMAIL}](mailto:{CONTACT_EMAIL})"
# 버튼에는 순번 없이 이름만(제목에는 기획안 순번 유지)
BUTTON_1, BUTTON_2, BUTTON_3, BUTTON_4 = (name[2:] for name in (FEATURE_1, FEATURE_2, FEATURE_3, FEATURE_4))
FEATURE_2_TABS = {PAGE_JOURNEY: "정착 할 일 · 1~6개월 일정", PAGE_EXPLORE: "창원 생활 정보 둘러보기"}
# 사이드바 메뉴: (page, 버튼 이름)
PAGE_LABELS = {
    PAGE_HOME: "처음 화면",
    PAGE_PROFILE: "나의 조건 입력",
    PAGE_ASK: ASK_LABEL,
    PAGE_POLICY: BUTTON_1,
    PAGE_JOURNEY: "└ " + FEATURE_2_TABS[PAGE_JOURNEY],
    PAGE_EXPLORE: "└ " + FEATURE_2_TABS[PAGE_EXPLORE],
    PAGE_COMPLAINT: BUTTON_3,
    PAGE_DIALECT: BUTTON_4,
}
# 기획안 핵심기능 4개만 '기능 버튼'. 조건 입력(STEP 1)과 오이소창원에게 물어보기(STEP 3)는 별도 안내 칸.
FEATURE_BUTTONS = (
    (PAGE_POLICY, BUTTON_1, "show-policy"),
    (PAGE_JOURNEY, BUTTON_2, "show-journey"),
    (PAGE_COMPLAINT, BUTTON_3, "show-complaint"),
    (PAGE_DIALECT, BUTTON_4, "show-dialect"),
)
DISTRICT_PLACEHOLDER = "지역을 선택해 주세요"
# 창원에서 하는 일 — 직장인만 기업노동자 전입지원금 대상(근무하는 노동자), 자영업은 재직 대상 사업마다 기관 확인.
EMPLOYMENT_OPTIONS = ("직장인", "자영업", "학생", "기타")
WORKING_OPTIONS = ("직장인", "자영업")
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
        args=(PAGE_HOME,),
    )


@st.cache_data(show_spinner=False)
def _logo_light_data_uri():
    # 세부 화면 머리 띠의 작은 로고(그림 요소 대신 HTML로 — 화면당 그림 1개 규칙 유지)
    from PIL import Image
    import io, base64
    image = Image.open(LOGO_LIGHT_PATH)
    image = image.resize((320, round(image.height * 320 / image.width)))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def _page_hero(position, title, desc=None, eyebrow=None):
    """세부 화면 머리 띠(10/4 이혜경: 첫 화면과 같은 컨셉) — 처음으로 버튼 · 작은 로고 · 제목 · 한 줄 설명.
    with 문으로 쓰면 띠 안에 버튼(탭 등)을 더 넣을 수 있다."""
    hero = st.container(key=f"page-hero-{position}")
    with hero:
        with st.container(key=f"page-hero-top-{position}", horizontal=True, vertical_alignment="center",
                          horizontal_alignment="distribute"):
            _back_home_button(position)
            st.markdown('<span class="page-hero-logo" role="img" aria-label="오이소창원"></span>', unsafe_allow_html=True)
        if eyebrow:
            st.markdown(f'<span class="hero-eyebrow">{html.escape(eyebrow)}</span>', unsafe_allow_html=True)
        st.subheader(title, anchor=False)
        if desc:
            st.markdown(f'<p class="page-hero-desc">{desc}</p>', unsafe_allow_html=True)
    return hero


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
    layout="wide",
)

st.html(READABILITY_CSS)

_keep_widget_values()
st.session_state.setdefault("page", PAGE_HOME)

nickname = st.session_state["nickname"]
user_key = nickname.strip()
if not user_key and st.session_state["page"] not in (PAGE_HOME, PAGE_PROFILE):
    st.session_state["page"] = PAGE_HOME
page = st.session_state["page"]
# 첫 화면(처음 들어온 사람)에서는 왼쪽 메뉴를 숨기고, ‘시작하기’로 다른 화면에 간 뒤부터 보여 줌 (10/3 이혜경)
if page != PAGE_HOME or user_key:
    st.session_state["sidebar_unlocked"] = True
if not st.session_state.get("sidebar_unlocked"):
    st.markdown(
        "<style>[data-testid='stSidebar'], [data-testid='stExpandSidebarButton'], "
        "[data-testid='stSidebarCollapsedControl'] {display: none !important;}</style>",
        unsafe_allow_html=True,
    )

saved_mission_states = load_mission_states(user_key) if user_key else {}
saved_mission_notes = load_mission_notes(user_key) if user_key else {}
saved_mission_timestamps = load_mission_timestamps(user_key) if user_key else {}


# --- 처음 화면: STEP 1 조건 입력 카드 + STEP 2 기능 버튼 5개 -------------------
CONDITION_LABEL = "나의 조건 입력"
PROFILE_EDIT_LABEL = "나의 조건 확인·수정"
# 첫 화면 주황 버튼 바로 위 안내 (10/3 이혜경 문구)
CTA_HELP = "창원 생활, 어디서부터 시작할지 고민되나요?  \n먼저 나의 조건을 확인하면 필요한 정보를 맞춤 안내해 드려요."
CTA_HELP_HTML = '<p class="cta-help">' + html.escape(CTA_HELP).replace("  \n", "<br>") + "</p>"
DATA_COUNTS = [
    (label, count, unit)
    for label, count, unit in (
        ("정책", POLICY_COUNT, "건"), ("정착 할 일", MISSION_COUNT, "개"), ("생활 정보", ACTIVITY_COUNT, "곳"),
        ("지역말", DIALECT_COUNT, "개"), ("접수 창구", CHANNEL_COUNT, "곳"),
    )
    if count
]
APP_INTRO = (
    "창원에 막 이사 온 청년이 처음 6개월 동안 놓치기 쉬운 혜택과 할 일을 한곳에서 챙길 수 있게 돕는 서비스예요. "
    "공식 자료로 확인한 "
    + "·".join(f"{label} {count:,}{unit}" for label, count, unit in DATA_COUNTS)
    + ("를" if DATA_COUNTS and DATA_COUNTS[-1][2] == "개" else "을")
    + " 바탕으로, 오이소창원(코디네이터 Agent)이 내 조건에 맞춰 안내해요."
)
HOW_TO_STEPS = (
    (CONDITION_LABEL, "나이·전입일 같은 조건만 적어요"),
    ("기능 4개 중 고르기", "혜택·정착 일정·불편 접수·지역말"),
    ("오이소창원에게 묻기", "궁금한 건 한 문장으로"),
)
FEATURE_SUMMARIES = {
    PAGE_POLICY: f"정책 {POLICY_COUNT}건을 내 조건과 비교해 해당 가능·조건부·신청 시기를 알려 줘요.",
    PAGE_JOURNEY: "1~6개월 정착 할 일 체크와 창원 가볼 곳·행사를 안내해요.",
    PAGE_COMPLAINT: "불편한 상황의 긴급도를 판단해 알맞은 접수 창구를 알려 줘요.",
    PAGE_DIALECT: "직장·식당에서 들은 창원 말의 뜻과 쓰임을 알려 줘요.",
}
USAGE_NOTES = (
    "실명·연락처 등 개인정보는 받지 않아요. 닉네임과 나이·전입일 같은 조건만 써요.",
    "이메일 일정 알림은 선택 기능이에요. 직접 신청하지 않으면 이메일을 받지 않고, 신청하면 개인정보 수집·이용 동의와 "
    "이메일 수신 동의를 받은 뒤에 일정 알림을 보내요. 해지하면 이메일은 바로 삭제돼요.",
    "안내는 공식 자료로 확인한 정보(확인일 표시) 기준이에요. 지원 대상 여부의 최종 판단은 담당 기관에서 해요.",
    "장소·행사는 방문 전 운영시간을 꼭 확인해 주세요. 특정 업체 홍보가 아니에요.",
    "AI 답변은 검증 자료 안에서만 만들지만 틀릴 수 있어요. 중요한 내용은 링크로 원문을 확인해 주세요.",
)


def _feature_buttons(with_descriptions=False, per_row=2):
    # 기획안 핵심기능 4개(① 혜택 알림 ② 생활 정보·일정 편성 ③ 불편 접수 ④ 지역말 번역)
    with st.container(key="feature-grid"):
        rows = [FEATURE_BUTTONS[i:i + per_row] for i in range(0, len(FEATURE_BUTTONS), per_row)]
        for row in rows:
            columns = st.columns(per_row, gap="small")
            for column, (target_page, label, key) in zip(columns, row):
                with column:
                    with st.container(key=f"feature-card-{target_page}"):
                        st.button(
                            label,
                            key=key,
                            type="primary",
                            disabled=not user_key,
                            on_click=_go,
                            args=(target_page,),
                            width="stretch",
                        )
                        if with_descriptions:
                            _caption(FEATURE_SUMMARIES[target_page])


def _ai_banner():
    with st.container(key="ai-banner"):
        text_col, button_col = st.columns([3, 1], vertical_alignment="center")
        with text_col:
            st.markdown(f"**STEP 3 · 궁금한 건 {ASK_LABEL}**")
            _caption("“내가 받을 수 있는 지원 알려줘”, “버스로 갈 만한 야경 명소?”처럼 한 문장으로 물어보세요.")
        with button_col:
            st.button(
                f"{ASK_LABEL} →",
                key="show-ask",
                disabled=not user_key,
                on_click=_go,
                args=(PAGE_ASK,),
                width="stretch",
            )


def _condition_card():
    with st.container(key="start-card"):
        text_col, button_col = st.columns([3, 1], vertical_alignment="center")
        with text_col:
            st.markdown(f"**STEP 1 · {CONDITION_LABEL}**")
            if user_key:
                _caption(f"{user_key}님의 조건이 입력돼 있어요. 바꾸려면 오른쪽 버튼을 눌러 주세요.")
            else:
                _caption("나이·창원 전입일 같은 조건만 적으면 아래 기능 4개가 열려요. 개인정보는 받지 않아요. "
                           "먼저 둘러보려면 들어가서 ‘예시 정보로 채우기’를 눌러 보세요.")
        with button_col:
            if user_key:
                st.button(PROFILE_EDIT_LABEL, key="show-profile", on_click=_go, args=(PAGE_PROFILE,), width="stretch")
            else:
                st.button(f"{CONDITION_LABEL}하기 →", key="show-profile", type="primary", on_click=_go,
                          args=(PAGE_PROFILE,), width="stretch")


HOME_FEATURES = (
    (PAGE_POLICY, BUTTON_1, f"내 조건과 정책 {POLICY_COUNT}건을 비교해 먼저 확인할 혜택을 찾아요."),
    (PAGE_JOURNEY, BUTTON_2, "첫 180일의 할 일과 창원 생활을 함께 계획해요."),
    (PAGE_COMPLAINT, BUTTON_3, "상황에 맞는 행정 접수 창구를 찾아요."),
    (PAGE_DIALECT, BUTTON_4, "낯선 창원·경상 지역 표현을 문헌 자료 기준으로 풀어드려요."),
)
FEATURE_KEYS = {target: key for target, _, key in FEATURE_BUTTONS}
AI_FLOW_CLASS = " flow-ai"
# (제목, 설명, AI 동작 여부) — AI가 일하는 단계는 상자 색만 연한 남색으로
AGENT_FLOW = (
    ("내 조건", "나이·전입일·하는 일·차량 소지 여부", False),
    ("AI 분석 · 조건 비교", "질문은 AI가 분석하고 필요한 도구 선정, 혜택은 정책과 규칙으로 비교", True),
    ("검증 자료 확인", "공식 자료만 찾고, AI 답의 연락처·링크를 자료와 대조", False),
    ("AI 맞춤 결과 안내", "해당 가능 혜택·추천 장소·접수 창구, AI가 답 문장 작성", True),
    ("일정 저장 및 알림(선택)", "캘린더·정착 리포트로 내 기기에 보관, 원하면 이메일 알림", False),
)
# 예시 카드: 창원·경남에서만 주는 혜택을 먼저, 그다음 청년이 많이 찾는 지원 (모두 data/policies_mvp.json에 있는 사업)
EXAMPLE_CHECKS = (
    ("✓", "새 주소로 전입신고 하기"),
    ("○", "창원 기업노동자 전입지원금 확인"),
    ("○", "창원시 청년월세 지원 알림 받기"),
    ("○", "K-패스 대중교통비 환급 신청"),
)


def _start_demo():
    _fill_profile(DEMO_PROFILE)
    _go(PAGE_PROFILE)


def _hero_progress_card():
    with st.container(key="hero-progress"):
        st.markdown(f"**{user_key}님의 정착 현황**")
        day = _settlement_day()
        if progress_summary is None:
            _caption("창원 전입일을 입력하면 정착 단계와 할 일을 보여 드려요.")
            return
        _caption(
            (f"창원 정착 {day + 1}일째 · " if day is not None and day >= 0 else "")
            + f"{current_month}개월 차 · {current_group['theme']}"
        )
        st.progress(progress_summary["overall_completed"] / progress_summary["overall_total"])
        st.markdown(f"전체 할 일 {progress_summary['overall_completed']} / {progress_summary['overall_total']} 완료")
        remaining = [m["미션"] for m in current_group["missions"] if not completion_states.get(m["ID"])][:3]
        if remaining:
            # 세로 길이를 줄이려고 한 덩어리로 (10/3 이혜경)
            st.markdown("<p class='hero-lines'><b>이번 단계에 남은 할 일</b><br>"
                        + "<br>".join(f"○ {html.escape(name)}" for name in remaining) + "</p>", unsafe_allow_html=True)
        st.button("정착 일정 이어서 하기 →", key="home-continue", on_click=_go, args=(PAGE_JOURNEY,))


def _hero_example_card():
    with st.container(key="hero-example"):
        st.markdown("<p class='hero-lines'><b>이런 걸 함께 챙겨드려요</b><br>"
                    + "<br>".join(f"{mark} {html.escape(text)}" for mark, text in EXAMPLE_CHECKS) + "</p>",
                    unsafe_allow_html=True)
        _caption("예시 화면이에요. 조건을 입력하면 나의 진행 상황으로 바뀌어요.")


def render_home_page():
    # HERO: 화면 전체 폭 배경, 내용은 가운데 1200px
    with st.container(key="home-hero-band"):
        with st.container(key="home-hero-inner"):
            # 맨 위 한 줄: 작은 로고(왼쪽 끝) + 서비스 한 줄 소개(오른쪽)
            with st.container(key="home-topbar", horizontal=True, vertical_alignment="center",
                              horizontal_alignment="distribute"):
                st.image(str(LOGO_LIGHT_PATH), width=LOGO_WIDTH)
                st.markdown('<span class="top-pill">창원 전입 청년 · 첫 180일 정착 코디</span>', unsafe_allow_html=True)
            text_col, preview_col = st.columns([3, 2], gap="large", vertical_alignment="center")
            with text_col:
                st.markdown('<span class="hero-eyebrow">AI 정착 코디네이터 Agent</span>', unsafe_allow_html=True)
                with st.container(key="slogan"):
                    st.subheader(SLOGAN, anchor=False)
                with st.container(key="hero-intro"):
                    # 세 줄을 한 덩어리로(줄 간격만) — 아래 시작 버튼과는 간격으로 구분
                    st.markdown(
                        "<p class='hero-lines'><b>오이소창원</b>은 창원에 새로 전입한 청년의 초기 정착을 돕는 코디네이터 Agent입니다.<br>"
                        "창원에서의 첫 180일, 놓치기 쉬운 혜택과 할 일을 <b>오이소창원</b>이 함께 챙겨드려요.<br>"
                        "오이소창원과 180일간의 정착 여정을 함께 떠나볼까요?</p>",
                        unsafe_allow_html=True,
                    )
                with st.container(key="hero-cta", horizontal=True, wrap=True, vertical_alignment="center"):
                    st.button(
                        f"{CONDITION_LABEL}하고 시작하기 →" if not user_key else PROFILE_EDIT_LABEL,
                        key="show-profile",
                        type="primary",
                        on_click=_go,
                        args=(PAGE_PROFILE,),
                    )
                    if not user_key:
                        st.button(f"{DEFAULT_NICKNAME} 예시로 둘러보기", key="home-demo", type="tertiary", on_click=_start_demo)
                # 안내 문구는 주황 버튼 아래 (10/3 이혜경)
                with st.container(key="hero-cta-help"):
                    st.markdown(CTA_HELP_HTML, unsafe_allow_html=True)
                    # 신뢰 안내는 시작 안내 바로 아래 한 줄로 (10/4 이혜경: 하단에 홀로 있던 문구)
                    with st.container(key="hero-trust"):
                        _caption("🔒 실명·연락처는 받지 않아요 · 안내는 확인일 기준 공식 자료 · 최종 판단은 담당 기관")
            with preview_col:
                if user_key:
                    _hero_progress_card()
                else:
                    _hero_example_card()

    with st.container(key="home-body"):
        st.markdown('<p class="sec-title">오이소창원은 이렇게 일해요</p>', unsafe_allow_html=True)
        # 5단계 흐름: 같은 크기 상자 + 화살표(PC는 가로 →, 모바일은 세로 ↓)
        flow_html = '<span class="flow-arrow" aria-hidden="true">→</span>'.join(
            f'<div class="flow-box{AI_FLOW_CLASS if uses_ai else ""}"><b>{number}. {html.escape(title)}</b>'
            f'<span>{html.escape(text)}</span></div>'
            for number, (title, text, uses_ai) in enumerate(AGENT_FLOW, start=1)
        )
        with st.container(key="agent-flow"):
            st.markdown(f'<div class="flow-row">{flow_html}</div>', unsafe_allow_html=True)
        # 두 영역 사이 구분선 (10/4 이혜경)
        st.divider()
        st.markdown('<p class="sec-title">이 서비스가 하는 일</p>', unsafe_allow_html=True)
        columns = st.columns(4, gap="medium")
        for column, (target_page, title, text) in zip(columns, HOME_FEATURES):
            with column:
                with st.container(key=f"home-card-{target_page}"):
                    st.markdown(f"**{title}**")
                    _caption(text)
                    if user_key:
                        st.button("열기 →", key=FEATURE_KEYS[target_page], type="primary",
                                  on_click=_go, args=(target_page,), width="stretch")
                    else:
                        st.button("🔒 조건 입력 후 열려요", key=FEATURE_KEYS[target_page],
                                  disabled=True, width="stretch")

        # 설명과 버튼을 한 묶음으로, 잠금 안내는 버튼 아래 작은 글씨로 (10/3 실사용자 피드백)
        with st.container(key="home-ask-row"):
            st.markdown("**궁금한 게 있나요?** 오이소창원에게 한 문장으로 물어보세요.")
            # 누를 수 없는 버튼은 두지 않음(10/3 팀 자체 테스트 모바일 의견) — 조건 입력 전에는 잠금 안내만
            if user_key:
                st.button(f"{ASK_LABEL} →", key="show-ask", on_click=_go, args=(PAGE_ASK,))
            else:
                _caption("🔒 조건 입력 후 열려요")

        with st.expander("이용 참고사항 자세히 보기"):
            st.markdown(APP_INTRO)
            st.markdown("\n".join(f"- {note}" for note in USAGE_NOTES))
            st.markdown("- 창원시 행정·민원 문의: 창원시 콜센터 1899-1111")


# --- 나의 조건 입력 --------------------------------------------------------------
PROFILE_NEXT_STEPS = (
    (PAGE_POLICY, "show-policy", "내 맞춤 혜택 확인하기 →", "primary"),
    (PAGE_JOURNEY, "show-journey", "정착 일정 만들기", "secondary"),
    (PAGE_ASK, "show-ask", "오이소창원에게 바로 물어보기", "secondary"),
)
PROFILE_MORE_STEPS = (
    (PAGE_COMPLAINT, "show-complaint", BUTTON_3),
    (PAGE_DIALECT, "show-dialect", BUTTON_4),
)


def _profile_next_card():
    with st.container(key="profile-next"):
        if user_key:
            st.markdown(f"### {user_key}님, 준비됐어요.")
            _caption("다음에 할 일을 골라 주세요. 조건은 언제든 이 화면에서 바꿀 수 있어요.")
        else:
            st.markdown("### 닉네임을 입력하면 다음 단계가 열려요")
            _caption("닉네임만 있어도 시작할 수 있어요. 나이·전입일을 넣으면 혜택과 일정이 더 정확해져요.")
        with st.container(key="profile-next-main", horizontal=True, wrap=True):
            for target_page, key, label, button_type in PROFILE_NEXT_STEPS:
                st.button(label, key=key, type=button_type, disabled=not user_key,
                          on_click=_go, args=(target_page,))
        with st.container(key="profile-next-more", horizontal=True, wrap=True, vertical_alignment="center"):
            _caption("다른 기능:")
            for target_page, key, label in PROFILE_MORE_STEPS:
                st.button(label, key=key, type="tertiary", disabled=not user_key,
                          on_click=_go, args=(target_page,))


# 조건 입력 칸 설명: ‘?’를 눌러야 보이는 툴팁 대신 칸 바로 아래에 항상 보이게 (10/3 사용자 테스트 의견)
PROFILE_FIELD_HELP = {
    "nickname": "실명 대신 쓰는 이름이에요. 같은 닉네임으로 다시 들어오면 체크한 할 일이 이어져요.",
    "age": "만 나이예요. 청년 정책의 나이 조건(보통 만 19~39세)을 확인할 때 써요.",
    "move_in_date": "새 주소로 전입신고를 한 날이에요. 1~6개월 정착 일정과 혜택 신청 시기를 계산해요.",
    "home_district": "사는 구를 고르면 가까운 생활 정보를 먼저 보여 드려요.",
    "previous_residence_years": "왜 필요할까요? ‘창원시 기업노동자 전입지원금’은 창원으로 오기 전 다른 시·군·구에 "
    "1년 이상 주민등록을 두고 살았어야 받을 수 있어요. 이 조건을 확인하는 데만 써요.",
    "employment_status": "직장인 = 창원 회사·가게 근무, 자영업 = 창원에서 직접 사업,  \n"
    "학생 = 대학·대학원 재학, 기타 = 구직 중·쉬는 중 등  \n하는 일에 따라 받을 수 있는 혜택이 달라져요.",
    "vehicle": "차가 없으면 대중교통 혜택(K-패스)을 먼저 보여 주고, 장소 안내도 대중교통 기준으로 알려 드려요.",
}


def _field_help(field):
    _caption(PROFILE_FIELD_HELP[field])


def render_profile_page():
    _page_hero("profile", "먼저, 오이소창원이 알아야 할 조건을 알려주세요.",
               "정책과 정착 일정을 찾는 데 필요한 최소한의 조건만 사용해요. <b>실명과 연락처는 받지 않아요.</b>",
               eyebrow=CONDITION_LABEL)
    with st.container(key="profile-head", horizontal=True, wrap=True, vertical_alignment="bottom"):
        with st.container():
            _caption(
                "입력한 조건은 저장하지 않아요(정착 할 일 체크만 닉네임 기준으로 저장). 칸마다 아래에 쉬운 설명이 있어요."
            )
        with st.container(horizontal=True, wrap=True, horizontal_alignment="right", width="content"):
            st.button(
                f"예시 정보로 채우기 ({DEFAULT_NICKNAME})",
                key="fill-demo",
                type="secondary",
                on_click=_fill_profile,
                args=(DEMO_PROFILE,),
            )
            st.button(
                "입력 지우기",
                key="clear-profile",
                type="tertiary",
                on_click=_fill_profile,
                args=(PROFILE_DEFAULTS,),
            )
    left_inputs, right_inputs = st.columns(2, gap="large")
    with left_inputs:
        with st.container(key="profile-group-basic"):
            st.markdown("**기본 조건**")
            st.text_input("닉네임", key="nickname", placeholder="실명 대신 쓸 이름 (예: 창원새내기)", max_chars=20)
            _field_help("nickname")
            st.number_input("나이", min_value=19, max_value=100, key="age", placeholder="만 나이")
            _field_help("age")
            st.date_input("창원 전입일", key="move_in_date", format="YYYY/MM/DD")
            _field_help("move_in_date")
            district_col, town_col = st.columns(2, gap="small")
            with district_col:
                st.selectbox(
                    "사는 지역",
                    [DISTRICT_PLACEHOLDER, *HOME_DISTRICTS],
                    key="home_district",
                    on_change=_sync_activity_district,
                )
                _field_help("home_district")
            with town_col:
                st.text_input(
                    "동네 (선택)",
                    placeholder="예: 상남동",
                    max_chars=40,
                    key="neighborhood",
                )
    with right_inputs:
        with st.container(key="profile-group-life"):
            st.markdown("**생활 조건**")
            st.number_input(
                "창원 전입 전 타지역 거주기간(년)",
                min_value=0,
                max_value=50,
                key="previous_residence_years",
                placeholder="예: 2",
            )
            _field_help("previous_residence_years")
            st.radio(
                "지금 하는 일 (창원 기준)",
                EMPLOYMENT_OPTIONS,
                key="employment_status",
                horizontal=True,
            )
            _field_help("employment_status")
            st.radio(
                "차량 소지 여부",
                VEHICLE_OPTIONS,
                key="vehicle",
                horizontal=True,
            )
            _field_help("vehicle")
    _profile_next_card()


move_in_date = st.session_state["move_in_date"]
home_district = (
    st.session_state["home_district"]
    if st.session_state["home_district"] in HOME_DISTRICTS
    else None
)
neighborhood = st.session_state["neighborhood"] or ""

all_missions = personalize_missions(load_missions(), st.session_state["employment_status"])
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


# --- ② 받을 수 있는 지원 -----------------------------------------------------
def _current_profile():
    return {
        "nickname": nickname,
        "age": st.session_state["age"],
        "move_in_date": move_in_date,
        "home_district": home_district,
        "neighborhood": neighborhood.strip(),
        "previous_residence_years": st.session_state["previous_residence_years"],
        "job_type": st.session_state["employment_status"],
        "employed_in_changwon": (
            None
            if st.session_state["employment_status"] is None
            else st.session_state["employment_status"] in WORKING_OPTIONS
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
    "M1-5": "dialect", "M2-3": "dialect", "M4-4": "dialect", "M6-3": "dialect",
    "M5-4": "complaint",
}
POLICY_CARDS_SHOWN = 5
POLICY_NAMES = {p["ID"]: p["사업명"] for p in load_policies()}
# 정착 할 일 중 '지원'과 연결된 미션 → 관련 정책(지원 화면 카드)
MISSION_POLICY_IDS = {
    "M1-2": (),
    "M1-3": ("P21",),
    "M4-1": ("P20",),
    "M4-2": ("P19", "P11"),
    "M4-3": ("P09",),
    "M6-1": ("P01",),
    "M6-2": ("P03", "P04", "P05"),
    "M6-4": ("P06",),
}


LEVEL_STYLE = {
    "해당 가능": "level-ok",
    "조건부 해당 가능": "level-cond",
    "직접 확인": "level-check",
    "해당 없음": "level-no",
}
WHY_LABELS = {
    "해당 가능": "왜 먼저 보여드리나요?",
    "조건부 해당 가능": "확인할 조건",
    "직접 확인": "확인할 조건",
    "해당 없음": "왜 해당하지 않나요?",
}
LEVEL_HINTS = {
    "해당 가능": "지금 조건과 맞아요",
    "조건부 해당 가능": "시기·조건이 되면",
    "직접 확인": "담당 창구 확인",
    "해당 없음": "지금 조건과 달라요",
}


def _first_sentence(text, limit=70):
    first = re.split(r"(?<=[.다요])\s|\n| / ", text or "", maxsplit=1)[0].strip()
    return first if len(first) <= limit else first[: limit - 1] + "…"


def _policy_why(match):
    # 판정 로직이 만든 이유만 사용 (새로 지어내지 않음)
    reasons = [r for r in match["reasons"] if r]
    if match["priority"] and reasons:
        return reasons[0]
    return reasons[0] if reasons else match["message"]


def _policy_todo(match):
    if match["level"] == "해당 없음":
        return "지금 조건으로는 신청 대상이 아니에요. 조건이 바뀌면 다시 확인해 주세요."
    schedule = list(match["schedule"])
    if match["eligible_date"]:
        schedule.insert(0, f"계속 거주 6개월 기준일: {match['eligible_date']}")
    if schedule:
        return schedule[0]
    return _first_sentence(match["action"]) if match["action"] else "안내 링크에서 신청 조건과 기간을 확인해 주세요."


def _policy_card(match):
    style = LEVEL_STYLE[match["level"]]
    with st.container(border=True, key=f"policy-card-{match['id']}"):
        st.badge(match["level"], color={"level-ok": "green", "level-cond": "blue", "level-check": "orange", "level-no": "gray"}[style])
        _content_title(match["name"])
        _caption(match["message"])
        if match["support"]:
            st.markdown(f"**지원** · {_first_sentence(match['support'], 90)}")
        why_label = WHY_LABELS[match["level"]]
        st.markdown(
            f"<div class='pc-label'>{html.escape(why_label)}</div><div class='pc-body'>{html.escape(_policy_why(match))}</div>"
            f"<div class='pc-label'>지금 할 일</div><div class='pc-body'>{html.escape(_policy_todo(match))}</div>",
            unsafe_allow_html=True,
        )
        with st.container(horizontal=True, wrap=True, vertical_alignment="center"):
            st.link_button("공식 안내 보기" if match["level"] == "해당 없음" else "안내·신청 링크 열기", match["link"], key=f"policy-link-{match['id']}")
            with st.popover("자세히 보기"):
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
                _caption(" · ".join(v for v in (f"{match['checked']} 확인" if match["checked"] else "", match["status"]) if v))


def _policy_grid(matches, per_row=2):
    # PC는 카드 2개씩 가로로, 모바일은 한 줄에 하나
    for start in range(0, len(matches), per_row):
        columns = st.columns(per_row, gap="medium")
        for column, match in zip(columns, matches[start:start + per_row]):
            with column:
                _policy_card(match)


def render_policy_page():
    profile = _current_profile()
    matches = match_policies(profile)
    candidates = [m for m in matches if m["level"] != "해당 없음"]
    excluded = [m for m in matches if m["level"] == "해당 없음"]
    counts = {level: sum(1 for m in matches if m["level"] == level) for level in LEVELS}

    _page_hero("policy", FEATURE_1, "받을 수 있는 혜택 한눈에 보기 · 실제 판정 결과 기준", eyebrow="맞춤 혜택")
    st.markdown(f"### {nickname}님이 먼저 확인하면 좋은 혜택")
    with st.container(key="level-counts"):
        count_columns = st.columns(len(LEVELS), gap="small")
    for column, level in zip(count_columns, LEVELS):
        with column:
            with st.container(key=f"level-count-{LEVEL_STYLE[level]}"):
                st.markdown(
                    f"<div class='lvl-name'>{level}</div><div class='lvl-num'>{counts[level]}</div>"
                    f"<div class='lvl-hint'>{LEVEL_HINTS[level]}</div>",
                    unsafe_allow_html=True,
                )
    _caption(
        f"검증한 창원·청년 정책 {len(matches)}건과 입력한 조건을 규칙으로 비교했어요. "
        "받을 수 있다고 단정하지 않아요 — 최종 판단은 담당 기관에서 해요."
    )
    p01 = evaluate_p01(profile)
    if p01["missing_fields"]:
        missing_labels = [
            PROFILE_FIELD_LABELS.get(field, "추가 정보")
            for field in p01["missing_fields"]
        ]
        st.info("더 정확히 보려면 입력해 주세요: " + ", ".join(missing_labels))

    st.markdown("**오이소창원이 먼저 볼 혜택을 정리했어요.**")
    _policy_grid(candidates[:POLICY_CARDS_SHOWN])
    if len(candidates) > POLICY_CARDS_SHOWN:
        with st.expander(f"더 보기 · 다른 지원 {len(candidates) - POLICY_CARDS_SHOWN}개"):
            _policy_grid(candidates[POLICY_CARDS_SHOWN:])
    if excluded:
        with st.expander(f"해당 없음 {len(excluded)}개 · 이유 보기"):
            _policy_grid(excluded)

    if move_in_date is not None:
        st.markdown("**혜택 확인일·정착 일정 저장**")
        _save_buttons(datetime.now(ZoneInfo("Asia/Seoul")).date(), PAGE_POLICY)
        # 첫 화면에 있던 저장 안내를 여기로 옮겨 짧게 (10/4 이혜경)
        _caption(POLICY_SAVE_HELP)
    with st.container(horizontal=True, wrap=True, vertical_alignment="center"):
        st.link_button(
            "창원시 청년정책 전체 보기",
            CITY_YOUTH_POLICY_URL,
        )
        _caption("조건을 바꾸려면 ‘나의 조건 입력’에서 고쳐 주세요.")
    _next_feature_button(PAGE_JOURNEY, f"{BUTTON_2} →")


# --- ③ 정착 할 일 ------------------------------------------------------------
def _feature_2_header(current):
    with _page_hero(current, FEATURE_2, "전입일 기준 1~6개월 할 일과 창원 생활 정보를 한곳에서", eyebrow="정착 일정 · 생활 정보"):
        with st.container(key="feature2-tabs", horizontal=True, wrap=True):
            for target_page, label in FEATURE_2_TABS.items():
                st.button(
                    label,
                    key=f"tab-{target_page}",
                    type="primary" if current == target_page else "secondary",
                    on_click=_go,
                    args=(target_page,),
                )


APP_URL = "https://oisochangwon-4fuybothxlr78qnnaappqv.streamlit.app/"


def _export_files(today):
    """캘린더 파일·정착 리포트 바이트. 실명·연락처·닉네임은 넣지 않는다."""
    matches = match_policies(_current_profile())
    events = build_schedule_events(move_in_date, MILESTONE_LABELS, mission_groups, matches)
    notes = {
        mission["ID"]: st.session_state.get(
            f"mission-note:{user_key}:{mission['ID']}", saved_mission_notes.get(mission["ID"], "")
        )
        for mission in all_missions
    }
    profile = {
        "move_in_date": move_in_date.isoformat(),
        "job_type": st.session_state["employment_status"],
        "age": st.session_state["age"],
        "vehicle": st.session_state["vehicle"],
    }
    report = build_report_html(
        profile, _settlement_day(), progress_summary, mission_groups,
        completion_states, notes, matches, events,
    )
    counts = {kind: sum(1 for event in events if event["kind"] == kind) for kind in ("milestone", "missions", "policy")}
    return events, build_ics(events), report, counts


def _open_email_alert(where):
    st.session_state["alert_open"] = True
    st.session_state["email_scroll"] = True
    if where != PAGE_JOURNEY:
        _go(PAGE_JOURNEY)


def _save_buttons(today, where):
    """📅 캘린더에 저장 · 📄 정착 리포트 저장 · ✉️ 이메일 알림 신청 — 필요한 화면에 같은 버튼 줄."""
    events, ics, report, counts = _export_files(today)
    with st.container(key=f"save-row-{where}", horizontal=True, wrap=True):
        st.download_button(
            "📅 캘린더에 저장",
            data=ics,
            file_name="oisochangwon_schedule.ics",
            mime="text/calendar",
            key=f"download-ics-{where}",
            type="primary",
            on_click="ignore",
        )
        st.download_button(
            "📄 정착 리포트 저장",
            data=report,
            file_name=f"oisochangwon_report_{today.isoformat()}.html",
            mime="text/html",
            key=f"download-report-{where}",
            on_click="ignore",
        )
        st.button("✉️ 이메일 알림 신청", key=f"email-open-{where}", on_click=_open_email_alert, args=(where,))
    return events, counts


def _journey_tools(today):
    st.subheader("일정 저장·알림")
    with st.container(key="journey-tools"):
        events, counts = _save_buttons(today, PAGE_JOURNEY)
        # 긴 설명은 접어 두고 핵심 한 줄만 (10/3 UI 다듬기 — 내용은 그대로)
        _caption(
            f"📅 캘린더 파일에는 정착 일정 {counts['milestone']}개 · 월별 할 일 {counts['missions']}개 · "
            f"혜택 확인일 {counts['policy']}개가 들어가고, 하루 전 오전 9시에 알림이 떠요."
        )
        with st.popover("저장 방법 자세히 보기"):
            _caption(
                "캘린더 파일: 열면 휴대폰·PC 캘린더에 일정이 들어가요.  \n"
                "정착 리포트: 나의 조건·할 일 진행·다가오는 일정·맞는 혜택을 한 파일로 저장해요. "
                "브라우저에서 열어 인쇄하면 PDF로도 저장돼요. 파일은 내 기기에만 저장되고 실명·연락처는 들어가지 않아요.  \n"
                "휴대폰에서는 버튼을 누른 뒤 화면 위·아래의 다운로드 알림(또는 ‘내 파일 → 다운로드’)에서 파일을 눌러 "
                "캘린더 앱·브라우저로 열어요."
            )
        _email_alert_box(events, today)


def _email_alert_box(events, today):
    for key in ("alert_email", "alert_consent_privacy", "alert_consent_receive", "unsubscribe_email"):
        if st.session_state.pop(f"clear:{key}", False):
            st.session_state.pop(key, None)
    config = email_alerts.smtp_config(_setting)
    with st.container(key="email-alert"):
        message = st.session_state.pop("alert_message", None)
        unsubscribe_message = st.session_state.pop("unsubscribe_message", None)

        def show(msg):
            (st.success if msg[0] == "ok" else st.error)(msg[1])

        if not st.session_state.get("alert_open"):
            for msg in (message, unsubscribe_message):
                if msg:
                    show(msg)
            message = unsubscribe_message = None
        if st.session_state.pop("email_scroll", False):
            _scroll_into_view("email-alert")
        if not st.session_state.get("alert_open"):
            _caption("이메일 알림은 선택이에요. ‘✉️ 이메일 알림 신청’을 누르지 않으면 이메일을 묻거나 저장하지 않아요.")
            return
        with st.container(horizontal=True, vertical_alignment="center"):
            st.markdown("**✉️ 이메일 알림 신청 (선택)**")
            st.button("닫기", key="email-close", type="tertiary", on_click=lambda: st.session_state.update(alert_open=False))
        if config is None:
            st.info(
                "이메일 발송 설정이 아직 준비되지 않아 지금은 이메일을 받지 않아요. "
                "위 ‘📅 캘린더에 저장’으로 내 캘린더에서 알림을 받아 주세요."
            )
            return
        _caption(
            "신청하지 않으면 이메일을 받지 않아요. 신청하면 바로 전체 일정(캘린더 파일 첨부)을 보내 드리고, "
            "일정 하루 전에 알림 메일을 보내요. 메일은 앱 서버가 깨어 있을 때 보내져 늦어질 수 있어 "
            "정확한 알림은 캘린더 파일을 함께 쓰는 걸 권해요."
        )
        with st.form("email-alert-form", border=False):
            email = st.text_input("이메일 주소", key="alert_email", placeholder="example@email.com")
            # 신청 결과 안내는 이메일 주소 칸 바로 아래에 (10/3 이혜경)
            if message:
                show(message)
            st.markdown(email_alerts.PRIVACY_NOTICE)
            agree_privacy = st.checkbox("[필수] 개인정보 수집·이용에 동의해요", key="alert_consent_privacy")
            agree_receive = st.checkbox("[필수] 창원 정착 일정 알림 메일 수신에 동의해요", key="alert_consent_receive")
            submitted = st.form_submit_button("알림 신청하기", type="primary")
        if submitted:
            try:
                result = email_alerts.subscribe(email, events, agree_privacy, agree_receive)
            except email_alerts.AlertError as error:
                st.error(str(error))
            else:
                try:
                    email_alerts.send_message(
                        config,
                        email_alerts.build_welcome_message(
                            config, result["email"], result["alerts"], result["token"], build_ics(events), APP_URL
                        ),
                    )
                except Exception as error:
                    # 보내지 못한 이메일은 남기지 않는다
                    email_alerts.unsubscribe(token=result["token"])
                    print(f"[email_alerts] 환영 메일 발송 실패: {type(error).__name__}: {error}", flush=True)
                    reason = (
                        " (보내는 메일 계정 로그인 실패 — 관리자: Secrets의 앱 비밀번호 확인)"
                        if type(error).__name__ == "SMTPAuthenticationError"
                        else f" (오류: {error})" if isinstance(error, email_alerts.SendFailure)
                        else f" (오류 종류: {type(error).__name__})"
                    )
                    st.session_state["alert_message"] = (
                        "error",
                        "지금은 메일 서버에 연결되지 않아 신청을 취소했어요(이메일도 저장하지 않았어요). "
                        "일정 알림은 위의 ‘📅 캘린더에 저장’으로 받을 수 있어요 — 하루 전 오전 9시에 휴대폰·PC 캘린더 알림이 떠요."
                        + reason,
                    )
                else:
                    st.session_state["alert_message"] = (
                        "ok", f"신청했어요. 일정 {len(result['alerts'])}개를 알려 드릴게요. 받은 편지함을 확인해 주세요."
                    )
                for key in ("alert_email", "alert_consent_privacy", "alert_consent_receive"):
                    st.session_state[f"clear:{key}"] = True
                st.rerun()
        # 신청 버튼과 해지 칸이 붙어 헷갈리지 않게 구분선·간격 (10/3 이혜경)
        st.divider()
        with st.container(key="email-unsubscribe-box"):
            st.markdown("**알림 그만 받기**")
            _caption("이미 신청한 이메일의 알림을 끊고 이메일을 지울 때만 써요.")
            if unsubscribe_message:
                show(unsubscribe_message)
        with st.form("email-unsubscribe-form", border=False):
            unsubscribe_email = st.text_input("신청한 이메일 주소", key="unsubscribe_email")
            if st.form_submit_button("알림 해지·이메일 삭제"):
                try:
                    removed = email_alerts.unsubscribe(email=unsubscribe_email)
                except email_alerts.AlertError as error:
                    st.session_state["unsubscribe_message"] = ("error", str(error))
                else:
                    st.session_state["unsubscribe_message"] = (
                        "ok", "알림을 해지하고 이메일을 삭제했어요." if removed else "신청된 이메일이 없어요."
                    )
                st.session_state["clear:unsubscribe_email"] = True
                st.rerun()


def render_journey_page():
    _feature_2_header(PAGE_JOURNEY)
    if move_in_date is None:
        st.subheader("창원 정착 일정")
        st.info("정착 일정과 할 일을 만들려면 ‘나의 조건 입력’에서 창원 전입일을 입력해 주세요.")
        return
    settlement_plan = build_settlement_plan(move_in_date)

    # 지금 위치 요약 — 모두 실제 계산값(전입일·저장된 체크)만 사용
    today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    with st.container(key="journey-summary"):
        day = _settlement_day()
        st.markdown(
            f"### 창원 정착 {day + 1}일째" if day is not None and day >= 0 else "### 창원 전입 예정"
        )
        if progress_summary is not None:
            _caption(f"지금은 {current_month}개월 차 · {current_group['theme']}")
            stage_column, overall_column = st.columns(2, gap="large")
            with stage_column:
                st.markdown(f"**이번 단계** {progress_summary['stage_completed']} / {progress_summary['stage_total']} 완료")
                st.progress(progress_summary["stage_completed"] / progress_summary["stage_total"] if progress_summary["stage_total"] else 0.0)
            with overall_column:
                st.markdown(f"**전체 할 일** {progress_summary['overall_completed']} / {progress_summary['overall_total']} 완료")
                st.progress(progress_summary["overall_completed"] / progress_summary["overall_total"] if progress_summary["overall_total"] else 0.0)

    st.subheader("창원 정착 일정")

    milestones = settlement_plan["milestones"]
    next_index = next((i for i, m in enumerate(milestones) if date.fromisoformat(m["date"]) > today), None)
    milestone_columns = st.columns(len(milestones), gap="small")
    for index, (column, milestone) in enumerate(zip(milestone_columns, milestones)):
        label = MILESTONE_LABELS[milestone["day"]]
        state = "next" if index == next_index else ("done" if date.fromisoformat(milestone["date"]) <= today else "later")
        mark = {"done": "✓ 지남", "next": "● 다음", "later": "○ 예정"}[state]
        with column:
            with st.container(key=f"milestone-{milestone['day']}-{state}"):
                _caption(mark)
                st.markdown(f"**{label}**  \n{milestone['date']}")
    _caption(
        "마지막 일정과 계속 거주 6개월 기준일은 서로 다른 방식으로 계산되어 "
        "날짜가 다를 수 있어요."
    )
    _journey_tools(today)

    try:
        mission_resources = load_mission_resources()
    except (OSError, ValueError):
        mission_resources = {}
        st.info("할 일 관련 안내를 불러오지 못했어요. 할 일과 기록 저장은 계속 이용할 수 있어요.")

    st.subheader("이번에 할 일 · 1~6개월 정착 여정")
    _caption("모든 단계는 제목을 눌러 언제든 열어볼 수 있어요. 체크와 내 기록은 ‘이 단계 저장하기’를 눌러 저장해 주세요.")
    _caption(SAVE_HELP)

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
                _caption(
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
                _caption(f"완료 기준: {mission['완료 기준']}")
                resource = mission_resources.get(mission_id)
                feature_page = MISSION_FEATURE_PAGES.get(mission_id)
                if feature_page:
                    st.button(
                        f"{PAGE_LABELS[feature_page]} 열기",
                        key=f"to-feature-{mission_id}",
                        on_click=_go,
                        args=(feature_page,),
                    )
                if mission.get("_variant"):
                    resource = None  # 직장인 기준 공식 링크는 바뀐 할 일과 맞지 않으므로 숨김
                policy_ids = mission.get("_policy_ids", MISSION_POLICY_IDS.get(mission_id))
                if policy_ids is not None:
                    # 할 일은 '무엇을 할까'만 — 지원 내용·대상 여부는 지원 화면 카드로 연결
                    related = [POLICY_NAMES[pid] for pid in policy_ids if pid in POLICY_NAMES]
                    _caption(
                        f"지원 내용·대상 여부는 ‘{BUTTON_1}’에서 확인해요"
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
                _caption(f"마지막 저장: {max(stage_timestamps)} (한국시간)")
    _next_feature_button(PAGE_EXPLORE, f"{FEATURE_2_TABS[PAGE_EXPLORE]} →")


# --- ② 창원 생활 둘러보기 -------------------------------------------------------
EXPLORE_CARDS_SHOWN = 6
# 생활 정보 첫 화면에 먼저 보여 줄 장소(목록 맨 앞·‘자세히 볼 곳’ 첫 선택) — 2026 창원 K-POP 월드페스티벌 · 성산구 (10/4 이혜경)
FEATURED_ACTIVITY_ID = "A143"


def _select_activity(activity_id):
    st.session_state["activity_selection"] = activity_id
    st.session_state["explore_scroll"] = True


def _md_text(value):
    return MD_SPECIAL_RE.sub(r"\\\1", str(value or ""))


def _activity_card(activity, app_name, car_only=False):
    item = activity_view(activity, app_name)
    with st.container(border=True, key=f"activity-card-{activity['ID']}", height="stretch"):
        st.markdown(f"**{_md_text(item['name'])}**")
        _caption(f"{item['district']} · {item['category']}" + (" · 차량 권장" if car_only else ""))
        introduction = item.get("introduction")
        if isinstance(introduction, str) and introduction.strip():
            st.markdown(_md_text(introduction))
        schedule = (item["schedule"] or "").strip()
        if schedule:
            _caption("운영·일정: " + _md_text(schedule if len(schedule) <= 60 else schedule[:59] + "…"))
        with st.container(horizontal=True, wrap=True, vertical_alignment="center"):
            st.button("자세히 보기", key=f"activity-more-{activity['ID']}", on_click=_select_activity,
                      args=(activity["ID"],), type="tertiary")
            st.link_button("지도에서 보기", item["naver_map_url"])


def _activity_grid(activities, app_name, car_only=False, per_row=3):
    for start in range(0, len(activities), per_row):
        columns = st.columns(per_row, gap="medium")
        for column, activity in zip(columns, activities[start:start + per_row]):
            with column:
                _activity_card(activity, app_name, car_only)


def render_explore_page():
    _feature_2_header(PAGE_EXPLORE)
    st.subheader("이번 주말엔 창원을 조금 알아볼까요?")
    _caption("창원에서 해볼 것 — 동네와 관심 분야를 고르면 갈 만한 곳과 참여할 일을 보여 드려요.")

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
        no_car = st.session_state["vehicle"] == "없음"

        with st.container(key="explore-filters"):
            district_column, category_column, move_info_column = st.columns([1, 1, 1.2], gap="medium")
            with district_column:
                selected_district = st.selectbox(
                    "어느 지역에서 찾을까요?",
                    district_options,
                    key="activity_district",
                )
            with category_column:
                selected_category = st.selectbox(
                    "어떤 활동을 찾으세요?",
                    ["모든 분야", *activity_options["categories"]],
                    key="activity_category",
                )
            with move_info_column:
                st.markdown("**이동 방식**")
                if no_car:
                    _caption("차량 없음 — 대중교통으로 갈 수 있는 곳을 먼저 보여 드려요. 외곽은 ‘차로 가면 좋은 곳’으로 따로 모았어요.")
                elif st.session_state["vehicle"] == "있음":
                    _caption("차량 있음 — 모든 장소를 함께 보여 드려요.")
                else:
                    _caption("‘나의 조건 입력’에서 차량 여부를 고르면 이동 방식에 맞춰 보여 드려요.")

        filtered_activities = filter_activities(
            activities,
            district=(None if selected_district == "창원 전체" else selected_district),
            category=(None if selected_category == "모든 분야" else selected_category),
        )
        _caption(f"둘러볼 수 있는 활동 {len(filtered_activities)}개 · 카드의 ‘자세히 보기’를 누르면 아래에서 운영시간·이동 방법·지도를 볼 수 있어요.")
        if not filtered_activities:
            st.info("조건에 맞는 활동을 찾지 못했어요. 다른 지역이나 분야를 골라보세요.")

        app_name = st.context.url or "http://localhost:8501"
        car_only = [a for a in filtered_activities if a.get("이동 권장") == "차량 권장"] if no_car else []
        main_list = [a for a in filtered_activities if a not in car_only]
        main_list.sort(key=lambda a: a["ID"] != FEATURED_ACTIVITY_ID)  # 대표 장소를 맨 앞으로(나머지 순서 유지)
        _activity_grid(main_list[:EXPLORE_CARDS_SHOWN], app_name)
        if len(main_list) > EXPLORE_CARDS_SHOWN:
            with st.expander(f"더 보기 · {len(main_list) - EXPLORE_CARDS_SHOWN}곳"):
                _activity_grid(main_list[EXPLORE_CARDS_SHOWN:], app_name)
        if car_only:
            st.markdown("**차로 가면 좋은 곳** · 창원 외곽이라 시내버스로는 가기 어려워요")
            _activity_grid(car_only, app_name, car_only=True)
        elif no_car and filtered_activities:
            # 10/3 팀 자체 테스트(모바일 G-5): 목록이 안 보이는 이유를 알려 줌
            _caption("이 지역·분야에는 ‘차로 가면 좋은 곳’(외곽 차량 권장 장소)이 없어요. 지역을 ‘창원 전체’로 바꾸면 볼 수 있어요.")

        selected_activity_id = None
        if filtered_activities:
            st.divider()
            # 선택 목록은 화면 카드 순서(대중교통 목록 → 차로 가면 좋은 곳)와 같게
            activity_by_id = {activity["ID"]: activity for activity in [*main_list, *car_only]}
            if st.session_state.get("activity_selection") not in activity_by_id:
                # 필터를 바꿔 이전 선택이 목록에 없으면 첫 장소로 명시적으로 맞춤 — 선택창과 상세가 어긋나지 않게 (10/3 팀 자체 테스트 G-2)
                st.session_state["activity_selection"] = next(iter(activity_by_id))
            with st.container(key="explore-detail"):
                selected_activity_id = st.selectbox(
                    "자세히 볼 곳",
                    list(activity_by_id),
                    format_func=lambda activity_id: (
                        f"{activity_by_id[activity_id]['이름']} · "
                        f"{activity_by_id[activity_id]['생활권(구)']}"
                    ),
                    key="activity_selection",
                )

        if selected_activity_id:
            item = activity_view(activity_by_id[selected_activity_id], app_name)
            detail_column, move_column = st.columns([1.6, 1], gap="large")
            with detail_column:
                _content_title(item["name"])
                introduction = item.get("introduction")
                if isinstance(introduction, str) and introduction.strip():
                    st.text(introduction)
                _caption(f"{item['district']} · {item['category']}")
                _caption(f"관심 분야: {item['interests']}")
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
                _caption(f"{item['last_checked']} 기준으로 확인했어요.")
                _caption("방문 전 운영시간을 한 번 더 확인해 주세요.")

            with move_column:
                st.subheader("장소 안내")
                if item["official_url"]:
                    st.link_button(
                        item["official_link_label"],
                        item["official_url"],
                    )

                st.subheader("이동")
                selected_raw = activity_by_id[selected_activity_id]
                if selected_raw.get("이동 권장") == "차량 권장":
                    st.warning("창원 외곽이라 시내버스로 가기 어려워요. 차량으로 가는 것을 권장해요.")
                elif no_car:
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
            # 상세를 본 뒤 카드 목록으로 바로 돌아가기 (10/3 실사용자 테스트: 생활 정보 개선 필요 3명)
            st.button("↑ 장소 목록으로 돌아가기", key="explore-back-to-list", type="tertiary",
                      on_click=lambda: st.session_state.update(explore_scroll_top=True))
            if st.session_state.pop("explore_scroll", False):
                _scroll_into_view("explore-detail")
        if st.session_state.pop("explore_scroll_top", False):
            _scroll_into_view("explore-filters")
    except (OSError, ValueError):
        st.info(
            "창원 활동 정보를 불러오지 못했어요. "
            "지원 확인과 정착 할 일은 계속 이용할 수 있어요."
        )
    _next_feature_button(PAGE_COMPLAINT, f"{BUTTON_3} →")


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
def _llm_client(provider, api_key, base_url=None):
    return make_client(provider, api_key, base_url)


def _queue_question(text):
    st.session_state["ask_pending"] = text


def _ask_agent(question):
    provider, api_key, model = llm_settings()
    client = _llm_client(provider, api_key, _setting("LLM_BASE_URL")) if provider else None
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
        st.markdown(_answer_markdown(item["answer"]))
        badge = MODE_LABELS[item["mode"]]
        if item["mode"] == "llm":
            badge += f" · {item['model']}"
        badge += " · 검증 통과" if item["verified"] else " · 검증 필요"
        _caption(badge)
        error_step = next((step for step in item["steps"] if step["단계"] == "AI 연결 오류"), None)
        if error_step:
            _caption(f"AI가 답하지 못한 이유: {error_step['내용']} — ‘Agent 실행 기록 보기’의 ‘오류 상세’ 줄을 확인해 주세요.")
        inline_urls = {url for _, url in MD_LINK_RE.findall(item["answer"])}
        for link_index, (label, url) in enumerate(l for l in item.get("links", []) if l[1] not in inline_urls):
            st.link_button(label, url, key=f"{key_prefix}-link-{link_index}")
        with st.expander("Agent 실행 기록 보기"):
            for number, step in enumerate(item["steps"], start=1):
                st.text(f"{number}. [{step['단계']}] {step['내용']}")


MD_LINK_RE = re.compile(r"\[([^\]\n]+)\]\((https://[^)\s]+)\)")
MD_SPECIAL_RE = re.compile(r"([\\`*_{}\[\]()<>#+!|~])")


def _answer_markdown(text):
    """AI·규칙 답을 그대로 보여 주되, 검증된 https 링크([공식 안내](주소))만 클릭되는 링크로 바꾼다.
    나머지 글자는 서식으로 바뀌지 않게(예: 4~10월의 ~) 이스케이프한다."""
    parts, last = [], 0
    for match in MD_LINK_RE.finditer(text or ""):
        parts.append(MD_SPECIAL_RE.sub(r"\\\1", text[last:match.start()]))
        label = MD_SPECIAL_RE.sub(r"\\\1", match.group(1))
        parts.append("[" + label + "](" + match.group(2) + ")")
        last = match.end()
    parts.append(MD_SPECIAL_RE.sub(r"\\\1", (text or "")[last:]))
    return "".join(parts).replace("\n", "  \n")


def _scroll_into_view(key):
    # 새 답이 생기면 그 위치로 화면을 옮긴다(모바일에서 결과가 아래에 숨지 않게).
    st.session_state["scroll_count"] = st.session_state.get("scroll_count", 0) + 1
    components.html(
        "<script>"
        f"/* {st.session_state['scroll_count']} */"
        "setTimeout(() => {"
        f"const el = window.parent.document.querySelector('.st-key-{key}');"
        "if (el) { el.scrollIntoView({behavior: 'smooth', block: 'start'}); }"
        "}, 300);"
        "</script>",
        height=0,
    )


def _ai_status_caption():
    provider, _, model = llm_settings()
    if provider:
        _caption(f"AI 연결됨: {MODEL_LABELS.get(model, model)} · 검증된 자료로만 답해요.")
    else:
        _caption("AI 모델이 연결되지 않아 기본 안내(키워드 규칙)로 답해요.")


def render_ask_page():
    _page_hero("ask", ASK_LABEL, "혜택·정착 할 일·가볼 곳·지역말·불편 접수 창구를 한 문장으로 물어보세요.", eyebrow="코디네이터 Agent")
    provider, api_key, model = llm_settings()
    if provider:
        _caption(f"AI 연결됨: {MODEL_LABELS.get(model, model)} · 검증된 자료(정책·장소·지역말·접수 창구)로만 답해요.")
    else:
        _caption("AI 모델이 연결되지 않아 기본 안내(키워드 규칙)로 답해요.")
    _caption("실명·연락처 같은 개인정보는 입력하지 마세요. 질문은 답변을 만들기 위해 AI 모델로 전송돼요.")

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
        with st.container(key=f"ask-item-{index}"):
            _render_agent_item(item, f"ask-{index}")
    if question and history:
        _scroll_into_view(f"ask-item-{len(history) - 1}")
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


COMPLAINT_LEVEL_RE = re.compile(r"\[(긴급|위기|높음|보통|제안|마음 건강)\]")
COMPLAINT_BADGE_COLORS = {"긴급": "red", "위기": "red", "높음": "orange", "보통": "blue", "제안": "green", "마음 건강": "violet"}


def _complaint_level(result):
    match = COMPLAINT_LEVEL_RE.search(result.get("answer") or "")
    if match:
        return match.group(1)
    if result.get("mode") in ("emergency", "crisis"):
        return "긴급" if result["mode"] == "emergency" else "위기"
    return None


def render_complaint_page():
    _page_hero("complaint", FEATURE_3, "불편한 상황을 한 문장으로 적으면 긴급도를 판단해 알맞은 접수 창구를 알려 드려요.<br>"
               "민원을 대신 접수하거나 개인정보를 받지 않아요.", eyebrow="불편사항")
    input_column, result_column = st.columns([1, 1.25], gap="large")
    with input_column:
        with st.container(key="complaint-input"):
            _ai_status_caption()
            with st.form("complaint-form", clear_on_submit=True, border=False):
                text = st.text_input("어떤 불편이 있나요?", placeholder="예: 우리 동네 인도 블록이 깨져서 위험해요", max_chars=200)
                submitted = st.form_submit_button("접수 창구 찾기", type="primary")
            st.markdown("**예시로 해 보기**")
            with st.container(horizontal=True, wrap=True):
                for index, example in enumerate(COMPLAINT_EXAMPLES):
                    st.button(example, key=f"complaint-example-{index}", on_click=_queue_complaint, args=(example,))
            _caption("화재·사고 같은 긴급 상황은 기다리지 말고 바로 112·119에 신고하세요.")
    question = (text if submitted and text.strip() else None) or st.session_state.pop("complaint_pending", None)
    if question:
        st.session_state["complaint_result"] = _ask_agent(f"[불편사항 접수 안내] {question}")
        st.session_state["complaint_result"]["question"] = question
    with result_column:
        st.markdown("**안내 결과**")
        result = st.session_state.get("complaint_result")
        if result:
            with st.container(key="complaint-result"):
                level = _complaint_level(result)
                if level:
                    st.badge(f"{level} 단계", color=COMPLAINT_BADGE_COLORS[level])
                _render_agent_item(result, "complaint")
            if question:
                _scroll_into_view("complaint-result")
        else:
            _caption("상황을 적거나 예시를 누르면 여기에 결과가 나와요.")
    st.markdown("**단계별 접수 창구**")
    channels = load_complaint_channels()
    for row_start in range(0, len(channels), 3):
        columns = st.columns(3, gap="small")
        for column, item in zip(columns, channels[row_start:row_start + 3]):
            with column:
                with st.container(border=True, key=f"channel-{row_start}-{item['단계']}"):
                    st.badge(item["단계"], color=COMPLAINT_BADGE_COLORS.get(item["단계"], "gray"))
                    st.markdown(f"**{item['예시']}**")
                    _caption(item["안내"] + " 연락처: " + ", ".join(item["연락처"]))
    _next_feature_button(PAGE_DIALECT, f"{BUTTON_4} →")


# --- ④ 창원 지역말 번역 --------------------------------------------------------
def _queue_dialect(text):
    st.session_state["dialect_pending"] = text


DIALECT_EXT_COUNT = len(json.loads((Path(__file__).parent / "data" / "dialects_ext.json").read_text(encoding="utf-8"))["items"])


def render_dialect_page():
    _page_hero("dialect", FEATURE_4, "직장·식당·병원에서 들은 창원(경남) 말을 적으면 뜻과 쓰임을 알려 드려요.", eyebrow="지역말")
    dialects = load_dialects()
    demo = [d for d in dialects if d.get("시연 사용")][:6]
    _caption(
        f"핵심 {len(dialects)}개와 공식 출처(국립국어원 우리말샘 등) "
        f"확장 사전 {DIALECT_EXT_COUNT:,}개에서 찾아 ‘문헌 기준 뜻’으로 알려 드리고, 사전에 없는 말은 짐작하지 않아요."
    )
    input_column, result_column = st.columns([1, 1.25], gap="large")
    with input_column:
        with st.container(key="dialect-input"):
            _ai_status_caption()
            with st.form("dialect-form", clear_on_submit=True, border=False):
                text = st.text_input("들은 말", placeholder="예: 단디 해래이", max_chars=60)
                submitted = st.form_submit_button("뜻 찾기", type="primary")
            st.markdown("**예시로 해 보기**")
            with st.container(horizontal=True, wrap=True):
                for index, item in enumerate(demo):
                    st.button(item["표현"], key=f"dialect-example-{index}", on_click=_queue_dialect, args=(item["표현"],))
    expression = (text if submitted and text.strip() else None) or st.session_state.pop("dialect_pending", None)
    if expression:
        result = _ask_agent(f"창원 지역말 ‘{expression.strip()}’이(가) 무슨 뜻이에요?")
        result["question"] = expression.strip()
        st.session_state["dialect_result"] = result
    with result_column:
        st.markdown("**뜻 풀이**")
        if st.session_state.get("dialect_result"):
            with st.container(key="dialect-result"):
                _render_agent_item(st.session_state["dialect_result"], "dialect")
            if expression:
                _scroll_into_view("dialect-result")
        else:
            _caption("들은 말을 적거나 예시를 누르면 여기에 뜻이 나와요.")
    with st.expander(f"핵심 지역말 {len(dialects)}개 한눈에 보기"):
        for row_start in range(0, len(dialects), 3):
            columns = st.columns(3, gap="small")
            for column, item in zip(columns, dialects[row_start:row_start + 3]):
                with column:
                    st.markdown(f"**{item['표현']}**")
                    _caption(f"{item['표준어 뜻']} · {item.get('사용 상황') or ''}")
        _caption("출처: 우리말샘·국립국어원 온라인가나다 등(문헌 기준 뜻)")
    _next_feature_button(PAGE_ASK, f"{ASK_LABEL} →")


# --- 사이드바: 정착 진행상황 + 빠른 이동 (실제 상태값만 표시) ---------------------
def _settlement_day():
    if not isinstance(move_in_date, date):
        return None
    return (datetime.now(ZoneInfo("Asia/Seoul")).date() - move_in_date).days


def _eligible_count():
    if not user_key:
        return None
    return sum(1 for match in match_policies(_current_profile()) if match["level"] == "해당 가능")


def _nav_button(target_page, label):
    st.button(
        label,
        key=f"nav-{target_page}",
        type="primary" if page == target_page else "secondary",
        disabled=target_page not in (PAGE_HOME, PAGE_PROFILE) and not user_key,
        on_click=_go,
        args=(target_page,),
        width="stretch",
    )


def render_sidebar():
    with st.sidebar:
        if user_key:
            st.markdown(f"**{user_key}**")
        else:
            st.write("닉네임을 입력해 주세요")
        day = _settlement_day()
        if day is not None:
            _caption(f"창원 정착 {day + 1}일째" if day >= 0 else "창원 전입 예정")
        if home_district:
            _caption(
                f"{home_district} · {neighborhood.strip()}"
                if neighborhood.strip()
                else home_district
            )
        if st.session_state["vehicle"]:
            _caption(VEHICLE_SUMMARY[st.session_state["vehicle"]])
        if progress_summary is None:
            _caption("창원 전입일을 입력하면 정착 단계와 진행률을 보여 드려요.")
        else:
            st.progress(
                progress_summary["overall_completed"] / progress_summary["overall_total"]
                if progress_summary["overall_total"]
                else 0.0
            )
            st.markdown(
                f"전체 진행: {progress_summary['overall_completed']} / "
                f"{progress_summary['overall_total']} 완료"
            )
            _caption(f"지금은 창원 생활 {current_month}개월 차예요 · {current_group['theme']}")

        _nav_button(PAGE_HOME, "홈")
        _caption("정착 코스")
        condition_done = bool(user_key and move_in_date)
        _nav_button(PAGE_PROFILE, f"조건 입력 · {'완료' if condition_done else '필요'}")
        eligible = _eligible_count()
        _nav_button(PAGE_POLICY, f"맞춤 혜택 · 해당 가능 {eligible}건" if eligible is not None else "맞춤 혜택")
        if progress_summary is not None:
            _nav_button(
                PAGE_JOURNEY,
                f"정착 일정 · 이번 단계 {progress_summary['stage_completed']}/{progress_summary['stage_total']}",
            )
        else:
            _nav_button(PAGE_JOURNEY, "정착 일정")
        _nav_button(PAGE_EXPLORE, "생활 정보")
        _caption("도움받기")
        _nav_button(PAGE_COMPLAINT, "불편사항")
        _nav_button(PAGE_DIALECT, "지역말")
        st.divider()
        _nav_button(PAGE_ASK, ASK_LABEL)
        if not user_key:
            _caption("🔒 조건 입력 후 열려요")
        if progress_summary is not None:
            _caption(
                f"현재 단계: {progress_summary['stage_completed']} / "
                f"{progress_summary['stage_total']} 완료"
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
                _caption(f"저장한 단계: {MONTH_LABELS[saved_month]}")
            formatted_saved_at = format_korea_timestamp(last_saved_at)
            if formatted_saved_at:
                _caption(f"마지막 저장: {formatted_saved_at} (한국시간)")


PAGE_RENDERERS = {
    PAGE_COMPLAINT: render_complaint_page,
    PAGE_DIALECT: render_dialect_page,
    PAGE_ASK: render_ask_page,
    PAGE_HOME: render_home_page,
    PAGE_PROFILE: render_profile_page,
    PAGE_POLICY: render_policy_page,
    PAGE_JOURNEY: render_journey_page,
    PAGE_EXPLORE: render_explore_page,
}
# 화면을 바꾸면 이전 화면을 통째로 지우고 새 화면만 그린다(이전 화면이 아래에 남지 않게).
@st.cache_resource(show_spinner=False)
def _alert_runner_state():
    return {"last": None}


def _run_due_alerts():
    """상시 스케줄러가 없으므로 앱이 실행될 때 한 시간에 한 번만 보낼 날이 된 알림을 보낸다."""
    config = email_alerts.smtp_config(_setting)
    if config is None:
        return
    state = _alert_runner_state()
    hour = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y%m%d%H")
    if state["last"] == hour:
        return
    state["last"] = hour
    import threading

    def _work():
        try:
            email_alerts.send_due_alerts(config, app_url=APP_URL)
        except Exception:
            pass

    threading.Thread(target=_work, daemon=True).start()


_unsubscribe_token = st.query_params.get("unsubscribe")
if _unsubscribe_token:
    removed = email_alerts.unsubscribe(token=_unsubscribe_token)
    st.query_params.clear()
    st.session_state["unsubscribe_notice"] = (
        "이메일 알림을 해지하고 이메일 주소를 삭제했어요." if removed else "이미 해지되었거나 신청 내역이 없어요."
    )
if st.session_state.get("unsubscribe_notice"):
    st.success(st.session_state.pop("unsubscribe_notice"))
_run_due_alerts()

if page != PAGE_HOME:
    # 세부 화면은 연한 배경 위에 흰 카드가 떠 보이게 (10/4 이혜경: 너무 하얗고 지루함)
    st.html("<style>.stApp, [data-testid='stMain'] {background: linear-gradient(180deg, #EEF3FA 0%, #F6F8FC 40%, #F8FAFD 100%) !important;}</style>")
    # 작은 로고는 스타일(배경 그림)로 넣어 화면 글자에 섞이지 않게
    st.html(f"<style>span.page-hero-logo {{background-image: url('{_logo_light_data_uri()}');}}</style>")
page_root = st.empty()
with page_root.container(key=f"page-{page}"):
    PAGE_RENDERERS.get(page, render_home_page)()

render_sidebar()
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
