import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


DB_PATH = Path(__file__).resolve().parent / "storage" / "progress.sqlite3"
KOREA_TIMEZONE = ZoneInfo("Asia/Seoul")


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
            note TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (nickname, mission_id)
        )
        """
    )
    columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(mission_progress)")
    }
    if "note" not in columns:
        connection.execute(
            "ALTER TABLE mission_progress ADD COLUMN note TEXT NOT NULL DEFAULT ''"
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
            INSERT INTO mission_progress (
                nickname, mission_id, completed, updated_at, note
            )
            VALUES (?, ?, ?, ?, '')
            ON CONFLICT (nickname, mission_id) DO UPDATE SET
                completed = excluded.completed,
                updated_at = excluded.updated_at
            """,
            (
                normalized_nickname,
                normalized_mission_id,
                int(completed),
                _korea_timestamp(),
            ),
        )
        connection.commit()


def load_mission_notes(nickname, db_path=None):
    normalized_nickname = _normalize_identifier(nickname, "nickname")
    with closing(_connect(db_path)) as connection:
        rows = connection.execute(
            """
            SELECT mission_id, note
            FROM mission_progress
            WHERE nickname = ?
            """,
            (normalized_nickname,),
        ).fetchall()

    return {mission_id: note for mission_id, note in rows}


def load_mission_timestamps(nickname, db_path=None):
    normalized_nickname = _normalize_identifier(nickname, "nickname")
    with closing(_connect(db_path)) as connection:
        rows = connection.execute(
            """
            SELECT mission_id, updated_at
            FROM mission_progress
            WHERE nickname = ?
            """,
            (normalized_nickname,),
        ).fetchall()

    return {mission_id: updated_at for mission_id, updated_at in rows}


def save_mission_group(nickname, progress, db_path=None):
    """Save one stage's completion and note values in a single transaction."""
    normalized_nickname = _normalize_identifier(nickname, "nickname")
    if not isinstance(progress, dict) or not progress:
        raise ValueError("progress must be a non-empty mapping")

    saved_at = _korea_timestamp()
    rows = []
    for mission_id, values in progress.items():
        normalized_mission_id = _normalize_identifier(mission_id, "mission_id")
        if not isinstance(values, dict):
            raise TypeError("each progress value must be a mapping")
        completed = values.get("completed")
        note = values.get("note", "")
        if not isinstance(completed, bool):
            raise TypeError("completed must be a bool")
        if not isinstance(note, str):
            raise TypeError("note must be a string")
        rows.append(
            (
                normalized_nickname,
                normalized_mission_id,
                int(completed),
                saved_at,
                note,
            )
        )

    with closing(_connect(db_path)) as connection:
        with connection:
            connection.executemany(
                """
                INSERT INTO mission_progress (
                    nickname, mission_id, completed, updated_at, note
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (nickname, mission_id) DO UPDATE SET
                    completed = excluded.completed,
                    updated_at = excluded.updated_at,
                    note = excluded.note
                """,
                rows,
            )

    return saved_at


def format_korea_timestamp(value):
    if not isinstance(value, str) or not value:
        return None

    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError:
        return None

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(KOREA_TIMEZONE).strftime("%Y-%m-%d %H:%M")


def _korea_timestamp():
    return datetime.now(KOREA_TIMEZONE).isoformat(timespec="minutes")
