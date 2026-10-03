import os
import sqlite3
import uuid
from datetime import datetime, timezone

from app.models.work import Work


class SQLiteWorkRepository:
    def __init__(self, db_path="data/reader.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._create_schema()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _create_schema(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS works (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    progress_unit TEXT NOT NULL,
                    progress_current INTEGER NOT NULL DEFAULT 0,
                    progress_total INTEGER,
                    status TEXT NOT NULL DEFAULT 'Quero ler',
                    release_day TEXT,
                    synopsis TEXT NOT NULL DEFAULT '',
                    rating INTEGER,
                    favorite INTEGER NOT NULL DEFAULT 0,
                    personal_notes TEXT NOT NULL DEFAULT '',
                    start_date TEXT,
                    end_date TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    deleted_at TEXT,
                    sync_status TEXT NOT NULL DEFAULT 'PENDING_CREATE'
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS work_tags (
                    work_id TEXT NOT NULL,
                    tag TEXT NOT NULL,
                    PRIMARY KEY (work_id, tag)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id TEXT PRIMARY KEY,
                    work_id TEXT NOT NULL,
                    description TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    sync_status TEXT NOT NULL DEFAULT 'PENDING_CREATE'
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS goals (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    goal_type TEXT NOT NULL,
                    target_value INTEGER NOT NULL,
                    current_value INTEGER NOT NULL DEFAULT 0,
                    start_date TEXT,
                    end_date TEXT,
                    created_at TEXT NOT NULL
                )
            """)

            self._ensure_column(conn, "works", "rating", "INTEGER")
            self._ensure_column(conn, "works", "favorite", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "works", "personal_notes", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "works", "start_date", "TEXT")
            self._ensure_column(conn, "works", "end_date", "TEXT")

    def _ensure_column(self, conn, table, column, definition):
        columns = {
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in columns:
            conn.execute(
                f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
            )

    def list_all(self):
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT
                    id, name, category, progress_unit,
                    progress_current, progress_total,
                    status, release_day, synopsis,
                    rating, favorite, personal_notes,
                    start_date, end_date,
                    created_at, updated_at
                FROM works
                WHERE deleted_at IS NULL
                ORDER BY favorite DESC, updated_at DESC
            """).fetchall()

        result = []
        for row in rows:
            data = dict(row)
            data["favorite"] = bool(data["favorite"])
            result.append(Work(**data))
        return result

    def get_by_id(self, work_id):
        with self._connect() as conn:
            row = conn.execute("""
                SELECT
                    id, name, category, progress_unit,
                    progress_current, progress_total,
                    status, release_day, synopsis,
                    rating, favorite, personal_notes,
                    start_date, end_date,
                    created_at, updated_at
                FROM works
                WHERE id = ? AND deleted_at IS NULL
            """, (work_id,)).fetchone()

        if row is None:
            return None

        data = dict(row)
        data["favorite"] = bool(data["favorite"])
        return Work(**data)

    def create(
        self,
        name,
        category,
        progress_unit,
        progress_current=0,
        progress_total=None,
        status="Quero ler",
        release_day=None,
        synopsis="",
        rating=None,
        favorite=False,
        personal_notes="",
        start_date=None,
        end_date=None,
    ):
        now = datetime.now(timezone.utc).isoformat()

        work = Work(
            id=str(uuid.uuid4()),
            name=name,
            category=category,
            progress_unit=progress_unit,
            progress_current=progress_current,
            progress_total=progress_total,
            status=status,
            release_day=release_day,
            synopsis=synopsis,
            rating=rating,
            favorite=favorite,
            personal_notes=personal_notes,
            start_date=start_date,
            end_date=end_date,
            created_at=now,
            updated_at=now,
        )

        with self._connect() as conn:
            conn.execute("""
                INSERT INTO works (
                    id, name, category, progress_unit,
                    progress_current, progress_total, status,
                    release_day, synopsis, rating, favorite,
                    personal_notes, start_date, end_date,
                    created_at, updated_at, sync_status
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    'PENDING_CREATE'
                )
            """, (
                work.id,
                work.name,
                work.category,
                work.progress_unit,
                work.progress_current,
                work.progress_total,
                work.status,
                work.release_day,
                work.synopsis,
                work.rating,
                int(work.favorite),
                work.personal_notes,
                work.start_date,
                work.end_date,
                work.created_at,
                work.updated_at,
            ))

        return work

    def increment_progress(self, work_id, amount=1):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM works WHERE id = ?",
                (work_id,),
            ).fetchone()

            if row is None:
                raise ValueError("Obra não encontrada.")

            old_value = row["progress_current"]
            new_value = old_value + amount
            now = datetime.now(timezone.utc).isoformat()

            next_sync = (
                "PENDING_CREATE"
                if row["sync_status"] == "PENDING_CREATE"
                else "PENDING_UPDATE"
            )

            conn.execute("""
                UPDATE works
                SET progress_current = ?,
                    updated_at = ?,
                    sync_status = ?
                WHERE id = ?
            """, (
                new_value,
                now,
                next_sync,
                work_id,
            ))

            conn.execute("""
                INSERT INTO history (
                    id, work_id, description,
                    created_at, sync_status
                )
                VALUES (?, ?, ?, ?, 'PENDING_CREATE')
            """, (
                str(uuid.uuid4()),
                work_id,
                f"Progresso: {old_value} → {new_value}",
                now,
            ))

    def set_reading_dates(self, work_id, start_date=None, end_date=None):
        with self._connect() as conn:
            conn.execute("""
                UPDATE works
                SET start_date = ?,
                    end_date = ?,
                    updated_at = ?,
                    sync_status = 'PENDING_UPDATE'
                WHERE id = ?
            """, (
                start_date or None,
                end_date or None,
                datetime.now(timezone.utc).isoformat(),
                work_id,
            ))

    def set_favorite(self, work_id, favorite):
        self._update_metadata(work_id, favorite=int(bool(favorite)))

    def set_rating(self, work_id, rating):
        if rating not in (1, 2, 3, 4, 5):
            raise ValueError("A avaliação deve estar entre 1 e 5.")
        self._update_metadata(work_id, rating=rating)

    def set_notes(self, work_id, notes):
        self._update_metadata(work_id, personal_notes=notes)

    def _update_metadata(self, work_id, **fields):
        allowed = {"favorite", "rating", "personal_notes"}
        invalid = set(fields) - allowed
        if invalid:
            raise ValueError(f"Campos inválidos: {sorted(invalid)}")

        now = datetime.now(timezone.utc).isoformat()
        assignments = [f"{name} = ?" for name in fields]
        values = list(fields.values())

        assignments.extend([
            "updated_at = ?",
            "sync_status = 'PENDING_UPDATE'",
        ])
        values.extend([now, work_id])

        with self._connect() as conn:
            conn.execute(
                f"""
                UPDATE works
                SET {", ".join(assignments)}
                WHERE id = ?
                """,
                values,
            )

    def get_tags(self, work_id):
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT tag
                FROM work_tags
                WHERE work_id = ?
                ORDER BY tag
            """, (work_id,)).fetchall()

        return [row["tag"] for row in rows]

    def set_tags(self, work_id, tags):
        clean_tags = sorted({
            tag.strip()
            for tag in tags
            if tag.strip()
        })

        with self._connect() as conn:
            conn.execute(
                "DELETE FROM work_tags WHERE work_id = ?",
                (work_id,),
            )
            for tag in clean_tags:
                conn.execute("""
                    INSERT INTO work_tags (work_id, tag)
                    VALUES (?, ?)
                """, (work_id, tag))

            conn.execute("""
                UPDATE works
                SET updated_at = ?,
                    sync_status = 'PENDING_UPDATE'
                WHERE id = ?
            """, (
                datetime.now(timezone.utc).isoformat(),
                work_id,
            ))

    def create_goal(
        self,
        title,
        goal_type,
        target_value,
        start_date=None,
        end_date=None,
    ):
        goal_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            conn.execute("""
                INSERT INTO goals (
                    id, title, goal_type, target_value,
                    current_value, start_date, end_date, created_at
                )
                VALUES (?, ?, ?, ?, 0, ?, ?, ?)
            """, (
                goal_id,
                title,
                goal_type,
                target_value,
                start_date,
                end_date,
                now,
            ))

        return goal_id

    def list_goals(self):
        with self._connect() as conn:
            return [
                dict(row)
                for row in conn.execute("""
                    SELECT *
                    FROM goals
                    ORDER BY created_at DESC
                """).fetchall()
            ]

    def update_goal_progress(self, goal_id, current_value):
        with self._connect() as conn:
            conn.execute("""
                UPDATE goals
                SET current_value = ?
                WHERE id = ?
            """, (
                current_value,
                goal_id,
            ))

    def list_calendar_events(self):
        events = []
        for work in self.list_all():
            if work.start_date:
                events.append({
                    "date": work.start_date,
                    "type": "Início",
                    "title": work.name,
                })
            if work.end_date:
                events.append({
                    "date": work.end_date,
                    "type": "Conclusão",
                    "title": work.name,
                })

        return sorted(
            events,
            key=lambda item: item["date"],
        )

    def export_payload(self):
        with self._connect() as conn:
            works = [dict(row) for row in conn.execute("SELECT * FROM works").fetchall()]
            history = [dict(row) for row in conn.execute("SELECT * FROM history").fetchall()]
            tags = [dict(row) for row in conn.execute("SELECT * FROM work_tags").fetchall()]
            goals = [dict(row) for row in conn.execute("SELECT * FROM goals").fetchall()]

        return {
            "schema_version": 3,
            "works": works,
            "history": history,
            "tags": tags,
            "goals": goals,
        }

    def replace_from_payload(self, payload):
        works = payload.get("works", [])
        history = payload.get("history", [])
        tags = payload.get("tags", [])
        goals = payload.get("goals", [])

        with self._connect() as conn:
            conn.execute("DELETE FROM work_tags")
            conn.execute("DELETE FROM history")
            conn.execute("DELETE FROM goals")
            conn.execute("DELETE FROM works")

            for item in works:
                conn.execute("""
                    INSERT INTO works (
                        id, name, category, progress_unit,
                        progress_current, progress_total, status,
                        release_day, synopsis, rating, favorite,
                        personal_notes, start_date, end_date,
                        created_at, updated_at, deleted_at, sync_status
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                """, (
                    item["id"],
                    item["name"],
                    item["category"],
                    item["progress_unit"],
                    item.get("progress_current", 0),
                    item.get("progress_total"),
                    item.get("status", "Quero ler"),
                    item.get("release_day"),
                    item.get("synopsis", ""),
                    item.get("rating"),
                    item.get("favorite", 0),
                    item.get("personal_notes", ""),
                    item.get("start_date"),
                    item.get("end_date"),
                    item["created_at"],
                    item["updated_at"],
                    item.get("deleted_at"),
                    item.get("sync_status", "SYNCED"),
                ))

            for item in history:
                conn.execute("""
                    INSERT INTO history (
                        id, work_id, description,
                        created_at, sync_status
                    )
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    item["id"],
                    item["work_id"],
                    item["description"],
                    item["created_at"],
                    item.get("sync_status", "SYNCED"),
                ))

            for item in tags:
                conn.execute("""
                    INSERT INTO work_tags (work_id, tag)
                    VALUES (?, ?)
                """, (
                    item["work_id"],
                    item["tag"],
                ))

            for item in goals:
                conn.execute("""
                    INSERT INTO goals (
                        id, title, goal_type, target_value,
                        current_value, start_date, end_date, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    item["id"],
                    item["title"],
                    item["goal_type"],
                    item["target_value"],
                    item.get("current_value", 0),
                    item.get("start_date"),
                    item.get("end_date"),
                    item["created_at"],
                ))
