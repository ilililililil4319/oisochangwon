import json
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from mission_manager import load_missions
import activity_manager


POLICY_RESOURCES_PATH = (
    Path(__file__).resolve().parent / "data" / "mission_resources.json"
)
OFFICIAL_POLICY_HOSTS = frozenset(
    {
        "www.changwon.go.kr",
        "www.gyeongnam.go.kr",
        "www.korea-pass.kr",
        "vacation.visitkorea.or.kr",
        "www.modadream.kr",
        "baro.gyeongnam.go.kr",
        "www.cwsisul.or.kr",
        "reserve.cwsisul.or.kr",
        "lib.changwon.go.kr",
        "www.1365.go.kr",
        "sakers.kbl.or.kr",
    }
)
_REQUIRED_FIELDS = (
    "mission_id",
    "resource_type",
    "title",
    "summary",
    "eligibility",
    "application_period",
    "application_status",
    "details_status",
    "official_links",
    "verified_date",
    "source_type",
)
_TEXT_FIELDS = (
    "mission_id",
    "resource_type",
    "title",
    "summary",
    "eligibility",
    "application_period",
    "application_status",
    "details_status",
    "source_type",
)


def load_mission_resources(path=None):
    source_path = POLICY_RESOURCES_PATH if path is None else Path(path)
    with source_path.open("r", encoding="utf-8") as source_file:
        payload = json.load(source_file)

    if not isinstance(payload, dict):
        raise ValueError("mission resources must be an object")
    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError("mission resources must contain an items list")
    if type(payload.get("count")) is not int or payload["count"] != len(items):
        raise ValueError("mission resource count must match the number of items")

    mission_ids = {mission["ID"] for mission in load_missions()}
    activity_ids_in_catalog = {
        activity["ID"] for activity in activity_manager.load_activities()
    }
    resources = {}
    for index, resource in enumerate(items):
        if not isinstance(resource, dict):
            raise ValueError(f"resource at index {index} must be an object")
        missing_fields = [field for field in _REQUIRED_FIELDS if field not in resource]
        if missing_fields:
            raise ValueError(
                f"resource at index {index} is missing fields: {missing_fields}"
            )
        for field in _TEXT_FIELDS:
            if not isinstance(resource[field], str) or not resource[field].strip():
                raise ValueError(
                    f"resource at index {index} has an invalid {field} value"
                )

        verified_date = resource["verified_date"]
        if verified_date is not None:
            if not isinstance(verified_date, str):
                raise ValueError(f"resource at index {index} has an invalid verified_date")
            try:
                date.fromisoformat(verified_date)
            except ValueError as error:
                raise ValueError(
                    f"resource at index {index} has an invalid verified_date"
                ) from error

        links = resource["official_links"]
        if not isinstance(links, list):
            raise ValueError(f"resource at index {index} official_links must be a list")
        for link in links:
            if (
                not isinstance(link, dict)
                or not isinstance(link.get("label"), str)
                or not link["label"].strip()
            ):
                raise ValueError(f"resource at index {index} has an invalid link")
            if not _is_approved_official_url(link.get("url")):
                raise ValueError(f"resource at index {index} has a non-official link")

        application_url = resource.get("application_url")
        if application_url is not None and not _is_approved_official_url(
            application_url
        ):
            raise ValueError(
                f"resource at index {index} has a non-official application URL"
            )

        activity_ids = resource.get("related_activity_ids", [])
        if not isinstance(activity_ids, list) or not all(
            isinstance(activity_id, str) and activity_id
            for activity_id in activity_ids
        ):
            raise ValueError(f"resource at index {index} has invalid activity IDs")

        related_places = resource.get("related_places", [])
        if not isinstance(related_places, list):
            raise ValueError(
                f"resource at index {index} related_places must be a list"
            )
        for place in related_places:
            if not isinstance(place, dict):
                raise ValueError(f"resource at index {index} has an invalid place")
            for field in ("title", "district", "address", "official_url"):
                if not isinstance(place.get(field), str) or not place[field].strip():
                    raise ValueError(
                        f"resource at index {index} has an invalid place {field}"
                    )
            if not _is_approved_official_url(place["official_url"]):
                raise ValueError(f"resource at index {index} has a non-official place link")
            place_application_url = place.get("application_url")
            if place_application_url is not None and not _is_approved_official_url(
                place_application_url
            ):
                raise ValueError(
                    f"resource at index {index} has a non-official place application URL"
                )

        mission_id = resource["mission_id"]
        if mission_id not in mission_ids:
            raise ValueError(f"unknown mission ID: {mission_id}")
        if any(activity_id not in activity_ids_in_catalog for activity_id in activity_ids):
            raise ValueError(f"resource at index {index} has unknown activity IDs")
        if mission_id in resources:
            raise ValueError(f"duplicate mission resource: {mission_id}")
        resources[mission_id] = resource

    return resources


def _is_approved_official_url(value):
    if not isinstance(value, str):
        return False
    if not value or any(character.isspace() for character in value):
        return False
    try:
        parsed_url = urlsplit(value)
        return (
            parsed_url.scheme == "https"
            and (parsed_url.hostname or "").lower() in OFFICIAL_POLICY_HOSTS
            and parsed_url.username is None
            and parsed_url.password is None
            and parsed_url.port in (None, 443)
        )
    except ValueError:
        return False
