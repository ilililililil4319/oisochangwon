import json
import re
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from naver_map_links import build_naver_map_search_web_url, map_search_name, naver_map_web_url


ACTIVITIES_PATH = Path(__file__).resolve().parents[1] / "data" / "activities_mvp.json"
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
PUBLIC_OFFICIAL_DOMAINS = frozenset(
    {
        "www.changwon.go.kr",
        "www.gyeongnam.go.kr",
        "www.mcst.go.kr",
        "korean.visitkorea.or.kr",
        "access.visitkorea.or.kr",
    }
)
OPERATOR_OFFICIAL_DOMAINS = frozenset(
    {
        "www.cwsisul.or.kr",
        "sakers.kbl.or.kr",
        "changdongartvillage.kr",
        "cgv.co.kr",
        "www.ceco.co.kr",
        "www.dd.co.kr",
        "www.lotteshopping.com",
        "www.shinsegae.com",
        "spathespace.com",
        "www.fatimahosp.co.kr",
        "www.smgysh.co.kr",
        "www.yonseis.com",
        "www.mamf.co.kr",
    }
)
NAVER_MAP_DOMAIN = "map.naver.com"
_BLOG_DOMAINS = frozenset({"blog.naver.com", "mirimblog.com"})
_DIRECTORY_DOMAINS = frozenset(
    {"www.diningcode.com", "www.ban-life.com", "selection.moumi.app"}
)
_NEWS_DOMAINS = frozenset(
    {
        "www.koreatimenews.com",
        "www.gnnews.co.kr",
        "thetravelnews.co.kr",
        "sports.news.nate.com",
    }
)


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


def classify_activity_url(value):
    url = _extract_http_url(value) if isinstance(value, str) else None
    if not url:
        return {
            "domain": None,
            "classification": "no_link",
            "is_official": False,
            "url": None,
            "label": None,
        }

    parsed_url = urlsplit(url)
    domain = (parsed_url.hostname or "").lower()
    if domain == NAVER_MAP_DOMAIN:
        return {
            "domain": domain,
            "classification": "naver_map",
            "is_official": False,
            "url": None,
            "label": None,
        }

    if domain in PUBLIC_OFFICIAL_DOMAINS:
        classification = "public_official"
    elif domain in OPERATOR_OFFICIAL_DOMAINS:
        classification = "operator_official"
    elif domain == "namu.wiki" or domain.endswith(".wikipedia.org"):
        classification = "encyclopedia"
    elif domain in _BLOG_DOMAINS or "blog" in domain:
        classification = "blog"
    elif domain == "facebook.com" or domain.endswith(".facebook.com"):
        classification = "unverified_social"
    elif domain in _DIRECTORY_DOMAINS:
        classification = "directory"
    elif domain in _NEWS_DOMAINS:
        classification = "news"
    else:
        classification = "unverified"

    # This venue currently has no certificate-valid HTTPS endpoint.
    withheld = domain == "changdongartvillage.kr"
    is_official = classification in {"public_official", "operator_official"} and not withheld
    path = parsed_url.path.lower()
    if is_official and any(
        marker in path for marker in ("/reserve", "/reservation", "/booking", "/ticket")
    ):
        label = "예약·이용 안내 보기"
    elif is_official:
        label = "공식 안내 보기"
    else:
        label = None

    return {
        "domain": domain,
        "classification": classification,
        "is_official": is_official,
        "url": url if is_official else None,
        "label": label,
    }


def build_naver_map_search_app_url(place_name, app_name):
    """Build the documented Naver Maps app search URL; never invent coordinates."""
    if not isinstance(place_name, str) or not place_name.strip():
        raise ValueError("place_name must not be empty")
    if not isinstance(app_name, str):
        raise TypeError("app_name must be a string")

    parsed_app_name = urlsplit(app_name)
    if parsed_app_name.scheme not in {"http", "https"} or not parsed_app_name.netloc:
        raise ValueError("app_name must be the calling web page URL")

    parameters = urlencode(
        {
            "query": place_name.strip(),
            "appname": app_name,
        }
    )
    return f"nmap://search?{parameters}"


def activity_introduction(activity):
    """Summarize only recorded type/category/tags, without ratings or new services."""
    name = activity.get("이름")
    name = name if isinstance(name, str) else ""
    raw_tags = activity.get("관심사 태그")
    raw_tags = raw_tags if isinstance(raw_tags, str) else ""
    tags = [tag.strip() for tag in raw_tags.split(",") if tag.strip()]
    if all(tag in tags for tag in ("온천", "찜질방", "인피니티풀")):
        return "온천·찜질방·인피니티풀을 이용할 수 있는 휴식 공간이에요."
    if name.endswith("미술관") and "미술" in tags:
        return "미술 작품을 관람할 수 있는 미술관이에요."
    kind = activity.get("유형(행사/모임/기관/공간)")
    category = activity.get("MVP 그룹")
    subject = "·".join(tags[:3]) or (category.strip() if isinstance(category, str) else "")
    if not subject:
        return ""
    kind = kind.strip() if isinstance(kind, str) and kind.strip() else "활동"
    return f"{subject} 관련 {kind}이에요."


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


def activity_view(activity, app_name):
    source_link = classify_activity_url(activity["공식 URL"])

    return {
        "id": activity["ID"],
        "name": activity["이름"],
        "introduction": activity_introduction(activity),
        "kind": activity["유형(행사/모임/기관/공간)"],
        "district": activity["생활권(구)"],
        "category": activity["MVP 그룹"],
        "interests": activity["관심사 태그"],
        "audience": activity["대상"],
        "participation": activity["참여 방법"],
        "schedule": activity["일정·운영시간"],
        "start_date": activity.get("시작일"),
        "end_date": activity.get("종료일"),
        "official_url": source_link["url"],
        "official_link_label": source_link["label"],
        "link_classification": source_link["classification"],
        "map_search_name": map_search_name(activity["이름"]),
        "naver_map_url": naver_map_web_url(activity),
        "naver_map_search_app_url": build_naver_map_search_app_url(
            activity["이름"],
            app_name,
        ),
        "last_checked": activity["최종 확인일"],
    }
