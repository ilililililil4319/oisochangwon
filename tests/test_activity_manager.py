import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import json
import unittest
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, quote, unquote, urlsplit

from activity_manager import (
    activity_view,
    activity_introduction,
    build_naver_map_search_web_url,
    build_naver_map_search_app_url,
    classify_activity_url,
    filter_activities,
    get_activity_filter_options,
    load_activities,
)


from naver_map_links import map_search_name


class ActivityManagerTests(unittest.TestCase):
    def test_loads_all_curated_activities_with_unique_ids(self):
        activities = load_activities()

        self.assertEqual(len(activities), 60)
        self.assertEqual(len({activity["ID"] for activity in activities}), 60)
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
            build_naver_map_search_web_url(without_official_url["이름"], without_official_url["생활권(구)"]),
        )
        self.assertTrue(view["naver_map_search_app_url"].startswith("nmap://search?"))

    def test_web_map_links_for_all_activities_and_korean_place_names(self):
        activities = load_activities()
        self.assertEqual(len(activities), 60)
        for activity in activities:
            with self.subTest(activity_id=activity["ID"]):
                url = activity_view(activity, "http://localhost:8501")["naver_map_url"]
                parsed = urlsplit(url)
                self.assertEqual(parsed.scheme, "https")
                self.assertEqual(parsed.hostname, "map.naver.com")
                self.assertTrue(url.startswith("https://map.naver.com/p/search/"))
                self.assertIn(quote(map_search_name(activity["이름"]), safe=""), url)
                self.assertFalse(parsed.query)
        for name in ("경남도립미술관", "시민생활체육관 (창원)", "창원 청년비전센터"):
            with self.subTest(name=name):
                activity = dict(activities[0], 이름=name)
                url = activity_view(activity, "http://localhost:8501")["naver_map_url"]
                self.assertIn(quote(map_search_name(name), safe=""), url)
                self.assertNotIn(" ", url)
                self.assertIn(map_search_name(name), unquote(url))

    def test_representative_search_queries_and_no_invented_coordinates(self):
        for name, district in (("시민생활체육관", "성산구"), ("스파더스페이스", "마산합포구"), ("경남도립미술관", "의창구")):
            parsed = urlsplit(build_naver_map_search_web_url(name, district))
            self.assertEqual(parsed.scheme, "https")
            self.assertTrue(parsed.path.startswith("/p/search/"))
            self.assertEqual(parsed.path, "/p/search/" + quote(f"{name} 창원", safe=""))
            query = unquote(parsed.path.removeprefix("/p/search/"))
            self.assertIn(name, query)
            self.assertIn("창원", query)
            self.assertNotIn(district, query)
            self.assertFalse(parsed.query)
            self.assertFalse(parsed.fragment)
        self.assertEqual(build_naver_map_search_web_url(""), "https://map.naver.com/p/")

    def test_existing_place_link_precedes_search_and_home_link_does_not(self):
        activity = dict(load_activities()[0])
        # Synthetic fixture: verifies preservation, not a claim that this place exists.
        activity["대중교통 접근(검수)"] = "https://map.naver.com/p/entry/place/123"
        self.assertEqual(activity_view(activity, "http://localhost:8501")["naver_map_url"], activity["대중교통 접근(검수)"])
        activity["대중교통 접근(검수)"] = "https://map.naver.com/p/"
        self.assertIn("/p/search/", activity_view(activity, "http://localhost:8501")["naver_map_url"])

    def test_short_map_names_preserve_display_names_and_use_recorded_venues(self):
        expected = {"A29": "스펀지파크", "A31": "3·15해양누리공원", "A35": "경남도립미술관",
                    "A39": "창원체육관", "A40": "창동예술촌", "A83": "스펀지파크",
                    "A140": "용지문화공원", "A151": "도계부부시장", "A165": "창원컨벤션센터"}
        for activity in load_activities():
            with self.subTest(activity=activity["ID"]):
                view = activity_view(activity, "http://localhost:8501")
                name = view["map_search_name"]
                self.assertTrue(name)
                self.assertEqual(view["name"], activity["이름"])
                self.assertNotIn("(", name)
                self.assertLessEqual(len(name), 30)
                if activity["ID"] in expected:
                    self.assertEqual(name, expected[activity["ID"]])
                    evidence = " ".join(str(activity.get(k, "")) for k in ("이름", "메모", "생활권(구)", "연락처", "출처"))
                    self.assertIn(name, evidence)
                query = unquote(urlsplit(view["naver_map_url"]).path.removeprefix("/p/search/"))
                self.assertEqual(query, name if "창원" in name else name + " 창원")
        self.assertEqual(map_search_name("스펀지파크(청년문화예술복합공간)"), "스펀지파크")
        self.assertEqual(map_search_name("장소 (설명 (추가))"), "장소")
        self.assertEqual(map_search_name(None), "")

    def test_introductions_only_use_recorded_tags_and_types(self):
        for activity in load_activities():
            intro = activity_introduction(activity)
            self.assertTrue(intro.strip())
            self.assertLess(len(intro), 120)
            self.assertEqual(intro.count("."), 1)
            self.assertNotIn("최고", intro)
            self.assertNotIn("인기 명소", intro)
            tags = [tag.strip() for tag in activity["관심사 태그"].split(",") if tag.strip()]
            if intro.startswith("온천·"):
                self.assertTrue(all(tag in tags for tag in ("온천", "찜질방", "인피니티풀")))
            elif "미술관이에요" in intro:
                self.assertIn("미술", tags)
                self.assertTrue(activity["이름"].endswith("미술관"))
            else:
                for tag in tags[:3]:
                    self.assertIn(tag, intro)
                self.assertIn(activity["유형(행사/모임/기관/공간)"], intro)
        plain = dict(load_activities()[0], 이름="알 수 없는 장소", **{"관심사 태그": "휴식"})
        self.assertNotIn("온천", activity_introduction(plain))

    def test_all_60_activity_views_always_supply_introduction(self):
        activities = load_activities()
        self.assertEqual(len(activities), 60)
        for activity in activities:
            with self.subTest(activity_id=activity["ID"]):
                view = activity_view(activity, "http://localhost:8501")
                self.assertIsInstance(view["introduction"], str)
                self.assertTrue(view["introduction"].strip())
        self.assertEqual(activity_introduction({}), "")
        self.assertEqual(activity_introduction({"이름": None, "관심사 태그": None, "MVP 그룹": None}), "")

    def test_classifies_all_60_source_links(self):
        activities = load_activities()
        classifications = Counter(
            classify_activity_url(activity["공식 URL"])["classification"]
            for activity in activities
        )

        self.assertEqual(len(activities), 60)
        self.assertEqual(
            classifications,
            {
                "public_official": 18,
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
            32,
        )

    def test_withholds_changdong_venue_without_valid_https(self):
        for url in ("http://changdongartvillage.kr/", "https://changdongartvillage.kr/"):
            result = classify_activity_url(url)
            self.assertEqual(result["classification"], "operator_official")
            self.assertFalse(result["is_official"])
            self.assertIsNone(result["url"])
            self.assertIsNone(result["label"])

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
        self.assertIn(map_search_name(activity["이름"]), unquote(view["naver_map_url"]))

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
