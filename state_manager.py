import sqlite3
from contextlib import closing
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent / "storage" / "progress.sqlite3"


def _normalize_identifier(value, field_name):
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")

    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _connect(db_path=None):
    path = DB_PATH if db_path is None else Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(str(path))
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS mission_progress (
            nickname TEXT NOT NULL,
            mission_id TEXT NOT NULL,
            completed INTEGER NOT NULL CHECK (completed IN (0, 1)),
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (nickname, mission_id)
        )
        """
    )
    connection.commit()
    return connection


def load_mission_states(nickname, db_path=None):
    normalized_nickname = _normalize_identifier(nickname, "nickname")
    with closing(_connect(db_path)) as connection:
        rows = connection.execute(
            """
            SELECT mission_id, completed
            FROM mission_progress
            WHERE nickname = ?
            """,
            (normalized_nickname,),
        ).fetchall()

    return {mission_id: bool(completed) for mission_id, completed in rows}


def save_mission_state(nickname, mission_id, completed, db_path=None):
    normalized_nickname = _normalize_identifier(nickname, "nickname")
    normalized_mission_id = _normalize_identifier(mission_id, "mission_id")
    if not isinstance(completed, bool):
        raise TypeError("completed must be a bool")

    with closing(_connect(db_path)) as connection:
        connection.execute(
            """
            INSERT INTO mission_progress (nickname, mission_id, completed)
            VALUES (?, ?, ?)
            ON CONFLICT (nickname, mission_id) DO UPDATE SET
                completed = excluded.completed,
                updated_at = CURRENT_TIMESTAMP
            """,
            (normalized_nickname, normalized_mission_id, int(completed)),
        )
        connection.commit()
