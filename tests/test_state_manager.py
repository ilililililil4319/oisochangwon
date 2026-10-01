import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from state_manager import load_mission_states, save_mission_state


class MissionStateStorageTests(unittest.TestCase):
    def test_creates_storage_and_reloads_state(self):
        with TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "storage" / "progress.sqlite3"

            save_mission_state("  코디세이 ", "confirm-move-in-date", True, database)

            self.assertTrue(database.is_file())
            self.assertEqual(
                load_mission_states("코디세이", database),
                {"confirm-move-in-date": True},
            )

    def test_updates_state_and_isolates_nicknames(self):
        with TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "progress.sqlite3"
            save_mission_state("사용자 A", "mission-1", True, database)
            save_mission_state("사용자 A", "mission-1", False, database)
            save_mission_state("사용자 B", "mission-1", True, database)

            self.assertEqual(
                load_mission_states("사용자 A", database),
                {"mission-1": False},
            )
            self.assertEqual(
                load_mission_states("사용자 B", database),
                {"mission-1": True},
            )

    def test_rejects_empty_identity_and_non_boolean_state(self):
        with TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "progress.sqlite3"

            with self.assertRaises(ValueError):
                load_mission_states("  ", database)
            with self.assertRaises(TypeError):
                save_mission_state("nickname", "mission-1", 1, database)


if __name__ == "__main__":
    unittest.main()
