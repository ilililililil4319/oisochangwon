import json
from pathlib import Path


MISSIONS_PATH = Path(__file__).resolve().parent / "data" / "missions.json"
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
