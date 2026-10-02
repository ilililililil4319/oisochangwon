"""오이소창원 AI Agent — 한 문장 질문을 이해하고 검증 DB 도구를 골라 답한다.

흐름: 안전 확인(긴급·위기) → LLM이 도구 선택·호출(최대 4회) → 답변 검증(연락처·링크가
도구 결과에 있는지) → 실패 시 1회 재작성 → 그래도 실패하거나 LLM을 못 쓰면 규칙 기반 안내.
모든 단계는 steps(실행 기록)에 남긴다.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path

from dateutil.relativedelta import relativedelta

DATA_DIR = Path(__file__).resolve().parent / "data"
CALL_CENTER = "창원시 콜센터 1899-1111"
YOUTH_PLATFORM_URL = "https://www.changwon.go.kr/youth/05085/05105/05105.web"
DEFAULT_MODELS = {
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-4.1-mini",
}
MODEL_LABELS = {
    "claude-haiku-4-5-20251001": "Claude Haiku 4.5",
    "gpt-4.1-mini": "GPT-4.1 mini",
}
MAX_TOOL_ROUNDS = 4
# 도구 결과가 아니어도 답에 쓸 수 있는 공용 연락처·링크(팀 확인값)
ALWAYS_ALLOWED = {"112", "119", "109", "1899-1111", "055-286-1008", "055-225-2074", YOUTH_PLATFORM_URL}

EMERGENCY_WORDS = ("불이 났", "불났", "화재", "연기가", "교통사고", "사고가 났", "사고 났", "다쳤", "피가 나", "쓰러졌",
                   "위협", "칼을", "폭행", "누가 따라", "가스 냄새", "가스냄새")
CRISIS_WORDS = ("죽고 싶", "죽고싶", "자살", "살기 싫", "살기싫", "사라지고 싶", "자해")

SYSTEM_PROMPT = """너는 '오이소창원'의 정착 코디네이터 Agent야. 창원에 새로 전입한 청년을 돕는다.
규칙:
1. 답은 반드시 도구(tool) 결과에 있는 내용으로만 한다. 정책명·금액·기간·조건·연락처·링크는 도구 결과의 값을 그대로 쓰고 추측하지 않는다.
2. 도구 결과에 없으면 "확인된 정보에는 없어요"라고 말하고 창원시 콜센터 1899-1111 또는 창원청년정보플랫폼(https://www.changwon.go.kr/youth/05085/05105/05105.web)을 안내한다.
3. 지원 대상 여부는 단정하지 않는다. '해당 가능 / 조건부 해당 가능 / 직접 확인 필요' 같은 표현을 쓴다.
4. 지역말이 사전(lookup_dialect)에 없으면 뜻을 말하되 맨 앞에 "[AI 추정 - 사람 검수 필요]"를 붙인다. 사전에 있으면 '문헌 기준 뜻'이라고 밝힌다.
5. 불편·민원은 find_complaint_channel로 단계(긴급·높음·보통·제안·마음 건강)를 골라 창구를 안내한다. 민원 대리 제출·제안서 작성은 하지 않는다.
6. 외로움·우울 같은 마음 건강 이야기는 진단하지 않고 공감 한 문장 후 상담 창구를 안내한다.
7. 의학·법률 판단, 창원 정착과 무관한 질문(주식·숙제 등)은 정중히 거절하고 할 수 있는 일(지원·할 일·장소·지역말·불편 접수)을 알려 준다.
8. 카페·식당 등 상업 시설은 "특정 업체 홍보 아님, 방문 전 운영시간 확인"을 덧붙인다.
9. 쉬운 한국어로 5~8문장 이내, 필요하면 짧은 목록. 어려운 용어는 풀어 쓴다(예: 전입일 = 새 주소로 전입신고를 한 날).
10. 사용자 정보가 필요하면 get_my_situation을 먼저 호출한다.
11. 사용자가 차량이 '없음'이면 장소·이동 안내는 대중교통·자전거 기준으로 하고, 교통 혜택(K-패스)을 함께 알려 준다."""

TOOLS = [
    {
        "name": "get_my_situation",
        "description": "사용자가 입력한 프로필(나이·전입일·사는 구·전입 전 거주기간·재직 여부·차량)과 전입 경과, 기업노동자 전입지원금(P01) 규칙 판정 결과, 지금 단계의 정착 할 일을 돌려준다. '나', '내가 받을 수 있는' 같은 개인 맞춤 질문에 먼저 쓴다.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "search_policies",
        "description": "팀이 검증한 창원·청년 정책 DB(23건)에서 키워드로 정책을 찾는다. 예: 월세, 교통, 통장, 적금, 전입, 취업, 자격증, 운동.",
        "input_schema": {
            "type": "object",
            "properties": {"keyword": {"type": "string", "description": "찾을 단어(한두 단어). 비우면 핵심 정책 목록"}},
        },
    },
    {
        "name": "search_activities",
        "description": "팀이 검증한 창원 지역활동·장소 DB(60곳)에서 찾는다. 카페·먹거리·야경·산책·행사·축제·문화생활·쇼핑·의료·반려동물·운동 등.",
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "관심사 단어(예: 카페, 야경, 축제, 반려견)"},
                "district": {"type": "string", "description": "의창구·성산구·마산합포구·마산회원구·진해구 중 하나(선택)"},
                "indoor_only": {"type": "boolean", "description": "실내 장소만(비 오는 날·실내로 바꿔 달라고 할 때)"},
            },
        },
    },
    {
        "name": "lookup_dialect",
        "description": "창원(경남) 지역말 핵심 30개 사전에서 표현의 뜻을 찾는다.",
        "input_schema": {
            "type": "object",
            "properties": {"expression": {"type": "string", "description": "뜻이 궁금한 지역말 표현"}},
            "required": ["expression"],
        },
    },
    {
        "name": "find_complaint_channel",
        "description": "불편·민원·위험·제안·마음 건강 상황의 단계별 접수 창구와 연락처를 돌려준다.",
        "input_schema": {
            "type": "object",
            "properties": {"level": {"type": "string", "enum": ["긴급", "높음", "보통", "제안", "마음 건강", "위기"]}},
            "required": ["level"],
        },
    },
]


# --- 데이터 ------------------------------------------------------------------
@lru_cache(maxsize=None)
def _items(file_name):
    return json.loads((DATA_DIR / file_name).read_text(encoding="utf-8"))["items"]


def _clean_url(value):
    if not isinstance(value, str):
        return None
    match = re.search(r"https://\S+", value)
    return match.group(0).rstrip(")") if match else None


def _clean_text(value):
    if value in (None, "None"):
        return ""
    return re.sub(r"\[서비스 기획 아이디어\]\s*", "", str(value)).strip()


def _score(text, keyword):
    words = [w for w in re.split(r"[\s,·/]+", keyword or "") if w]
    return sum(text.count(w) for w in words)


# --- 도구 ---------------------------------------------------------------------
def search_policies(keyword=""):
    policies = _items("policies_mvp.json")
    if keyword:
        scored = []
        for policy in policies:
            text = " ".join(str(policy.get(k, "")) for k in ("사업명", "분야", "대상 요약", "지원 내용", "취업 상태"))
            score = _score(text, keyword)
            if score:
                scored.append((score, policy))
        picked = [p for _, p in sorted(scored, key=lambda pair: -pair[0])][:5]
    else:
        picked = [p for p in policies if p.get("MVP 사용") == "핵심(시연)"][:6]
    return {
        "count": len(picked),
        "policies": [
            {
                "ID": p["ID"],
                "사업명": p["사업명"],
                "분야": p.get("분야"),
                "대상 요약": _clean_text(p.get("대상 요약")),
                "지원 내용": _clean_text(p.get("지원 내용")),
                "신청 방법": _clean_text(p.get("신청 방법")),
                "상태": _clean_text(p.get("상태(9/30 기준)")),
                "대표 사용자(코디2026) 해당": _clean_text(p.get("대표 사용자 해당")),
                "신청 연계 안내": _clean_text(p.get("신청 연계 안내")),
                "링크": p.get("link") or _clean_url(p.get("창원청년정보플랫폼 링크")) or _clean_url(p.get("공식 URL (원문 직접 확인)")),
                "최종 확인일": p.get("최종 확인일"),
            }
            for p in picked
        ],
    }


def search_activities(keyword="", district="", indoor_only=False):
    activities = _items("activities_mvp.json")
    results = []
    for activity in activities:
        if district and activity.get("생활권(구)") != district:
            continue
        if indoor_only and activity.get("실내·실외") != "실내":
            continue
        text = " ".join(str(activity.get(k, "")) for k in ("이름", "관심사 태그", "MVP 그룹", "대분류", "유형(행사/모임/기관/공간)"))
        score = _score(text, keyword) if keyword else 1
        if score:
            results.append((score, activity))
    picked = [a for _, a in sorted(results, key=lambda pair: -pair[0])][:5]
    return {
        "count": len(picked),
        "note": "특정 업체 홍보 아님. 방문 전 운영시간을 확인하세요.",
        "activities": [
            {
                "ID": a["ID"],
                "이름": a["이름"],
                "구": a.get("생활권(구)"),
                "분야": a.get("MVP 그룹"),
                "실내·실외": a.get("실내·실외"),
                "일정·운영시간": a.get("일정·운영시간"),
                "대중교통": a.get("대중교통 접근(검수)"),
                "링크": _clean_url(a.get("공식 URL")),
                "최종 확인일": a.get("최종 확인일"),
            }
            for a in picked
        ],
    }


def _normalize(text):
    return re.sub(r"[\s'\"‘’“”?？!.,~]", "", text or "")


def lookup_dialect(expression):
    target = _normalize(expression)
    for item in _items("dialects_core30.json"):
        for candidate in (item.get("표현"), item.get("DB 표제어")):
            norm = _normalize(candidate)
            if norm and (norm in target or (len(target) >= 2 and target in norm)):
                return {
                    "found": True,
                    "표현": item["표현"],
                    "표준어 뜻": item["표준어 뜻"],
                    "사용 상황": item.get("사용 상황"),
                    "표시": "문헌 기준 뜻(토박이 검수 생략)",
                    "출처": item.get("출처"),
                }
    return {"found": False, "message": "지역말 핵심 30개 사전에 없는 표현입니다."}


def find_complaint_channel(level):
    for item in _items("complaint_channels.json"):
        if item["단계"] == level:
            return dict(item)
    return {"found": False, "message": f"'{level}' 단계가 없습니다. {CALL_CENTER}로 문의하세요."}


def get_my_situation(profile):
    from mission_manager import group_missions_by_month, load_missions
    from policy_engine import evaluate_p01
    from progress_manager import current_settlement_month

    profile = profile or {}
    move_in_date = profile.get("move_in_date")
    situation = {
        "나이": profile.get("age"),
        "전입일": move_in_date.isoformat() if isinstance(move_in_date, date) else None,
        "사는 구": profile.get("home_district"),
        "전입 전 타지역 거주기간(년)": profile.get("previous_residence_years"),
        "창원 사업장 재직": profile.get("employed_in_changwon"),
        "차량": profile.get("vehicle"),
    }
    p01 = evaluate_p01(profile)
    situation["기업노동자 전입지원금 판정"] = {
        "결과": {"eligible_now": "지금 신청 가능", "eligible_later": "조건부 해당 가능(나중에 신청)",
                 "needs_info": "정보 부족", "not_eligible": "현재 조건으로는 해당 없음"}[p01["status"]],
        "이유": p01["reason"],
        "신청 가능 예정일": p01["eligible_date"],
    }
    if isinstance(move_in_date, date):
        month = current_settlement_month(move_in_date)
        group = next(g for g in group_missions_by_month(load_missions()) if g["month"] == month)
        situation["정착 단계"] = f"{month}개월 차 · {group['theme']}"
        situation["이번 단계 할 일"] = [m["미션"] for m in group["missions"]]
        situation["180일 범위"] = f"{move_in_date.isoformat()} ~ {(move_in_date + relativedelta(days=179)).isoformat()}"
    else:
        situation["안내"] = "전입일이 없어 정착 단계를 계산하지 못했습니다. '내 정보'에서 전입일을 입력하도록 안내하세요."
    return situation


def run_tool(name, args, profile=None):
    args = args or {}
    if name == "get_my_situation":
        return get_my_situation(profile)
    if name == "search_policies":
        return search_policies(args.get("keyword", ""))
    if name == "search_activities":
        return search_activities(args.get("keyword", ""), args.get("district", ""), bool(args.get("indoor_only")))
    if name == "lookup_dialect":
        return lookup_dialect(args.get("expression", ""))
    if name == "find_complaint_channel":
        return find_complaint_channel(args.get("level", "보통"))
    return {"error": f"알 수 없는 도구: {name}"}


# --- 결과 구조 ------------------------------------------------------------------
@dataclass
class AgentResult:
    answer: str
    mode: str  # llm / rule / emergency / crisis
    steps: list = field(default_factory=list)
    verified: bool = True
    model: str = ""
    links: list = field(default_factory=list)  # [(이름, 공식 링크)] — 답 아래 버튼으로 표시


def collect_links(tool_outputs, limit=5):
    """도구 결과(검증 DB)에 있는 공식 링크만 모은다."""
    links, seen = [], set()

    def add(label, url):
        if url and url.startswith("https://") and url not in seen and len(links) < limit:
            seen.add(url)
            links.append((label, url))

    for output in tool_outputs:
        if not isinstance(output, dict):
            continue
        for policy in output.get("policies", []):
            add(f"{policy['사업명']} 안내·신청", policy.get("링크"))
        for activity in output.get("activities", []):
            add(f"{activity['이름']} 공식 안내", activity.get("링크"))
        for contact in output.get("연락처", []):
            url = _clean_url(contact)
            if url:
                add("국민신문고" if "epeople" in url else "접수 창구", url)
        if "기업노동자 전입지원금 판정" in output:
            add("창원청년정보플랫폼 청년지원 서비스", YOUTH_PLATFORM_URL)
    return links


def _step(steps, kind, detail):
    steps.append({"단계": kind, "내용": detail})


# --- 검증 ---------------------------------------------------------------------
PHONE_RE = re.compile(r"(?<![\d-])(?:0\d{1,2}-\d{3,4}-\d{4}|1\d{3}-\d{4}|11[29]|109)(?![\d-])")
URL_RE = re.compile(r"https?://[^\s)\]]+")


def verify_answer(answer, tool_outputs):
    """답에 나온 전화번호·링크가 도구 결과나 공용 연락처에 있는지 확인한다."""
    evidence = "\n".join(json.dumps(o, ensure_ascii=False) for o in tool_outputs)
    unknown = []
    for value in PHONE_RE.findall(answer) + [u.rstrip(".,") for u in URL_RE.findall(answer)]:
        if value in ALWAYS_ALLOWED or value in evidence:
            continue
        unknown.append(value)
    return not unknown, unknown


# --- 규칙 기반(LLM 미연결·오류 시) ------------------------------------------------
def _quoted(question):
    match = re.search(r"[‘'\"“](.+?)[’'\"”]", question)
    if match:
        return match.group(1)
    match = re.match(r"\s*(.+?)\s*(?:가|이|는|은)?\s*(?:무슨|뭔|뭐)", question)
    return match.group(1) if match else question


def _classify_complaint(question):
    if any(w in question for w in ("우울", "외로", "힘들어", "불안", "심심")):
        return "마음 건강"
    if any(w in question for w in ("제안", "아이디어", "건의")):
        return "제안"
    if any(w in question for w in ("고장", "파손", "꺼져", "깨져", "구멍", "가로등", "도로", "누수")):
        return "높음"
    return "보통"


def _format_rule_answer(tool_name, output, question):
    if tool_name == "lookup_dialect":
        if output.get("found"):
            return f"‘{output['표현']}’은(는) “{output['표준어 뜻']}”라는 뜻이에요({output['표시']}). 주로 {output.get('사용 상황') or '일상'}에서 써요."
        return f"‘{_quoted(question)}’은(는) 제가 가진 지역말 사전(핵심 30개)에 없어요. 정확한 뜻은 주변 창원 분께 여쭤보세요."
    if tool_name == "find_complaint_channel":
        return f"[{output['단계']}] {output['안내']}\n연락처: " + ", ".join(output["연락처"])
    if tool_name == "search_activities":
        if not output["activities"]:
            return f"조건에 맞는 장소를 확인된 정보에서 찾지 못했어요. ‘창원 둘러보기’ 화면에서 지역·분야를 바꿔 보세요."
        lines = [f"- {a['이름']} ({a['구']}, {a['분야']})" for a in output["activities"]]
        return "확인된 장소 중 이런 곳이 있어요.\n" + "\n".join(lines) + "\n특정 업체 홍보가 아니며, 방문 전 운영시간을 확인해 주세요."
    if tool_name == "search_policies":
        if not output["policies"]:
            return f"확인된 정책 정보에는 없어요. {CALL_CENTER} 또는 창원청년정보플랫폼({YOUTH_PLATFORM_URL})에서 확인해 주세요."
        lines = [f"- {p['사업명']}: {p['지원 내용'][:60]}" for p in output["policies"]]
        return "확인된 정책 중 관련된 것이에요. 대상 여부는 담당 창구에서 꼭 확인해 주세요.\n" + "\n".join(lines)
    if tool_name == "get_my_situation":
        p01 = output["기업노동자 전입지원금 판정"]
        text = f"기업노동자 전입지원금: {p01['결과']}"
        if p01.get("신청 가능 예정일"):
            text += f"(신청 가능 예정일 {p01['신청 가능 예정일']})"
        if output.get("정착 단계"):
            text += f"\n지금은 {output['정착 단계']} 단계예요. ‘받을 수 있는 지원’과 ‘정착 할 일’ 화면에서 자세히 볼 수 있어요."
        return text
    return f"확인된 정보에는 없어요. {CALL_CENTER}로 문의해 주세요."


def rule_based_answer(question, profile=None, steps=None, reason=""):
    steps = steps if steps is not None else []
    q = question
    if any(w in q for w in ("뜻", "무슨 말", "무슨 뜻", "뭔 말", "사투리", "지역말")):
        tool, args = "lookup_dialect", {"expression": _quoted(q)}
    elif any(w in q for w in ("고장", "파손", "신고", "민원", "불편", "가로등", "도로", "건의", "제안", "우울", "외로", "힘들어", "불안")):
        tool, args = "find_complaint_channel", {"level": _classify_complaint(q)}
    elif any(w in q for w in ("카페", "맛집", "먹을", "가볼", "갈 만한", "놀러", "산책", "야경", "축제", "행사", "주말", "데이트", "운동", "반려")):
        keyword = next((w for w in ("카페", "야경", "산책", "축제", "행사", "운동", "반려") if w in q), "")
        tool, args = "search_activities", {"keyword": keyword, "indoor_only": "실내" in q or "비" in q}
    elif any(w in q for w in ("내가", "나는", "받을 수", "해당")):
        tool, args = "get_my_situation", {}
    elif any(w in q for w in ("지원", "혜택", "정책", "월세", "통장", "적금", "교통", "패스", "수당")):
        keyword = next((w for w in ("월세", "통장", "적금", "교통", "패스", "수당", "전입", "자격증") if w in q), "")
        tool, args = "search_policies", {"keyword": keyword}
    else:
        _step(steps, "목표 인식(규칙)", "창원 정착 관련 기능과 맞는 질문을 찾지 못함")
        return AgentResult(
            answer=(
                "죄송해요, 그 질문은 제가 확인된 정보로 답하기 어려워요. 저는 창원 정착에 필요한 "
                "지원 확인, 정착 할 일, 가볼 만한 곳, 지역말 뜻, 불편 접수 창구를 도와드려요. "
                f"그 밖의 궁금한 점은 {CALL_CENTER}로 문의해 주세요."
            ),
            mode="rule", steps=steps, verified=True,
        )
    _step(steps, "목표 인식(규칙)", f"키워드로 '{tool}' 도구 선택" + (f" — {reason}" if reason else ""))
    output = run_tool(tool, args, profile)
    _step(steps, "도구 호출", f"{tool}({json.dumps(args, ensure_ascii=False)}) → {_summarize(output)}")
    answer = _format_rule_answer(tool, output, question)
    ok, unknown = verify_answer(answer, [output])
    _step(steps, "답변 검증", "통과" if ok else f"확인 안 된 값 {unknown}")
    return AgentResult(answer=answer, mode="rule", steps=steps, verified=ok, links=collect_links([output]))


def _summarize(output):
    if isinstance(output, dict):
        if "count" in output:
            return f"{output['count']}건"
        if "found" in output:
            return "찾음" if output["found"] else "없음"
        if "단계" in output:
            return f"{output['단계']} 창구"
    return "결과 받음"


# --- 안전 우선 처리 --------------------------------------------------------------
def safety_check(question):
    if any(w in question for w in CRISIS_WORDS):
        return AgentResult(
            answer=(
                "많이 힘드시군요. 지금 바로 이야기 나눌 수 있는 곳이 있어요.\n"
                "- 자살예방상담전화 109 (24시간)\n- 위급하면 119\n"
                "- 경남 청년마음단디센터 055-286-1008 (청년 마음건강 상담)\n"
                "혼자 견디지 말고 꼭 연락해 주세요."
            ),
            mode="crisis",
            steps=[{"단계": "안전 확인", "내용": "위기 표현 감지 → AI 판단 없이 상담 창구 즉시 안내"}],
        )
    if any(w in question for w in EMERGENCY_WORDS):
        return AgentResult(
            answer="긴급 상황이에요. 지금 바로 112(경찰) 또는 119(소방·구급)에 신고하세요. 안전한 곳으로 먼저 이동하세요.",
            mode="emergency",
            steps=[{"단계": "안전 확인", "내용": "긴급 표현 감지 → 다른 처리 없이 112·119 안내"}],
        )
    return None


# --- LLM 호출 ------------------------------------------------------------------
def _profile_for_llm(profile):
    # 닉네임 등 식별 정보는 보내지 않는다.
    return {k: v for k, v in (profile or {}).items() if k != "nickname"}


def _run_anthropic(client, model, question, profile, steps, tool_outputs, extra_instruction=""):
    messages = [{"role": "user", "content": question + extra_instruction}]
    for _ in range(MAX_TOOL_ROUNDS + 1):
        response = client.messages.create(
            model=model, max_tokens=1024, system=SYSTEM_PROMPT, tools=TOOLS, messages=messages,
        )
        tool_uses = [b for b in response.content if getattr(b, "type", "") == "tool_use"]
        if not tool_uses:
            return "".join(getattr(b, "text", "") for b in response.content if getattr(b, "type", "") == "text").strip()
        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in tool_uses:
            output = run_tool(block.name, block.input, profile)
            tool_outputs.append(output)
            _step(steps, "도구 호출", f"{block.name}({json.dumps(block.input, ensure_ascii=False)}) → {_summarize(output)}")
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(output, ensure_ascii=False)})
        messages.append({"role": "user", "content": results})
    raise RuntimeError("도구 호출 횟수 초과")


def _run_openai(client, model, question, profile, steps, tool_outputs, extra_instruction=""):
    tools = [{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}} for t in TOOLS]
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": question + extra_instruction}]
    for _ in range(MAX_TOOL_ROUNDS + 1):
        response = client.chat.completions.create(model=model, messages=messages, tools=tools)
        message = response.choices[0].message
        if not message.tool_calls:
            return (message.content or "").strip()
        messages.append({
            "role": "assistant", "content": message.content,
            "tool_calls": [{"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}} for c in message.tool_calls],
        })
        for call in message.tool_calls:
            args = json.loads(call.function.arguments or "{}")
            output = run_tool(call.function.name, args, profile)
            tool_outputs.append(output)
            _step(steps, "도구 호출", f"{call.function.name}({json.dumps(args, ensure_ascii=False)}) → {_summarize(output)}")
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(output, ensure_ascii=False)})
    raise RuntimeError("도구 호출 횟수 초과")


def make_client(provider, api_key):
    if provider == "anthropic":
        import anthropic
        return anthropic.Anthropic(api_key=api_key)
    if provider == "openai":
        import openai
        return openai.OpenAI(api_key=api_key)
    raise ValueError(provider)


def run_agent(question, profile=None, provider=None, client=None, model=None):
    question = (question or "").strip()
    safe = safety_check(question)
    if safe:
        return safe
    steps = []
    llm_profile = _profile_for_llm(profile)
    if not provider or client is None:
        return rule_based_answer(question, profile, steps, reason="AI 모델 미연결")
    model = model or DEFAULT_MODELS[provider]
    runner = _run_anthropic if provider == "anthropic" else _run_openai
    _step(steps, "목표 인식", f"{MODEL_LABELS.get(model, model)}이(가) 질문을 이해하고 필요한 도구를 고름")
    tool_outputs = []
    try:
        answer = runner(client, model, question, llm_profile, steps, tool_outputs)
        ok, unknown = verify_answer(answer, tool_outputs)
        if not ok:
            _step(steps, "답변 검증", f"도구 결과에 없는 값 {unknown} 발견 → 다시 작성 요청")
            answer = runner(
                client, model, question, llm_profile, steps, tool_outputs,
                extra_instruction=f"\n\n(검증 안내: 다음 값은 도구 결과에 없으니 빼고 다시 답해: {', '.join(unknown)})",
            )
            ok, unknown = verify_answer(answer, tool_outputs)
        if not ok:
            _step(steps, "답변 검증", f"재작성 후에도 확인 안 된 값 {unknown} → 규칙 기반 안내로 전환")
            return rule_based_answer(question, profile, steps, reason="검증 실패")
        _step(steps, "답변 검증", "통과 — 답의 연락처·링크가 모두 도구 결과(검증 DB)에 있음")
        if not tool_outputs:
            _step(steps, "참고", "도구 없이 답함(인사·범위 밖 질문 등)")
        return AgentResult(answer=answer, mode="llm", steps=steps, verified=True, model=model,
                           links=collect_links(tool_outputs))
    except Exception as error:  # API 키 오류·네트워크·한도 초과 등
        _step(steps, "AI 연결 오류", type(error).__name__)
        return rule_based_answer(question, profile, steps, reason="AI 연결 오류")
