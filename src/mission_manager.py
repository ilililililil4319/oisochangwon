import json
from pathlib import Path


MISSIONS_PATH = Path(__file__).resolve().parents[1] / "data" / "missions.json"
_REQUIRED_FIELDS = (
    "ID",
    "개월",
    "월별 테마",
    "미션",
    "난이도(쉬움/보통)",
    "연결 기능",
    "완료 기준",
    "메모",
    "is_service_idea",
    "서비스 목표",
)
_NON_EMPTY_STRING_FIELDS = (
    "ID",
    "월별 테마",
    "미션",
    "난이도(쉬움/보통)",
    "연결 기능",
    "완료 기준",
    "서비스 목표",
)


def load_missions(path=None):
    """Load and validate source mission records without rewriting their fields."""
    source_path = MISSIONS_PATH if path is None else Path(path)
    with source_path.open("r", encoding="utf-8") as source_file:
        payload = json.load(source_file)

    if not isinstance(payload, dict):
        raise ValueError("missions.json must contain a JSON object")

    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError("missions.json must contain an items list")
    if type(payload.get("count")) is not int or payload["count"] != len(items):
        raise ValueError("missions.json count must match the number of items")

    seen_ids = set()
    month_themes = {}
    for index, mission in enumerate(items):
        if not isinstance(mission, dict):
            raise ValueError(f"mission at index {index} must be an object")

        missing_fields = [field for field in _REQUIRED_FIELDS if field not in mission]
        if missing_fields:
            raise ValueError(
                f"mission at index {index} is missing fields: {missing_fields}"
            )

        for field in _NON_EMPTY_STRING_FIELDS:
            if not isinstance(mission[field], str) or not mission[field].strip():
                raise ValueError(
                    f"mission at index {index} has an invalid {field} value"
                )
        if not isinstance(mission["메모"], str):
            raise ValueError(f"mission at index {index} has an invalid 메모 value")
        if type(mission["개월"]) is not int or mission["개월"] < 1:
            raise ValueError(f"mission at index {index} has an invalid 개월 value")
        if type(mission["is_service_idea"]) is not bool:
            raise ValueError(
                f"mission at index {index} has an invalid is_service_idea value"
            )

        mission_id = mission["ID"]
        if mission_id in seen_ids:
            raise ValueError(f"duplicate mission ID: {mission_id}")
        seen_ids.add(mission_id)

        month = mission["개월"]
        theme = mission["월별 테마"]
        existing_theme = month_themes.setdefault(month, theme)
        if existing_theme != theme:
            raise ValueError(f"month {month} has inconsistent themes")

    return items


def group_missions_by_month(missions):
    """Group source missions by their declared month, preserving source order."""
    groups = {}
    for mission in missions:
        month = mission["개월"]
        theme = mission["월별 테마"]
        group = groups.setdefault(
            month,
            {"month": month, "theme": theme, "missions": []},
        )
        if group["theme"] != theme:
            raise ValueError(f"month {month} has inconsistent themes")
        group["missions"].append(mission)

    return [groups[month] for month in sorted(groups)]


# 하는 일별 할 일 문구 — 직장인 기준 할 일(재직자·중소기업 재직자·기업노동자 전입지원금)을
# 학생·기타(구직)·자영업에 맞게 바꿔 보여 준다. 미션 ID(저장 키)는 그대로 두고, 팀 데이터에 있는 지원만 안내한다.
JOB_THEMES = {4: {"학생": "학업·생활과 연결하기", "기타": "취업 준비·생활과 연결하기"}}
_P01_OTHERS = (
    "내 조건으로 받을 수 있는 혜택 다시 확인하기 (기업노동자 전입지원금은 창원 사업장에 근무하는 직장인 대상)",
    "혜택 목록 다시 열람",
    (),
)
JOB_MISSIONS = {
    "M4-1": {
        "학생": ("전입 대학(원)생 생활안정지원(월 6만원) 신청 조건 확인하기", "조건 확인 + 신청 여부 기록", ("P32",)),
        "기타": ("국민취업지원제도(구직촉진수당·취업지원) 조건 확인하기", "조건 확인 기록", ("P29",)),
        "자영업": ("‘창원시 청년정책 전체 보기’에서 자영업 청년이 받을 수 있는 지원 찾아보기", "찾은 지원 1개 이상 메모", ()),
    },
    "M4-3": {
        "학생": ("졸업 후 취업 준비 대비 — 청년 면접수당·자격증 시험 응시료 지원 조건 미리 보기", "조건 확인 기록", ("P07", "P08")),
        "기타": ("청년 면접수당·자격증 시험 응시료 지원 신청하기", "신청 완료 체크", ("P07", "P08")),
        "자영업": ("청년 스포츠 패스 다음 모집 공고에서 자영업 참여 가능 여부 확인하기", "확인 결과 기록", ("P09",)),
    },
    "M6-1": {"학생": _P01_OTHERS, "기타": _P01_OTHERS, "자영업": _P01_OTHERS},
}


def personalize_missions(missions, job_type):
    if job_type not in ("학생", "기타", "자영업"):
        return missions
    personalized = []
    for mission in missions:
        mission = dict(mission)
        theme = JOB_THEMES.get(mission["개월"], {}).get(job_type)
        if theme:
            mission["월별 테마"] = theme
        variant = JOB_MISSIONS.get(mission["ID"], {}).get(job_type)
        if variant:
            mission["미션"], mission["완료 기준"], mission["_policy_ids"] = variant
            mission["_variant"] = True
        personalized.append(mission)
    return personalized
