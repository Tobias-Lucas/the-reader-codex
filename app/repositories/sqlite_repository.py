
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
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id TEXT PRIMARY KEY,
                    work_id TEXT NOT NULL,
                    description TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(work_id) REFERENCES works(id)
                )
            """)

    def list_all(self):
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM works ORDER BY updated_at DESC"
            ).fetchall()
        return [Work(**dict(row)) for row in rows]

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
            created_at=now,
            updated_at=now,
        )

        with self._connect() as conn:
            conn.execute("""
                INSERT INTO works (
                    id, name, category, progress_unit,
                    progress_current, progress_total, status,
                    release_day, synopsis, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

            conn.execute("""
                UPDATE works
                SET progress_current = ?, updated_at = ?
                WHERE id = ?
            """, (new_value, now, work_id))

            conn.execute("""
                INSERT INTO history (id, work_id, description, created_at)
                VALUES (?, ?, ?, ?)
            """, (
                str(uuid.uuid4()),
                work_id,
                f"Progresso: {old_value} → {new_value}",
                now,
            ))
