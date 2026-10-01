import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from policy_resource_manager import load_mission_resources


class PolicyResourceManagerTests(unittest.TestCase):
    def test_loads_resources_for_policy_related_missions(self):
        resources = load_mission_resources()

        self.assertEqual(len(resources), 18)
        self.assertEqual(
            set(resources),
            {"M1-2", "M1-3", "M1-4", "M2-1", "M2-2", "M2-3", "M3-1", "M3-2", "M3-3", "M3-4", "M4-1", "M4-2", "M4-3", "M5-1", "M5-2", "M5-3", "M6-1", "M6-2"},
        )
        self.assertEqual(resources["M6-1"]["details_status"], "verified")
        self.assertEqual(resources["M2-3"]["details_status"], "unverified")
        self.assertIsNone(resources["M2-3"]["verified_date"])

    def test_rejects_unapproved_link_hosts(self):
        resource = load_mission_resources()["M6-1"]
        resource["official_links"] = [
            {"label": "공식 안내 보기", "url": "https://example.com/fake"}
        ]
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "mission_resources.json"
            path.write_text(
                json.dumps({"count": 1, "items": [resource]}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "non-official link"):
                load_mission_resources(path)

    def test_rejects_duplicate_mission_resource_ids(self):
        resource = load_mission_resources()["M6-1"]
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "mission_resources.json"
            path.write_text(
                json.dumps({"count": 2, "items": [resource, resource]}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "duplicate mission resource"):
                load_mission_resources(path)


    def _assert_invalid(self, resource, error):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "resources.json"
            path.write_text(json.dumps({"count": 1, "items": [resource]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, error):
                load_mission_resources(path)

    def test_rejects_unknown_mission_and_activity_references(self):
        resource = load_mission_resources()["M6-1"]
        resource["mission_id"] = "M99-1"
        self._assert_invalid(resource, "unknown mission ID")
        resource["mission_id"] = "M6-1"
        resource["related_activity_ids"] = ["A99999"]
        self._assert_invalid(resource, "unknown activity IDs")

    def test_rejects_insecure_spoofed_and_malformed_urls_in_all_link_fields(self):
        urls = (
            "http://www.changwon.go.kr/", "https://www.changwon.go.kr.evil.test/",
            "https://evil.test@www.changwon.go.kr/", "https://www.changwon.go.kr:444/",
            "https://[invalid/", "https://www.changwon.go.kr:bad/",
            "https://www.changwon.go.kr/ bad",
        )
        for url in urls:
            for field in ("official_links", "application_url", "place_official", "place_application"):
                with self.subTest(url=url, field=field):
                    resource = load_mission_resources()["M2-1"]
                    if field == "official_links":
                        resource[field][0]["url"] = url
                    elif field == "application_url":
                        resource[field] = url
                    elif field == "place_official":
                        resource["related_places"][0]["official_url"] = url
                    else:
                        resource["related_places"][0]["application_url"] = url
                    self._assert_invalid(resource, "non-official")

    def test_withheld_venue_links_are_preserved_without_clickable_links(self):
        resources = load_mission_resources()
        for mission_id in ("M3-2", "M3-3"):
            resource = resources[mission_id]
            self.assertEqual(resource["official_links"], [])
            self.assertEqual(resource["details_status"], "unverified")
            self.assertIsNone(resource["verified_date"])
            self.assertEqual(resource["withheld_links"][0]["url"], "http://changdongartvillage.kr/")

    def test_rejects_count_missing_fields_and_invalid_dates(self):
        resource = load_mission_resources()["M6-1"]
        resource["verified_date"] = "2026-02-30"
        self._assert_invalid(resource, "verified_date")
        resource.pop("summary")
        self._assert_invalid(resource, "missing fields")
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "resources.json"
            path.write_text(json.dumps({"count": 2, "items": []}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "count"):
                load_mission_resources(path)


if __name__ == "__main__":
    unittest.main()
