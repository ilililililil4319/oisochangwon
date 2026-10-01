import json
import re
from pathlib import Path
from urllib.parse import urlsplit


ACTIVITIES_PATH = Path(__file__).resolve().parent / "data" / "activities_mvp.json"
_REQUIRED_FIELDS = (
    "ID",
    "이름",
    "유형(행사/모임/기관/공간)",
    "생활권(구)",
    "관심사 태그",
    "대상",
    "참여 방법",
    "일정·운영시간",
    "공식 URL",
    "출처",
    "최종 확인일",
    "MVP 선별",
    "MVP 그룹",
    "대중교통 접근(검수)",
)
_STRING_FIELDS = (
    "ID",
    "이름",
    "유형(행사/모임/기관/공간)",
    "생활권(구)",
    "관심사 태그",
    "대상",
    "참여 방법",
    "일정·운영시간",
    "공식 URL",
    "출처",
    "최종 확인일",
    "MVP 선별",
    "MVP 그룹",
    "대중교통 접근(검수)",
)
_DISTRICT_PATTERN = re.compile(r"[가-힣]+구")
_URL_PATTERN = re.compile(r"https?://[^\s<>\"']+")


def load_activities(path=None):
    """Load and validate the curated local activity data."""
    source_path = ACTIVITIES_PATH if path is None else Path(path)
    with source_path.open("r", encoding="utf-8") as source_file:
        payload = json.load(source_file)

    if not isinstance(payload, dict):
        raise ValueError("activities data must contain an object")

    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError("activities data must contain an items list")
    if type(payload.get("count")) is not int or payload["count"] != len(items):
        raise ValueError("activities count must match the number of items")

    seen_ids = set()
    for index, activity in enumerate(items):
        if not isinstance(activity, dict):
            raise ValueError(f"activity at index {index} must be an object")

        missing_fields = [field for field in _REQUIRED_FIELDS if field not in activity]
        if missing_fields:
            raise ValueError(
                f"activity at index {index} is missing fields: {missing_fields}"
            )

        for field in _STRING_FIELDS:
            if not isinstance(activity[field], str) or not activity[field].strip():
                raise ValueError(
                    f"activity at index {index} has an invalid {field} value"
                )

        for field in ("시작일", "종료일"):
            if field in activity and activity[field] is not None and not isinstance(
                activity[field], str
            ):
                raise ValueError(
                    f"activity at index {index} has an invalid {field} value"
                )

        activity_id = activity["ID"]
        if activity_id in seen_ids:
            raise ValueError(f"duplicate activity ID: {activity_id}")
        seen_ids.add(activity_id)

        if not _extract_http_url(activity["공식 URL"]) and not activity[
            "공식 URL"
        ].startswith("없음("):
            raise ValueError(f"activity at index {index} has an invalid official URL")

    return items


def _extract_http_url(value):
    url_match = _URL_PATTERN.search(value.strip())
    if not url_match:
        return None

    candidate = url_match.group(0).rstrip(".,;)")
    parsed_url = urlsplit(candidate)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        return None
    return candidate


def get_activity_filter_options(activities):
    districts = set()
    categories = []
    seen_categories = set()

    for activity in activities:
        districts.update(_DISTRICT_PATTERN.findall(activity["생활권(구)"]))
        category = activity["MVP 그룹"]
        if category not in seen_categories:
            categories.append(category)
            seen_categories.add(category)

    return {
        "districts": sorted(districts),
        "categories": categories,
    }


def filter_activities(activities, district=None, category=None):
    options = get_activity_filter_options(activities)
    if district is not None and district not in options["districts"]:
        raise ValueError("unknown district filter")
    if category is not None and category not in options["categories"]:
        raise ValueError("unknown category filter")

    return [
        activity
        for activity in activities
        if (district is None or district in activity["생활권(구)"])
        and (category is None or activity["MVP 그룹"] == category)
    ]


def activity_view(activity):
    route_text = activity["대중교통 접근(검수)"]
    route_url = _extract_http_url(route_text)

    return {
        "id": activity["ID"],
        "name": activity["이름"],
        "kind": activity["유형(행사/모임/기관/공간)"],
        "district": activity["생활권(구)"],
        "category": activity["MVP 그룹"],
        "interests": activity["관심사 태그"],
        "audience": activity["대상"],
        "participation": activity["참여 방법"],
        "schedule": activity["일정·운영시간"],
        "start_date": activity.get("시작일"),
        "end_date": activity.get("종료일"),
        "official_url": _extract_http_url(activity["공식 URL"]),
        "directions_url": route_url,
        "last_checked": activity["최종 확인일"],
    }
