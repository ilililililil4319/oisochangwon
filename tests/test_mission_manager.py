import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import json
import unittest
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

from mission_manager import group_missions_by_month, load_missions


class MissionManagerTests(unittest.TestCase):
    def test_loads_and_groups_all_source_missions(self):
        missions = load_missions()
        groups = group_missions_by_month(missions)

        self.assertEqual(len(missions), 26)
        self.assertEqual(len({mission["ID"] for mission in missions}), 26)
        self.assertEqual(missions[0]["ID"], "M1-1")
        self.assertEqual(missions[-1]["ID"], "M6-5")
        self.assertEqual(
            [group["month"] for group in groups],
            [1, 2, 3, 4, 5, 6],
        )
        self.assertEqual(
            [len(group["missions"]) for group in groups],
            [5, 3, 5, 4, 4, 5],
        )
        self.assertEqual(
            Counter(mission["연결 기능"] for mission in missions),
            {
                "Mission Tool": 2,
                "Policy Tool": 8,
                "Local Activity Tool": 11,
                "Dialect Tool": 4,
                "Complaint Tool": 1,
            },
        )
        self.assertTrue(
            all("완료 기준" in mission and "메모" in mission for mission in missions)
        )

    def test_rejects_declared_count_mismatch(self):
        with TemporaryDirectory() as temp_dir:
            invalid_data = {"count": 2, "items": []}
            data_path = Path(temp_dir) / "missions.json"
            data_path.write_text(json.dumps(invalid_data), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "count"):
                load_missions(data_path)

    def test_rejects_duplicate_source_ids(self):
        with TemporaryDirectory() as temp_dir:
            mission = load_missions()[0]
            invalid_data = {"count": 2, "items": [mission, mission]}
            data_path = Path(temp_dir) / "missions.json"
            data_path.write_text(json.dumps(invalid_data), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "duplicate mission ID"):
                load_missions(data_path)


if __name__ == "__main__":
    unittest.main()
