
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
                    updated_at TEXT NOT NULL,
                    deleted_at TEXT,
                    sync_status TEXT NOT NULL DEFAULT 'PENDING_CREATE'
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

    def list_all(self):
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT
                    id, name, category, progress_unit,
                    progress_current, progress_total,
                    status, release_day, synopsis,
                    created_at, updated_at
                FROM works
                WHERE deleted_at IS NULL
                ORDER BY updated_at DESC
            """).fetchall()
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
                    release_day, synopsis, created_at, updated_at,
                    sync_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING_CREATE')
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

            current_sync = row["sync_status"]
            next_sync = (
                "PENDING_CREATE"
                if current_sync == "PENDING_CREATE"
                else "PENDING_UPDATE"
            )

            conn.execute("""
                UPDATE works
                SET progress_current = ?,
                    updated_at = ?,
                    sync_status = ?
                WHERE id = ?
            """, (new_value, now, next_sync, work_id))

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

    def get_pending_works(self):
        with self._connect() as conn:
            return conn.execute("""
                SELECT * FROM works
                WHERE sync_status <> 'SYNCED'
            """).fetchall()

    def mark_work_synced(self, work_id):
        with self._connect() as conn:
            conn.execute("""
                UPDATE works
                SET sync_status = 'SYNCED'
                WHERE id = ?
            """, (work_id,))

    def upsert_remote(self, payload):
        with self._connect() as conn:
            local = conn.execute(
                "SELECT * FROM works WHERE id = ?",
                (payload["id"],),
            ).fetchone()

            if local is None:
                conn.execute("""
                    INSERT INTO works (
                        id, name, category, progress_unit,
                        progress_current, progress_total, status,
                        release_day, synopsis, created_at, updated_at,
                        deleted_at, sync_status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'SYNCED')
                """, (
                    payload["id"],
                    payload["name"],
                    payload["category"],
                    payload["progress_unit"],
                    payload["progress_current"],
                    payload.get("progress_total"),
                    payload["status"],
                    payload.get("release_day"),
                    payload.get("synopsis", ""),
                    payload["created_at"],
                    payload["updated_at"],
                    payload.get("deleted_at"),
                ))
                return

            if payload["updated_at"] > local["updated_at"]:
                conn.execute("""
                    UPDATE works SET
                        name = ?,
                        category = ?,
                        progress_unit = ?,
                        progress_current = ?,
                        progress_total = ?,
                        status = ?,
                        release_day = ?,
                        synopsis = ?,
                        updated_at = ?,
                        deleted_at = ?,
                        sync_status = 'SYNCED'
                    WHERE id = ?
                """, (
                    payload["name"],
                    payload["category"],
                    payload["progress_unit"],
                    payload["progress_current"],
                    payload.get("progress_total"),
                    payload["status"],
                    payload.get("release_day"),
                    payload.get("synopsis", ""),
                    payload["updated_at"],
                    payload.get("deleted_at"),
                    payload["id"],
                ))
