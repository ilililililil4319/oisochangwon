import json
import unittest
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlsplit

from activity_manager import (
    activity_view,
    build_naver_map_search_app_url,
    classify_activity_url,
    filter_activities,
    get_activity_filter_options,
    load_activities,
)


class ActivityManagerTests(unittest.TestCase):
    def test_loads_all_curated_activities_with_unique_ids(self):
        activities = load_activities()

        self.assertEqual(len(activities), 58)
        self.assertEqual(len({activity["ID"] for activity in activities}), 58)
        self.assertTrue(all(activity["MVP 선별"] == "O" for activity in activities))

    def test_filters_by_actual_district_and_category(self):
        activities = load_activities()
        options = get_activity_filter_options(activities)
        district = options["districts"][0]
        category = options["categories"][0]

        district_results = filter_activities(activities, district=district)
        category_results = filter_activities(activities, category=category)

        self.assertTrue(district_results)
        self.assertTrue(
            all(district in item["생활권(구)"] for item in district_results)
        )
        self.assertTrue(category_results)
        self.assertTrue(
            all(item["MVP 그룹"] == category for item in category_results)
        )

    def test_no_filters_returns_all_activities(self):
        activities = load_activities()

        self.assertEqual(filter_activities(activities), activities)

    def test_view_only_returns_verified_links(self):
        activities = load_activities()
        without_official_url = next(
            item for item in activities if item["ID"] == "A56"
        )
        view = activity_view(without_official_url, "http://localhost:8501")

        self.assertIsNone(view["official_url"])
        self.assertEqual(
            view["naver_map_url"],
            "https://map.naver.com/p/",
        )
        self.assertTrue(view["naver_map_search_app_url"].startswith("nmap://search?"))

    def test_classifies_all_58_source_links(self):
        activities = load_activities()
        classifications = Counter(
            classify_activity_url(activity["공식 URL"])["classification"]
            for activity in activities
        )

        self.assertEqual(len(activities), 58)
        self.assertEqual(
            classifications,
            {
                "public_official": 16,
                "operator_official": 15,
                "news": 4,
                "directory": 14,
                "encyclopedia": 1,
                "unverified_social": 1,
                "blog": 1,
                "unverified": 3,
                "no_link": 3,
            },
        )
        self.assertEqual(
            sum(classify_activity_url(item["공식 URL"])["is_official"] for item in activities),
            31,
        )

    def test_every_existing_activity_url_has_an_http_scheme(self):
        for activity in load_activities():
            with self.subTest(activity_id=activity["ID"]):
                classification = classify_activity_url(activity["공식 URL"])
                if classification["classification"] == "no_link":
                    self.assertFalse(activity["공식 URL"].startswith(("http://", "https://")))
                    continue
                parsed_url = urlsplit(activity["공식 URL"].split()[0])
                self.assertIn(parsed_url.scheme, {"http", "https"})
                self.assertTrue(parsed_url.netloc)

    def test_official_reservation_links_use_reservation_label(self):
        result = classify_activity_url("https://www.cwsisul.or.kr/reserve/facility")

        self.assertTrue(result["is_official"])
        self.assertEqual(result["label"], "예약·이용 안내 보기")

    def test_naver_search_does_not_use_original_kakao_route(self):
        activity = load_activities()[0]
        view = activity_view(activity, "http://localhost:8501")
        parsed_url = urlsplit(view["naver_map_search_app_url"])
        query = parse_qs(parsed_url.query)

        self.assertEqual(parsed_url.scheme, "nmap")
        self.assertEqual(parsed_url.netloc, "search")
        self.assertEqual(query["query"], [activity["이름"]])
        self.assertEqual(query["appname"], ["http://localhost:8501"])
        self.assertNotIn("lat", query)
        self.assertNotIn("lng", query)
        self.assertEqual(view["naver_map_url"], "https://map.naver.com/p/")

    def test_nonofficial_links_are_never_returned_as_official(self):
        untrusted_urls = (
            "https://namu.wiki/w/Example",
            "https://mirimblog.com/post",
            "https://www.facebook.com/example",
            "https://www.diningcode.com/profile.php?rid=1",
        )

        for url in untrusted_urls:
            with self.subTest(url=url):
                result = classify_activity_url(url)
                self.assertFalse(result["is_official"])
                self.assertIsNone(result["url"])
                self.assertIsNone(result["label"])

    def test_public_and_operator_sites_receive_official_labels(self):
        public_link = classify_activity_url("https://www.changwon.go.kr/youth/")
        operator_link = classify_activity_url("https://www.cwsisul.or.kr/")

        self.assertEqual(public_link["label"], "공식 안내 보기")
        self.assertEqual(operator_link["label"], "공식 안내 보기")
        self.assertTrue(public_link["is_official"])
        self.assertTrue(operator_link["is_official"])

    def test_unverified_map_domains_are_not_official_links(self):
        map_link = classify_activity_url("https://map.naver.com/p/")

        self.assertEqual(map_link["classification"], "naver_map")
        self.assertFalse(map_link["is_official"])
        self.assertIsNone(map_link["url"])

    def test_naver_search_link_uses_only_documented_query_without_coordinates(self):
        url = build_naver_map_search_app_url(
            "창원 체육관",
            "http://localhost:8501",
        )

        self.assertTrue(url.startswith("nmap://search?"))
        self.assertIn("query=%EC%B0%BD%EC%9B%90+%EC%B2%B4%EC%9C%A1%EA%B4%80", url)
        self.assertIn("appname=http%3A%2F%2Flocalhost%3A8501", url)
        self.assertNotIn("lat=", url)
        self.assertNotIn("lng=", url)

    def test_rejects_count_mismatch_and_duplicate_ids(self):
        activity = load_activities()[0]
        with TemporaryDirectory() as temp_dir:
            data_path = Path(temp_dir) / "activities.json"

            data_path.write_text(
                json.dumps({"count": 2, "items": []}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "count"):
                load_activities(data_path)

            data_path.write_text(
                json.dumps({"count": 2, "items": [activity, activity]}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "duplicate activity ID"):
                load_activities(data_path)

    def test_rejects_missing_required_fields(self):
        activity = load_activities()[0]
        del activity["이름"]
        with TemporaryDirectory() as temp_dir:
            data_path = Path(temp_dir) / "activities.json"
            data_path.write_text(
                json.dumps({"count": 1, "items": [activity]}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "missing fields"):
                load_activities(data_path)


if __name__ == "__main__":
    unittest.main()
