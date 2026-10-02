"""PC web map links, independent of cached activity presentation data."""
import re
from urllib.parse import quote, urlsplit

NAVER_MAP_DOMAIN = "map.naver.com"
NAVER_MAP_WEB_URL = "https://map.naver.com/p/"
# Existing activity names, district notes and memo fields supply these venues.
# Multi-venue events use the first recorded venue, not an invented event address.
_EVENT_VENUES = {
    "제26회 마산가고파국화축제": "3·15해양누리공원",  # 메모: 제1축제장
    "창원 LG 세이커스 홈경기 (창원체육관)": "창원체육관",  # 이름/메모
    "창동예술촌 '창동쪽샘길' 플리마켓·아트클래스": "창동예술촌",  # 이름/연락처
    "바로슥 클래스 - 주말 플레이리스트": "스펀지파크",  # 생활권(구)
    "문화다양성축제 맘프(MAMF) 2026": "용지문화공원",  # 메모
    "도계부부 달빛야시장 (2026)": "도계부부시장",  # 메모
    "2026 경남특산물박람회": "창원컨벤션센터",  # 메모/출처
}
_URL_PATTERN = re.compile(r"https?://[^\s<>\"']+")


def _extract_http_url(value):
    match = _URL_PATTERN.search(value) if isinstance(value, str) else None
    return match.group(0) if match else None


def map_search_name(display_name):
    """Keep the display name intact; derive a short, evidence-backed map name."""
    if not isinstance(display_name, str):
        return ""
    name = display_name.strip()
    if name in _EVENT_VENUES:
        return _EVENT_VENUES[name]
    # Strip explanatory parentheses, including nested pairs, without cutting words.
    while re.search(r"\([^()]*\)", name):
        name = re.sub(r"\([^()]*\)", " ", name)
    return " ".join(name.split())


def build_naver_map_search_web_url(place_name, district=""):
    """Search a concise place name; district is retained only for call compatibility."""
    name = map_search_name(place_name)
    if not name:
        return NAVER_MAP_WEB_URL
    query = name if "창원" in name else f"{name} 창원"
    return f"{NAVER_MAP_WEB_URL}search/{quote(query, safe='')}"


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

