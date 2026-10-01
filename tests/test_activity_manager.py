import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from activity_manager import (
    activity_view,
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
        view = activity_view(without_official_url)

        self.assertIsNone(view["official_url"])
        self.assertTrue(view["directions_url"].startswith("https://"))

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
