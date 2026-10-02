import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import re

from state_manager import (
    format_korea_timestamp,
    load_mission_notes,
    load_mission_states,
    load_mission_timestamps,
    save_mission_group,
    save_mission_state,
)


class MissionStateStorageTests(unittest.TestCase):
    def test_creates_storage_and_reloads_state(self):
        with TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "storage" / "progress.sqlite3"

            save_mission_state("  코디2026 ", "confirm-move-in-date", True, database)

            self.assertTrue(database.is_file())
            self.assertEqual(
                load_mission_states("코디2026", database),
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

    def test_migrates_legacy_database_and_preserves_completion(self):
        with TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "storage" / "progress.sqlite3"
            database.parent.mkdir(parents=True)
            connection = sqlite3.connect(database)
            try:
                connection.execute(
                    """
                    CREATE TABLE mission_progress (
                        nickname TEXT NOT NULL,
                        mission_id TEXT NOT NULL,
                        completed INTEGER NOT NULL CHECK (completed IN (0, 1)),
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (nickname, mission_id)
                    )
                    """
                )
                connection.execute(
                    """
                    INSERT INTO mission_progress (
                        nickname, mission_id, completed, updated_at
                    ) VALUES (?, ?, ?, ?)
                    """,
                    ("기존 사용자", "M1-1", 1, "2026-10-01 00:00:00"),
                )
                connection.commit()
            finally:
                connection.close()

            self.assertEqual(
                load_mission_states("기존 사용자", database),
                {"M1-1": True},
            )
            self.assertEqual(
                load_mission_notes("기존 사용자", database),
                {"M1-1": ""},
            )
            with closing(sqlite3.connect(database)) as connection:
                columns = {
                    row[1]
                    for row in connection.execute(
                        "PRAGMA table_info(mission_progress)"
                    )
                }
            self.assertIn("note", columns)

    def test_saves_stage_notes_and_korea_timestamp_together(self):
        with TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "progress.sqlite3"
            saved_at = save_mission_group(
                "사용자",
                {
                    "M1-1": {"completed": True, "note": "주민센터 방문"},
                    "M1-2": {"completed": False, "note": "지원 목록 확인"},
                },
                database,
            )

            self.assertEqual(
                load_mission_states("사용자", database),
                {"M1-1": True, "M1-2": False},
            )
            self.assertEqual(
                load_mission_notes("사용자", database),
                {"M1-1": "주민센터 방문", "M1-2": "지원 목록 확인"},
            )
            self.assertTrue(saved_at.endswith("+09:00"))
            self.assertTrue(
                re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", format_korea_timestamp(saved_at))
            )
            self.assertEqual(
                load_mission_timestamps("사용자", database),
                {"M1-1": saved_at, "M1-2": saved_at},
            )

    def test_stage_save_keeps_nickname_notes_separate(self):
        with TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "progress.sqlite3"
            save_mission_group(
                "사용자 A",
                {"M1-1": {"completed": True, "note": "A 기록"}},
                database,
            )
            save_mission_group(
                "사용자 B",
                {"M1-1": {"completed": False, "note": "B 기록"}},
                database,
            )

            self.assertEqual(load_mission_notes("사용자 A", database), {"M1-1": "A 기록"})
            self.assertEqual(load_mission_notes("사용자 B", database), {"M1-1": "B 기록"})


if __name__ == "__main__":
    unittest.main()
