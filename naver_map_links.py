"""PC web map links, independent of cached activity presentation data."""
import re
from urllib.parse import quote, urlsplit

NAVER_MAP_DOMAIN = "map.naver.com"
NAVER_MAP_WEB_URL = "https://map.naver.com/p/"
_DISTRICT_PATTERN = re.compile(r"[가-힣]+구")
_URL_PATTERN = re.compile(r"https?://[^\s<>\"']+")


def _extract_http_url(value):
    match = _URL_PATTERN.search(value) if isinstance(value, str) else None
    return match.group(0) if match else None


def build_naver_map_search_web_url(place_name, district=""):
    """Use the search route observed from Naver Map's own web search UI."""
    if not isinstance(place_name, str) or not place_name.strip():
        return NAVER_MAP_WEB_URL
    parts = [place_name.strip()]
    if "창원" not in place_name:
        parts.append("창원")
    for area in _DISTRICT_PATTERN.findall(district if isinstance(district, str) else ""):
        if area not in place_name and area not in parts:
            parts.append(area)
    return f"{NAVER_MAP_WEB_URL}search/{quote(' '.join(parts), safe='')}"


def naver_map_web_url(activity):
    # Reuse only already-present HTTPS place links, never invent a place ID.
    for field in ("공식 URL", "대중교통 접근(검수)"):
        url = _extract_http_url(activity.get(field, ""))
        if url:
            parsed = urlsplit(url)
            if (parsed.scheme == "https" and parsed.hostname == NAVER_MAP_DOMAIN
                    and re.fullmatch(r"/p/(?:entry/)?place/\d+/?", parsed.path)
                    and parsed.username is None and parsed.password is None):
                return url
    return build_naver_map_search_web_url(activity.get("이름"), activity.get("생활권(구)", ""))

