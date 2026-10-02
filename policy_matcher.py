"""정책 23건(policies_mvp.json)을 사용자 프로필과 비교해 4단계로 판정한다.

단계: 해당 가능 / 조건부 해당 가능 / 직접 확인 / 해당 없음
- '받을 수 있다'고 단정하지 않는다. 최종 판단은 담당 기관.
- P01(기업노동자 전입지원금)은 기존 결정론 엔진(policy_engine.evaluate_p01)을 그대로 쓴다.
- 일정은 planner_rule로 계산하고, 전입 후 180일 밖이면 '180일 이후'로 표시한다.
"""

import json
import re
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta

from policy_engine import evaluate_p01

POLICIES_PATH = Path(__file__).resolve().parent / "data" / "policies_mvp.json"
YOUTH_PLATFORM_URL = "https://www.changwon.go.kr/youth/05085/05105/05105.web"
LEVELS = ("해당 가능", "조건부 해당 가능", "직접 확인", "해당 없음")
LEVEL_MESSAGES = {
    "해당 가능": "지금 조건으로 해당 가능해요.",
    "조건부 해당 가능": "조건을 갖추거나 모집 시기가 되면 해당 가능해요.",
    "직접 확인": "입력한 정보만으로는 판단하기 어려워요. 담당 창구에서 직접 확인해 주세요.",
    "해당 없음": "현재 조건으로는 해당하지 않아요.",
}
P01_MESSAGES = {
    "eligible_now": ("해당 가능", "현재 신청할 수 있어요."),
    "eligible_later": ("조건부 해당 가능", "조금 뒤 신청할 수 있어요."),
    "needs_info": ("직접 확인", "정보를 조금 더 입력해 주세요."),
    "not_eligible": ("해당 없음", "현재 조건으로는 신청 대상이 아니에요."),
}
STATUS_LABELS = {
    "open": "모집 중",
    "always": "상시",
    "planned": "모집 예정",
    "closed": "2026 모집 마감 — 다음 공고 확인",
    "unknown": "모집 일정 확인 필요",
}
# 추가로 확인해야 하는 조건이 있는 정책(소득·전세·여성·중소기업·회사 참여 등)
EXTRA_CONDITION_WORDS = ("소득", "전세", "여성", "중소기업", "참여 기업", "회사 참여", "3개월", "부모와 별도", "채용 전", "정규직")


@lru_cache(maxsize=None)
def load_policies():
    return json.loads(POLICIES_PATH.read_text(encoding="utf-8"))["items"]


def _text(value):
    if value in (None, "None"):
        return ""
    return re.sub(r"\[서비스 기획 아이디어\]\s*", "", str(value)).strip()


def _age_limit(value):
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _clean_url(value):
    match = re.search(r"https://\S+", value or "")
    return match.group(0).rstrip(")") if match else None


def policy_link(policy):
    return (
        policy.get("link")
        or _clean_url(policy.get("창원청년정보플랫폼 링크"))
        or _clean_url(policy.get("공식 URL (원문 직접 확인)"))
        or YOUTH_PLATFORM_URL
    )


def _fmt(day):
    return f"{day.year}년 {day.month}월 {day.day}일"


def schedule_lines(policy, move_in_date):
    """planner_rule을 사람이 읽는 일정 문장으로 바꾼다."""
    rule = policy.get("planner_rule") or {}
    window_end = move_in_date + timedelta(days=179) if move_in_date else None

    def tag(day):
        if window_end and day > window_end:
            return f"{_fmt(day)} (180일 이후)"
        return _fmt(day)

    kind = rule.get("type")
    if kind == "after_move_in" and move_in_date:
        return [f"{tag(move_in_date + relativedelta(months=rule['months']))}: {rule['label']}"]
    if kind == "notice_check":
        return [f"{tag(date.fromisoformat(rule['date']))}: {rule['label']}"]
    if kind == "fixed_dates":
        return [f"{tag(date.fromisoformat(e['date']))}: {e['label']}" for e in rule.get("events", [])]
    if kind == "on_event":
        return [f"{rule.get('event', '해당 시점')}: {rule['label']}"]
    if kind == "immediate":
        return [f"지금 바로: {rule['label']}"]
    if kind == "after_hire":
        months = "·".join(str(m) for m in rule.get("months", []))
        return [f"입사 후 {months}개월 차: {rule['label']}"]
    period = _text(policy.get("신청 기간(2026)"))
    return [f"신청 기간(2026): {period}"] if period else []


def _employment_rule(text):
    if text.startswith("무관"):
        return None
    if "미취업" in text or "구직" in text:
        return "unemployed"
    if any(word in text for word in ("재직", "근로", "일하는", "취업")):
        return "employed"
    return None


def evaluate_policy(policy, profile, today=None):
    today = today or datetime.now(ZoneInfo("Asia/Seoul")).date()
    profile = profile or {}
    age = profile.get("age")
    employed = profile.get("employed_in_changwon")
    move_in_date = profile.get("move_in_date")
    vehicle = profile.get("vehicle")
    reasons = []

    if policy["ID"] == "P01":
        p01 = evaluate_p01(profile)
        level, message = P01_MESSAGES[p01["status"]]
        reasons.append(p01["reason"])
        result = _result(policy, level, message, reasons, move_in_date)
        result["name"] = p01["policy_name"]
        result["eligible_date"] = p01["eligible_date"]
        return result

    unknown = []
    # 1) 연령
    low, high = _age_limit(policy.get("최소 연령")), _age_limit(policy.get("최대 연령"))
    if low is not None or high is not None:
        range_text = f"만 {low or ''}~{high or ''}세"
        if age is None:
            unknown.append(f"나이({range_text})")
        elif (low is not None and age < low) or (high is not None and age > high):
            return _result(policy, "해당 없음", LEVEL_MESSAGES["해당 없음"], [f"연령 조건 {range_text}에 해당하지 않아요."], move_in_date)
        else:
            reasons.append(f"연령 조건 {range_text} 충족")
    # 2) 취업 상태
    job_text = _text(policy.get("취업 상태"))
    rule = _employment_rule(job_text)
    job_type = profile.get("job_type")
    if rule == "employed" and job_type == "자영업":
        # 자영업은 '재직·근로' 대상 사업마다 인정 여부가 달라 기관 확인이 필요
        unknown.append(f"취업 상태({job_text}) — 자영업 인정 여부")
    elif rule == "unemployed" and job_type == "학생":
        reasons.append(f"취업 조건({job_text}) — 재학생은 제외될 수 있어요")
        unknown.append("재학생 참여 가능 여부")
    elif rule:
        if employed is None:
            unknown.append(f"취업 상태({job_text})")
        elif rule == "unemployed" and employed:
            return _result(policy, "해당 없음", LEVEL_MESSAGES["해당 없음"], [f"{job_text} 대상이라 재직 중에는 해당하지 않아요."], move_in_date)
        elif rule == "employed" and not employed:
            return _result(policy, "해당 없음", LEVEL_MESSAGES["해당 없음"], [f"{job_text} 대상이에요."], move_in_date)
        else:
            reasons.append(f"취업 조건({job_text}) 충족")
    # 3) 거주 요건 — 'N년 이상 거주', '2025.7.1 이후 계속 거주'
    residence = _text(policy.get("거주 요건"))
    years = re.search(r"창원시?\s*(\d+)년 이상 거주", residence)
    since = re.search(r"(\d{4})\.(\d{1,2})\.(\d{1,2}) 이후 계속 거주", residence)
    conditional = []
    if since and move_in_date and move_in_date > date(*map(int, since.groups())):
        return _result(policy, "해당 없음", LEVEL_MESSAGES["해당 없음"], [f"거주 요건({residence})을 2026년 공고 기준으로 충족하지 못해요."], move_in_date)
    if years:
        if move_in_date is None:
            unknown.append(f"거주 기간({residence})")
        else:
            ready = move_in_date + relativedelta(years=int(years.group(1)))
            if ready > today:
                conditional.append(f"창원 거주 {years.group(1)}년이 되는 {_fmt(ready)} 이후 조건 충족")
    # 4) 추가 조건·모집 상태
    extra = " ".join(_text(policy.get(k)) for k in ("대상 요약", "기타 조건", "취업 상태", "거주 요건"))
    extra_words = [w for w in EXTRA_CONDITION_WORDS if w in extra]
    if extra_words:
        conditional.append("추가 조건 확인 필요: " + ", ".join(extra_words))
    status = policy.get("status_code")
    if status in ("closed", "planned", "unknown"):
        conditional.append(STATUS_LABELS[status])

    if unknown:
        level = "직접 확인"
        reasons.append("입력이 필요한 정보: " + ", ".join(unknown))
    elif conditional:
        level = "조건부 해당 가능"
        reasons.extend(conditional)
    else:
        level = "해당 가능"
    result = _result(policy, level, LEVEL_MESSAGES[level], reasons, move_in_date)
    if policy["ID"] == "P21" and vehicle == "없음":
        result["priority"] = True
        result["reasons"].insert(0, "차량이 없어 대중교통비 환급 혜택을 먼저 보여 드려요.")
    return result


def _result(policy, level, message, reasons, move_in_date):
    return {
        "id": policy["ID"],
        "name": policy["사업명"],
        "category": policy.get("분야"),
        "level": level,
        "message": message,
        "reasons": reasons,
        "support": _text(policy.get("지원 내용")),
        "how_to_apply": _text(policy.get("신청 방법")),
        "status": STATUS_LABELS.get(policy.get("status_code"), ""),
        "schedule": schedule_lines(policy, move_in_date),
        "link": policy_link(policy),
        "action": _text(policy.get("신청 연계 안내")),
        "checked": policy.get("최종 확인일"),
        "core": policy.get("MVP 사용") == "핵심(시연)",
        "priority": False,
        "eligible_date": None,
    }


def match_policies(profile, today=None):
    results = [evaluate_policy(p, profile, today) for p in load_policies()]
    order = {level: index for index, level in enumerate(LEVELS)}
    results.sort(key=lambda r: (order[r["level"]], not r["priority"], not r["core"], r["id"]))
    return results
