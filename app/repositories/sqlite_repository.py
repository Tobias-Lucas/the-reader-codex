import os
import shutil
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path

from app.models.work import Work
from app.paths import COVERS_DIR, DB_PATH
from app.utils.dates import next_weekday_date, normalize_weekday


class SQLiteWorkRepository:
    STATUS_OPTIONS = ("Quero ler", "Lendo", "Pausado", "Concluído", "Abandonado")
    PROGRESS_UNITS = ("Página", "Capítulo")
    GOAL_TYPES = ("books", "pages", "chapters")
    SCHEMA_VERSION = 5

    def __init__(self, db_path=None, covers_dir=None):
        self.db_path = str(Path(db_path or DB_PATH).resolve())
        self.covers_dir = str(Path(covers_dir or COVERS_DIR).resolve())
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.covers_dir).mkdir(parents=True, exist_ok=True)
        self._create_schema()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _utcnow():
        return datetime.now(timezone.utc).isoformat()

    def _create_schema(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS works (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT '',
                    progress_unit TEXT NOT NULL DEFAULT 'Página',
                    progress_current INTEGER NOT NULL DEFAULT 0,
                    progress_total INTEGER,
                    status TEXT NOT NULL DEFAULT 'Quero ler',
                    release_day TEXT,
                    synopsis TEXT NOT NULL DEFAULT '',
                    rating REAL,
                    favorite INTEGER NOT NULL DEFAULT 0,
                    personal_notes TEXT NOT NULL DEFAULT '',
                    start_date TEXT,
                    end_date TEXT,
                    cover_path TEXT,
                    cover_remote_id TEXT,
                    cover_remote_name TEXT,
                    cover_remote_modified TEXT,
                    cover_deleted INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    deleted_at TEXT,
                    sync_status TEXT NOT NULL DEFAULT 'PENDING_CREATE'
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    name TEXT PRIMARY KEY COLLATE NOCASE,
                    created_at TEXT NOT NULL
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS work_tags (
                    work_id TEXT NOT NULL,
                    tag TEXT NOT NULL COLLATE NOCASE,
                    PRIMARY KEY (work_id, tag),
                    FOREIGN KEY (work_id) REFERENCES works(id) ON DELETE CASCADE
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id TEXT PRIMARY KEY,
                    work_id TEXT NOT NULL,
                    description TEXT NOT NULL,
                    event_type TEXT NOT NULL DEFAULT 'progress',
                    delta INTEGER,
                    progress_unit TEXT,
                    created_at TEXT NOT NULL,
                    sync_status TEXT NOT NULL DEFAULT 'PENDING_CREATE',
                    FOREIGN KEY (work_id) REFERENCES works(id) ON DELETE CASCADE
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
                    created_at TEXT NOT NULL,
                    updated_at TEXT,
                    deleted_at TEXT,
                    sync_status TEXT NOT NULL DEFAULT 'PENDING_CREATE'
                )
            """)

            # Migrations from earlier repository versions.
            for column, definition in [
                ("rating", "REAL"),
                ("favorite", "INTEGER NOT NULL DEFAULT 0"),
                ("personal_notes", "TEXT NOT NULL DEFAULT ''"),
                ("start_date", "TEXT"),
                ("end_date", "TEXT"),
                ("cover_path", "TEXT"),
                ("cover_remote_id", "TEXT"),
                ("cover_remote_name", "TEXT"),
                ("cover_remote_modified", "TEXT"),
                ("cover_deleted", "INTEGER NOT NULL DEFAULT 0"),
                ("deleted_at", "TEXT"),
                ("sync_status", "TEXT NOT NULL DEFAULT 'PENDING_CREATE'"),
            ]:
                self._ensure_column(conn, "works", column, definition)

            for column, definition in [
                ("id", "TEXT"),
                ("updated_at", "TEXT"),
                ("deleted_at", "TEXT"),
                ("sync_status", "TEXT NOT NULL DEFAULT 'PENDING_CREATE'"),
            ]:
                self._ensure_column(conn, "categories", column, definition)

            for column, definition in [
                ("event_type", "TEXT NOT NULL DEFAULT 'progress'"),
                ("delta", "INTEGER"),
                ("progress_unit", "TEXT"),
                ("sync_status", "TEXT NOT NULL DEFAULT 'PENDING_CREATE'"),
            ]:
                self._ensure_column(conn, "history", column, definition)

            for column, definition in [
                ("updated_at", "TEXT"),
                ("deleted_at", "TEXT"),
                ("sync_status", "TEXT NOT NULL DEFAULT 'PENDING_CREATE'"),
            ]:
                self._ensure_column(conn, "goals", column, definition)

            now = self._utcnow()
            conn.execute("UPDATE categories SET updated_at = COALESCE(updated_at, created_at, ?)", (now,))
            conn.execute("UPDATE goals SET updated_at = COALESCE(updated_at, created_at, ?)", (now,))

            category_rows = conn.execute("SELECT name, id FROM categories").fetchall()
            for row in category_rows:
                if not row["id"]:
                    conn.execute(
                        "UPDATE categories SET id = ? WHERE name = ? COLLATE NOCASE",
                        (str(uuid.uuid4()), row["name"]),
                    )
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_categories_id ON categories(id)")

            # Any category already present in an older database becomes manageable.
            conn.execute("""
                INSERT OR IGNORE INTO categories (name, created_at, id, updated_at, sync_status)
                SELECT DISTINCT TRIM(category), ?, lower(hex(randomblob(16))), ?, 'PENDING_CREATE'
                FROM works
                WHERE deleted_at IS NULL AND TRIM(category) <> ''
            """, (now, now))

            conn.execute("PRAGMA user_version = 5")

    @staticmethod
    def _ensure_column(conn, table, column, definition):
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _normalize_cover_path(self, value):
        if not value:
            return None
        path = Path(value)
        if not path.is_absolute():
            # Legacy databases stored data/covers/... relative to the project root.
            candidate = Path(self.db_path).parent.parent / path
            if candidate.exists():
                path = candidate
            else:
                candidate = Path(self.covers_dir) / path.name
                path = candidate
        return str(path.resolve())

    def _row_to_work(self, row):
        data = dict(row)
        data["favorite"] = bool(data["favorite"])
        if data.get("rating") is not None:
            data["rating"] = float(data["rating"])
        if "cover_path" in data:
            data["cover_path"] = self._normalize_cover_path(data.get("cover_path"))
        allowed = set(Work.__dataclass_fields__)
        return Work(**{key: value for key, value in data.items() if key in allowed})

    @staticmethod
    def _normalize_text(value):
        return (value or "").strip()

    @staticmethod
    def _validate_progress(progress_current, progress_total):
        if progress_current is None:
            progress_current = 0
        try:
            progress_current = int(progress_current)
        except (TypeError, ValueError) as exc:
            raise ValueError("A quantidade lida deve ser um número inteiro.") from exc
        if progress_current < 0:
            raise ValueError("O progresso atual não pode ser negativo.")

        if progress_total in (None, ""):
            progress_total = None
        else:
            try:
                progress_total = int(progress_total)
            except (TypeError, ValueError) as exc:
                raise ValueError("O total deve ser um número inteiro.") from exc
            if progress_total <= 0:
                raise ValueError("O total deve ser maior que zero.")
            if progress_current > progress_total:
                raise ValueError("O progresso atual não pode ser maior que o total.")
        return progress_current, progress_total

    @staticmethod
    def _normalize_reading_state(status, progress_current, progress_total, start_date, end_date):
        """Keep status, progress and reading dates internally coherent."""
        today = date.today().isoformat()

        # A known 100% progress is a completed work unless the user explicitly abandoned it.
        if progress_total is not None and progress_current >= progress_total and status != "Abandonado":
            status = "Concluído"

        # Explicit completion with a known total means 100%.
        if status == "Concluído" and progress_total is not None:
            progress_current = progress_total

        # Any recorded reading progress means the work has already started.
        if status == "Quero ler" and progress_current > 0:
            status = "Lendo"

        if status == "Quero ler":
            start_date = None
            end_date = None
        elif status == "Concluído":
            end_date = end_date or today
        else:
            # "Data de conclusão" is only meaningful for a currently completed work.
            end_date = None

        if status == "Lendo" and not start_date:
            start_date = today
        elif status in ("Pausado", "Abandonado") and progress_current > 0 and not start_date:
            start_date = today

        return status, progress_current, start_date, end_date

    @staticmethod
    def _validate_rating(rating):
        if rating in (None, "", "Sem avaliação"):
            return None
        try:
            rating = float(rating)
        except (TypeError, ValueError) as exc:
            raise ValueError("Avaliação inválida.") from exc
        doubled = rating * 2
        if rating < 0.5 or rating > 5 or abs(doubled - round(doubled)) > 1e-9:
            raise ValueError("A avaliação deve estar entre 0,5 e 5, em passos de 0,5.")
        return rating

    @staticmethod
    def _validate_iso_date(value, field_name="Data"):
        value = (value or "").strip()
        if not value:
            return None
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"{field_name} deve estar no formato AAAA-MM-DD.") from exc
        return value

    def list_all(self):
        return self.list_filtered()

    def list_filtered(self, search="", category=None, status=None, tag=None, favorites_only=False):
        where = ["w.deleted_at IS NULL"]
        params = []
        search = self._normalize_text(search)
        category = self._normalize_text(category)
        status = self._normalize_text(status)
        tag = self._normalize_text(tag)

        if search:
            term = f"%{search}%"
            where.append("""
                (w.name LIKE ? COLLATE NOCASE OR
                 w.category LIKE ? COLLATE NOCASE OR
                 w.status LIKE ? COLLATE NOCASE OR
                 w.synopsis LIKE ? COLLATE NOCASE OR
                 w.personal_notes LIKE ? COLLATE NOCASE OR
                 EXISTS (SELECT 1 FROM work_tags wt_search
                         WHERE wt_search.work_id = w.id
                           AND wt_search.tag LIKE ? COLLATE NOCASE))
            """)
            params.extend([term] * 6)
        if category and category != "Todas":
            where.append("w.category = ? COLLATE NOCASE")
            params.append(category)
        if status and status != "Todos":
            where.append("w.status = ? COLLATE NOCASE")
            params.append(status)
        if tag and tag != "Todas":
            where.append("""
                EXISTS (SELECT 1 FROM work_tags wt_filter
                        WHERE wt_filter.work_id = w.id
                          AND wt_filter.tag = ? COLLATE NOCASE)
            """)
            params.append(tag)
        if favorites_only:
            where.append("w.favorite = 1")

        with self._connect() as conn:
            rows = conn.execute(f"""
                SELECT w.id, w.name, w.category, w.progress_unit,
                       w.progress_current, w.progress_total, w.status,
                       w.release_day, w.synopsis, w.rating, w.favorite,
                       w.personal_notes, w.start_date, w.end_date, w.cover_path,
                       w.created_at, w.updated_at
                FROM works w
                WHERE {' AND '.join(where)}
                ORDER BY w.favorite DESC, w.updated_at DESC
            """, params).fetchall()
        return [self._row_to_work(row) for row in rows]

    def get_by_id(self, work_id):
        with self._connect() as conn:
            row = conn.execute("""
                SELECT id, name, category, progress_unit, progress_current,
                       progress_total, status, release_day, synopsis, rating,
                       favorite, personal_notes, start_date, end_date, cover_path,
                       created_at, updated_at
                FROM works WHERE id = ? AND deleted_at IS NULL
            """, (work_id,)).fetchone()
        return self._row_to_work(row) if row else None

    def create(self, name, category="", progress_unit="Página", progress_current=0,
               progress_total=None, status="Quero ler", release_day=None,
               synopsis="", rating=None, favorite=False, personal_notes="",
               start_date=None, end_date=None, cover_path=None):
        name = self._normalize_text(name)
        category = self._normalize_text(category)
        if not name:
            raise ValueError("Informe o nome da obra.")
        if progress_unit not in self.PROGRESS_UNITS:
            raise ValueError("Unidade de progresso inválida.")
        if status not in self.STATUS_OPTIONS:
            raise ValueError("Status inválido.")
        progress_current, progress_total = self._validate_progress(progress_current, progress_total)
        rating = self._validate_rating(rating)
        start_date = self._validate_iso_date(start_date, "Data de início")
        end_date = self._validate_iso_date(end_date, "Data de conclusão")
        if start_date and end_date and end_date < start_date:
            raise ValueError("A data de conclusão não pode ser anterior à data de início.")
        status, progress_current, start_date, end_date = self._normalize_reading_state(
            status, progress_current, progress_total, start_date, end_date
        )

        now = self._utcnow()
        work_id = str(uuid.uuid4())
        work = Work(
            id=work_id, name=name, category=category, progress_unit=progress_unit,
            progress_current=progress_current, progress_total=progress_total,
            status=status, release_day=normalize_weekday(release_day),
            synopsis=synopsis or "", rating=rating, favorite=bool(favorite),
            personal_notes=personal_notes or "", start_date=start_date,
            end_date=end_date, cover_path=self._normalize_cover_path(cover_path),
            created_at=now, updated_at=now,
        )

        with self._connect() as conn:
            self._ensure_category_in_conn(conn, category, now)
            conn.execute("""
                INSERT INTO works (
                    id, name, category, progress_unit, progress_current,
                    progress_total, status, release_day, synopsis, rating,
                    favorite, personal_notes, start_date, end_date, cover_path,
                    created_at, updated_at, sync_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING_CREATE')
            """, (
                work.id, work.name, work.category, work.progress_unit,
                work.progress_current, work.progress_total, work.status,
                work.release_day, work.synopsis, work.rating, int(work.favorite),
                work.personal_notes, work.start_date, work.end_date, work.cover_path,
                work.created_at, work.updated_at,
            ))
            if progress_current > 0:
                self._insert_history(conn, work.id,
                    f"Progresso inicial: 0 → {progress_current}", "progress",
                    progress_current, progress_unit, now)
        return work

    def update_work(self, work_id, *, name, category, progress_unit,
                    progress_current, progress_total, status, release_day=None,
                    synopsis="", rating=None, favorite=False, personal_notes="",
                    start_date=None, end_date=None):
        name = self._normalize_text(name)
        category = self._normalize_text(category)
        if not name:
            raise ValueError("Informe o nome da obra.")
        if progress_unit not in self.PROGRESS_UNITS:
            raise ValueError("Unidade de progresso inválida.")
        if status not in self.STATUS_OPTIONS:
            raise ValueError("Status inválido.")
        progress_current, progress_total = self._validate_progress(progress_current, progress_total)
        rating = self._validate_rating(rating)
        start_date = self._validate_iso_date(start_date, "Data de início")
        end_date = self._validate_iso_date(end_date, "Data de conclusão")
        if start_date and end_date and end_date < start_date:
            raise ValueError("A data de conclusão não pode ser anterior à data de início.")

        now = self._utcnow()
        with self._connect() as conn:
            current = conn.execute(
                "SELECT * FROM works WHERE id = ? AND deleted_at IS NULL", (work_id,)
            ).fetchone()
            if current is None:
                raise ValueError("Obra não encontrada.")

            # Preserve an existing start date when the form leaves it blank while a work is already underway.
            if not start_date and current["start_date"] and status != "Quero ler":
                start_date = current["start_date"]
            if not end_date and current["end_date"] and status == "Concluído":
                end_date = current["end_date"]
            status, progress_current, start_date, end_date = self._normalize_reading_state(
                status, progress_current, progress_total, start_date, end_date
            )

            self._ensure_category_in_conn(conn, category, now)
            sync_status = "PENDING_CREATE" if current["sync_status"] == "PENDING_CREATE" else "PENDING_UPDATE"
            conn.execute("""
                UPDATE works SET
                    name = ?, category = ?, progress_unit = ?, progress_current = ?,
                    progress_total = ?, status = ?, release_day = ?, synopsis = ?,
                    rating = ?, favorite = ?, personal_notes = ?, start_date = ?,
                    end_date = ?, updated_at = ?, sync_status = ?
                WHERE id = ?
            """, (
                name, category, progress_unit, progress_current, progress_total,
                status, normalize_weekday(release_day), synopsis or "",
                rating, int(bool(favorite)), personal_notes or "", start_date,
                end_date, now, sync_status, work_id,
            ))

            old_progress = int(current["progress_current"] or 0)
            if progress_current != old_progress:
                delta = progress_current - old_progress
                self._insert_history(conn, work_id,
                    f"Progresso: {old_progress} → {progress_current}", "progress",
                    delta, progress_unit, now)
            if status != current["status"]:
                self._insert_history(conn, work_id,
                    f"Status: {current['status']} → {status}", "status", None,
                    progress_unit, now)

    def delete_work(self, work_id):
        now = self._utcnow()
        cover_to_remove = None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT sync_status, cover_path FROM works WHERE id = ? AND deleted_at IS NULL",
                (work_id,),
            ).fetchone()
            if row is None:
                return
            cover_to_remove = row["cover_path"]
            if row["sync_status"] == "PENDING_CREATE":
                conn.execute("DELETE FROM works WHERE id = ?", (work_id,))
            else:
                conn.execute("""
                    UPDATE works SET deleted_at = ?, updated_at = ?, sync_status = 'PENDING_DELETE'
                    WHERE id = ?
                """, (now, now, work_id))
        if cover_to_remove:
            try:
                Path(self._normalize_cover_path(cover_to_remove)).unlink(missing_ok=True)
            except OSError:
                pass

    def increment_progress(self, work_id, amount=1):
        amount = int(amount)
        if amount == 0:
            return
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM works WHERE id = ? AND deleted_at IS NULL", (work_id,)
            ).fetchone()
            if row is None:
                raise ValueError("Obra não encontrada.")
            old_value = int(row["progress_current"] or 0)
            new_value = max(0, old_value + amount)
            total = row["progress_total"]
            if total is not None:
                new_value = min(new_value, int(total))
            if new_value == old_value:
                return

            now = self._utcnow()
            status = row["status"]
            end_date = row["end_date"]
            if total is not None and new_value >= int(total) and status not in ("Concluído", "Abandonado"):
                status = "Concluído"
                end_date = end_date or date.today().isoformat()
            elif total is not None and new_value < int(total) and status == "Concluído":
                status = "Lendo" if new_value > 0 else "Quero ler"
                end_date = None
            elif new_value > 0 and status == "Quero ler":
                status = "Lendo"

            start_date = row["start_date"]
            if status == "Lendo" and not start_date:
                start_date = date.today().isoformat()

            next_sync = "PENDING_CREATE" if row["sync_status"] == "PENDING_CREATE" else "PENDING_UPDATE"
            conn.execute("""
                UPDATE works SET progress_current = ?, status = ?, start_date = ?, end_date = ?,
                                 updated_at = ?, sync_status = ? WHERE id = ?
            """, (new_value, status, start_date, end_date, now, next_sync, work_id))
            self._insert_history(conn, work_id,
                f"Progresso: {old_value} → {new_value}", "progress",
                new_value - old_value, row["progress_unit"], now)
            if status != row["status"]:
                self._insert_history(conn, work_id,
                    f"Status: {row['status']} → {status}", "status", None,
                    row["progress_unit"], now)

    def _insert_history(self, conn, work_id, description, event_type, delta, progress_unit, created_at=None):
        conn.execute("""
            INSERT INTO history (id, work_id, description, event_type, delta,
                                 progress_unit, created_at, sync_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING_CREATE')
        """, (str(uuid.uuid4()), work_id, description, event_type, delta,
              progress_unit, created_at or self._utcnow()))

    def set_reading_dates(self, work_id, start_date=None, end_date=None):
        self._update_metadata(
            work_id,
            start_date=self._validate_iso_date(start_date, "Data de início"),
            end_date=self._validate_iso_date(end_date, "Data de conclusão"),
        )

    def set_favorite(self, work_id, favorite):
        self._update_metadata(work_id, favorite=int(bool(favorite)))

    def set_rating(self, work_id, rating):
        self._update_metadata(work_id, rating=self._validate_rating(rating))

    def set_notes(self, work_id, notes):
        self._update_metadata(work_id, personal_notes=notes or "")

    def set_cover(self, work_id, source_path):
        source = Path(source_path)
        if not source.is_file():
            raise ValueError("Arquivo de capa não encontrado.")
        if source.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
            raise ValueError("Formato de capa não suportado.")
        work = self.get_by_id(work_id)
        if not work:
            raise ValueError("Obra não encontrada.")
        destination = Path(self.covers_dir) / f"{work_id}{source.suffix.lower()}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Remove a previous local file if the extension changed.
        if work.cover_path:
            old = Path(work.cover_path)
            if old.resolve() != destination.resolve():
                try:
                    old.unlink(missing_ok=True)
                except OSError:
                    pass
        if source.resolve() != destination.resolve():
            shutil.copy2(source, destination)
        normalized = str(destination.resolve())
        self._update_metadata(work_id, cover_path=normalized, cover_deleted=0)
        return normalized

    def remove_cover(self, work_id):
        work = self.get_by_id(work_id)
        if work and work.cover_path:
            try:
                Path(work.cover_path).unlink(missing_ok=True)
            except OSError:
                pass
        # Preserve cover_remote_id; SyncEngine uses it to remove the remote file.
        self._update_metadata(work_id, cover_path=None, cover_deleted=1)

    def _update_metadata(self, work_id, **fields):
        allowed = {"favorite", "rating", "personal_notes", "start_date", "end_date", "cover_path", "cover_deleted"}
        invalid = set(fields) - allowed
        if invalid:
            raise ValueError(f"Campos inválidos: {sorted(invalid)}")
        if not fields:
            return
        now = self._utcnow()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT sync_status FROM works WHERE id = ? AND deleted_at IS NULL", (work_id,)
            ).fetchone()
            if row is None:
                raise ValueError("Obra não encontrada.")
            sync_status = "PENDING_CREATE" if row["sync_status"] == "PENDING_CREATE" else "PENDING_UPDATE"
            assignments = [f"{name} = ?" for name in fields]
            values = list(fields.values())
            assignments += ["updated_at = ?", "sync_status = ?"]
            values += [now, sync_status, work_id]
            conn.execute(f"UPDATE works SET {', '.join(assignments)} WHERE id = ?", values)

    def get_tags(self, work_id):
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT tag FROM work_tags WHERE work_id = ? ORDER BY tag COLLATE NOCASE
            """, (work_id,)).fetchall()
        return [row["tag"] for row in rows]

    def list_tags(self):
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT DISTINCT wt.tag
                FROM work_tags wt JOIN works w ON w.id = wt.work_id
                WHERE w.deleted_at IS NULL
                ORDER BY wt.tag COLLATE NOCASE
            """).fetchall()
        return [row["tag"] for row in rows]

    def set_tags(self, work_id, tags):
        clean_tags = sorted({tag.strip() for tag in tags if tag and tag.strip()}, key=str.casefold)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT sync_status FROM works WHERE id = ? AND deleted_at IS NULL", (work_id,)
            ).fetchone()
            if row is None:
                raise ValueError("Obra não encontrada.")
            old_tags = [r["tag"] for r in conn.execute(
                "SELECT tag FROM work_tags WHERE work_id = ? ORDER BY tag COLLATE NOCASE", (work_id,)
            ).fetchall()]
            if [t.casefold() for t in old_tags] == [t.casefold() for t in clean_tags]:
                return
            conn.execute("DELETE FROM work_tags WHERE work_id = ?", (work_id,))
            for tag in clean_tags:
                conn.execute("INSERT OR IGNORE INTO work_tags (work_id, tag) VALUES (?, ?)", (work_id, tag))
            sync_status = "PENDING_CREATE" if row["sync_status"] == "PENDING_CREATE" else "PENDING_UPDATE"
            conn.execute("UPDATE works SET updated_at = ?, sync_status = ? WHERE id = ?",
                         (self._utcnow(), sync_status, work_id))

    def _ensure_category_in_conn(self, conn, category, now=None):
        category = self._normalize_text(category)
        if not category:
            return
        now = now or self._utcnow()
        row = conn.execute(
            "SELECT * FROM categories WHERE name = ? COLLATE NOCASE", (category,)
        ).fetchone()
        if row is None:
            conn.execute("""
                INSERT INTO categories (name, created_at, id, updated_at, deleted_at, sync_status)
                VALUES (?, ?, ?, ?, NULL, 'PENDING_CREATE')
            """, (category, now, str(uuid.uuid4()), now))
        elif row["deleted_at"]:
            next_sync = "PENDING_CREATE" if row["sync_status"] == "PENDING_CREATE" else "PENDING_UPDATE"
            conn.execute("""
                UPDATE categories SET deleted_at = NULL, updated_at = ?, sync_status = ?
                WHERE name = ? COLLATE NOCASE
            """, (now, next_sync, category))

    def list_categories(self):
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT c.name, COUNT(CASE WHEN w.deleted_at IS NULL THEN w.id END) AS work_count
                FROM categories c
                LEFT JOIN works w ON w.category = c.name COLLATE NOCASE
                WHERE c.deleted_at IS NULL
                GROUP BY c.name
                ORDER BY c.name COLLATE NOCASE
            """).fetchall()
        return [dict(row) for row in rows]

    def create_category(self, name):
        name = self._normalize_text(name)
        if not name:
            raise ValueError("Informe o nome da categoria.")
        with self._connect() as conn:
            self._ensure_category_in_conn(conn, name)
            row = conn.execute(
                "SELECT name FROM categories WHERE name = ? COLLATE NOCASE AND deleted_at IS NULL", (name,)
            ).fetchone()
        return row["name"]

    def rename_category(self, old_name, new_name):
        old_name = self._normalize_text(old_name)
        new_name = self._normalize_text(new_name)
        if not old_name:
            raise ValueError("Categoria de origem inválida.")
        if not new_name:
            raise ValueError("Informe o novo nome da categoria.")
        if old_name.casefold() == new_name.casefold():
            return
        now = self._utcnow()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM categories WHERE name = ? COLLATE NOCASE AND deleted_at IS NULL", (old_name,)
            ).fetchone()
            if row is None:
                raise ValueError("Categoria não encontrada.")
            if conn.execute(
                "SELECT 1 FROM categories WHERE name = ? COLLATE NOCASE AND deleted_at IS NULL", (new_name,)
            ).fetchone():
                raise ValueError("Já existe uma categoria com esse nome.")
            category_sync = "PENDING_CREATE" if row["sync_status"] == "PENDING_CREATE" else "PENDING_UPDATE"
            conn.execute("""
                UPDATE categories SET name = ?, updated_at = ?, sync_status = ?
                WHERE name = ? COLLATE NOCASE
            """, (new_name, now, category_sync, old_name))
            conn.execute("""
                UPDATE works SET category = ?, updated_at = ?,
                    sync_status = CASE WHEN sync_status = 'PENDING_CREATE' THEN 'PENDING_CREATE' ELSE 'PENDING_UPDATE' END
                WHERE category = ? COLLATE NOCASE AND deleted_at IS NULL
            """, (new_name, now, old_name))

    def delete_category(self, name):
        name = self._normalize_text(name)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM categories WHERE name = ? COLLATE NOCASE AND deleted_at IS NULL", (name,)
            ).fetchone()
            if row is None:
                return
            count = conn.execute("""
                SELECT COUNT(*) AS total FROM works
                WHERE category = ? COLLATE NOCASE AND deleted_at IS NULL
            """, (name,)).fetchone()["total"]
            if count:
                raise ValueError(f"A categoria está sendo usada por {count} obra(s). Altere essas obras antes de excluí-la.")
            if row["sync_status"] == "PENDING_CREATE":
                conn.execute("DELETE FROM categories WHERE name = ? COLLATE NOCASE", (name,))
            else:
                now = self._utcnow()
                conn.execute("""
                    UPDATE categories SET deleted_at = ?, updated_at = ?, sync_status = 'PENDING_DELETE'
                    WHERE name = ? COLLATE NOCASE
                """, (now, now, name))

    def create_goal(self, title, goal_type, target_value, start_date=None, end_date=None):
        title = self._normalize_text(title)
        if not title:
            raise ValueError("Informe o título da meta.")
        if goal_type not in self.GOAL_TYPES:
            raise ValueError("Tipo de meta inválido.")
        try:
            target_value = int(target_value)
        except (TypeError, ValueError) as exc:
            raise ValueError("A meta deve ser um número inteiro.") from exc
        if target_value <= 0:
            raise ValueError("A meta deve ser maior que zero.")
        start_date = self._validate_iso_date(start_date, "Data inicial")
        end_date = self._validate_iso_date(end_date, "Data final")
        if start_date and end_date and end_date < start_date:
            raise ValueError("A data final não pode ser anterior à data inicial.")
        goal_id = str(uuid.uuid4())
        now = self._utcnow()
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO goals (id, title, goal_type, target_value, current_value,
                                   start_date, end_date, created_at, updated_at, sync_status)
                VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?, 'PENDING_CREATE')
            """, (goal_id, title, goal_type, target_value, start_date, end_date, now, now))
        return goal_id

    def update_goal(self, goal_id, *, title, goal_type, target_value, start_date=None, end_date=None):
        title = self._normalize_text(title)
        if not title:
            raise ValueError("Informe o título da meta.")
        if goal_type not in self.GOAL_TYPES:
            raise ValueError("Tipo de meta inválido.")
        target_value = int(target_value)
        if target_value <= 0:
            raise ValueError("A meta deve ser maior que zero.")
        start_date = self._validate_iso_date(start_date, "Data inicial")
        end_date = self._validate_iso_date(end_date, "Data final")
        if start_date and end_date and end_date < start_date:
            raise ValueError("A data final não pode ser anterior à data inicial.")
        now = self._utcnow()
        with self._connect() as conn:
            row = conn.execute("SELECT sync_status FROM goals WHERE id = ? AND deleted_at IS NULL", (goal_id,)).fetchone()
            if not row:
                raise ValueError("Meta não encontrada.")
            sync = "PENDING_CREATE" if row["sync_status"] == "PENDING_CREATE" else "PENDING_UPDATE"
            conn.execute("""
                UPDATE goals SET title = ?, goal_type = ?, target_value = ?, start_date = ?, end_date = ?,
                                 updated_at = ?, sync_status = ? WHERE id = ?
            """, (title, goal_type, target_value, start_date, end_date, now, sync, goal_id))

    def delete_goal(self, goal_id):
        with self._connect() as conn:
            row = conn.execute("SELECT sync_status FROM goals WHERE id = ? AND deleted_at IS NULL", (goal_id,)).fetchone()
            if not row:
                return
            if row["sync_status"] == "PENDING_CREATE":
                conn.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
            else:
                now = self._utcnow()
                conn.execute("""
                    UPDATE goals SET deleted_at = ?, updated_at = ?, sync_status = 'PENDING_DELETE' WHERE id = ?
                """, (now, now, goal_id))

    def _calculate_goal_current(self, conn, goal):
        goal_type = goal["goal_type"]
        start = goal["start_date"]
        end = goal["end_date"]
        if goal_type == "books":
            where = ["deleted_at IS NULL", "status = 'Concluído'"]
            params = []
            if start:
                where.append("COALESCE(end_date, substr(updated_at, 1, 10)) >= ?")
                params.append(start)
            if end:
                where.append("COALESCE(end_date, substr(updated_at, 1, 10)) <= ?")
                params.append(end)
            return conn.execute(f"SELECT COUNT(*) AS n FROM works WHERE {' AND '.join(where)}", params).fetchone()["n"]

        unit = "Página" if goal_type == "pages" else "Capítulo"
        if start or end:
            where = ["h.event_type = 'progress'", "h.progress_unit = ?", "w.deleted_at IS NULL"]
            params = [unit]
            if start:
                where.append("substr(h.created_at, 1, 10) >= ?")
                params.append(start)
            if end:
                where.append("substr(h.created_at, 1, 10) <= ?")
                params.append(end)
            return conn.execute(f"""
                SELECT COALESCE(SUM(h.delta), 0) AS n
                FROM history h JOIN works w ON w.id = h.work_id
                WHERE {' AND '.join(where)}
            """, params).fetchone()["n"]

        return conn.execute("""
            SELECT COALESCE(SUM(progress_current), 0) AS n
            FROM works WHERE deleted_at IS NULL AND progress_unit = ?
        """, (unit,)).fetchone()["n"]

    def list_goals(self):
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM goals WHERE deleted_at IS NULL ORDER BY created_at DESC").fetchall()
            result = []
            for row in rows:
                item = dict(row)
                current = int(self._calculate_goal_current(conn, row) or 0)
                item["current_value"] = current
                if current != int(row["current_value"] or 0):
                    conn.execute("UPDATE goals SET current_value = ? WHERE id = ?", (current, row["id"]))
                result.append(item)
            return result

    def update_goal_progress(self, goal_id, current_value):
        # Kept for backwards compatibility; goal progress is now calculated automatically.
        with self._connect() as conn:
            conn.execute("UPDATE goals SET current_value = ? WHERE id = ?", (int(current_value), goal_id))

    def list_calendar_events(self):
        events = []
        for work in self.list_all():
            if work.start_date:
                events.append({"date": work.start_date, "type": "Início", "title": work.name, "work_id": work.id})
            if work.end_date:
                events.append({"date": work.end_date, "type": "Conclusão", "title": work.name, "work_id": work.id})
            if work.progress_unit == "Capítulo" and work.progress_total is None and work.release_day:
                predicted = next_weekday_date(work.release_day)
                if predicted:
                    events.append({
                        "date": predicted.isoformat(),
                        "type": "Próximo lançamento",
                        "title": work.name,
                        "work_id": work.id,
                    })
        return sorted(events, key=lambda item: (item["date"], item["title"].casefold()))

    def list_history(self, limit=500):
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT h.id, h.created_at, h.description, h.event_type, h.delta,
                       h.progress_unit, w.name, w.id AS work_id
                FROM history h JOIN works w ON w.id = h.work_id
                WHERE w.deleted_at IS NULL
                ORDER BY h.created_at DESC LIMIT ?
            """, (int(limit),)).fetchall()
        return [dict(row) for row in rows]

    def export_payload(self):
        with self._connect() as conn:
            works = [dict(row) for row in conn.execute("SELECT * FROM works").fetchall()]
            history = [dict(row) for row in conn.execute("SELECT * FROM history").fetchall()]
            tags = [dict(row) for row in conn.execute("SELECT * FROM work_tags").fetchall()]
            goals = [dict(row) for row in conn.execute("SELECT * FROM goals").fetchall()]
            categories = [dict(row) for row in conn.execute("SELECT * FROM categories").fetchall()]
        return {
            "schema_version": self.SCHEMA_VERSION,
            "works": works,
            "history": history,
            "tags": tags,
            "goals": goals,
            "categories": categories,
        }

    def replace_from_payload(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("Arquivo de dados inválido.")
        works = payload.get("works", [])
        history = payload.get("history", [])
        tags = payload.get("tags", [])
        goals = payload.get("goals", [])
        categories = payload.get("categories", [])
        if not all(isinstance(value, list) for value in (works, history, tags, goals, categories)):
            raise ValueError("Estrutura do backup inválida.")

        now = self._utcnow()
        with self._connect() as conn:
            conn.execute("DELETE FROM work_tags")
            conn.execute("DELETE FROM history")
            conn.execute("DELETE FROM goals")
            conn.execute("DELETE FROM works")
            conn.execute("DELETE FROM categories")

            for item in categories:
                name = self._normalize_text(item.get("name"))
                if not name:
                    continue
                conn.execute("""
                    INSERT OR IGNORE INTO categories
                    (name, created_at, id, updated_at, deleted_at, sync_status)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    name, item.get("created_at") or now, item.get("id") or str(uuid.uuid4()),
                    item.get("updated_at") or item.get("created_at") or now,
                    item.get("deleted_at"), item.get("sync_status", "PENDING_CREATE"),
                ))

            work_ids = set()
            for item in works:
                work_id = item.get("id") or str(uuid.uuid4())
                name = self._normalize_text(item.get("name"))
                if not name:
                    raise ValueError("Backup contém obra sem nome.")
                category = self._normalize_text(item.get("category"))
                if not item.get("deleted_at"):
                    self._ensure_category_in_conn(conn, category, now)
                cover_path = self._normalize_cover_path(item.get("cover_path"))
                if cover_path and not Path(cover_path).exists():
                    cover_path = None
                conn.execute("""
                    INSERT INTO works (
                        id, name, category, progress_unit, progress_current, progress_total,
                        status, release_day, synopsis, rating, favorite, personal_notes,
                        start_date, end_date, cover_path, cover_remote_id, cover_remote_name, cover_remote_modified, cover_deleted,
                        created_at, updated_at, deleted_at, sync_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    work_id, name, category, item.get("progress_unit", "Página"),
                    int(item.get("progress_current", 0) or 0), item.get("progress_total"),
                    item.get("status", "Quero ler"), item.get("release_day"), item.get("synopsis", ""),
                    item.get("rating"), int(bool(item.get("favorite", 0))), item.get("personal_notes", ""),
                    item.get("start_date"), item.get("end_date"), cover_path,
                    item.get("cover_remote_id"), item.get("cover_remote_name"), item.get("cover_remote_modified"),
                    int(bool(item.get("cover_deleted", 0))), item.get("created_at") or now, item.get("updated_at") or now,
                    item.get("deleted_at"), item.get("sync_status", "PENDING_CREATE"),
                ))
                work_ids.add(work_id)

            for item in history:
                if item.get("work_id") not in work_ids:
                    continue
                conn.execute("""
                    INSERT OR IGNORE INTO history
                    (id, work_id, description, event_type, delta, progress_unit, created_at, sync_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    item.get("id") or str(uuid.uuid4()), item["work_id"], item.get("description", ""),
                    item.get("event_type", "progress"), item.get("delta"), item.get("progress_unit"),
                    item.get("created_at") or now, item.get("sync_status", "PENDING_CREATE"),
                ))

            for item in tags:
                if item.get("work_id") in work_ids and self._normalize_text(item.get("tag")):
                    conn.execute("INSERT OR IGNORE INTO work_tags (work_id, tag) VALUES (?, ?)",
                                 (item["work_id"], self._normalize_text(item["tag"])))

            for item in goals:
                if not self._normalize_text(item.get("title")):
                    continue
                conn.execute("""
                    INSERT OR IGNORE INTO goals
                    (id, title, goal_type, target_value, current_value, start_date, end_date,
                     created_at, updated_at, deleted_at, sync_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    item.get("id") or str(uuid.uuid4()), item["title"], item.get("goal_type", "books"),
                    int(item.get("target_value", 1) or 1), int(item.get("current_value", 0) or 0),
                    item.get("start_date"), item.get("end_date"), item.get("created_at") or now,
                    item.get("updated_at") or item.get("created_at") or now,
                    item.get("deleted_at"), item.get("sync_status", "PENDING_CREATE"),
                ))

    # ------------------------- cloud sync support -------------------------
    def export_sync_payload(self):
        with self._connect() as conn:
            works = []
            for row in conn.execute("SELECT * FROM works").fetchall():
                item = dict(row)
                item["tags"] = [r["tag"] for r in conn.execute(
                    "SELECT tag FROM work_tags WHERE work_id = ? ORDER BY tag COLLATE NOCASE", (row["id"],)
                ).fetchall()]
                path = self._normalize_cover_path(item.pop("cover_path", None))
                item["cover_filename"] = Path(path).name if path else item.get("cover_remote_name")
                item.pop("sync_status", None)
                item.pop("cover_deleted", None)
                works.append(item)
            categories = [dict(row) for row in conn.execute("""
                SELECT id, name, created_at, updated_at, deleted_at FROM categories
            """).fetchall()]
            goal_rows = conn.execute("""
                SELECT id, title, goal_type, target_value, current_value, start_date, end_date,
                       created_at, updated_at, deleted_at FROM goals
            """).fetchall()
            goals = []
            for row in goal_rows:
                item = dict(row)
                if not row["deleted_at"]:
                    item["current_value"] = int(self._calculate_goal_current(conn, row) or 0)
                goals.append(item)
            history = [dict(row) for row in conn.execute("""
                SELECT id, work_id, description, event_type, delta, progress_unit, created_at FROM history
            """).fetchall()]
        return {"schema_version": self.SCHEMA_VERSION, "works": works,
                "categories": categories, "goals": goals, "history": history}

    @staticmethod
    def _remote_is_newer(remote_updated, local_updated):
        return (remote_updated or "") > (local_updated or "")

    def merge_remote_payload(self, payload):
        """Merge a remote snapshot using updated_at last-write-wins semantics."""
        if not payload:
            return {"downloaded": 0}
        downloaded = 0
        now = self._utcnow()
        with self._connect() as conn:
            # Categories first so works can reference them by display name.
            for item in payload.get("categories", []):
                name = self._normalize_text(item.get("name"))
                if not name:
                    continue
                category_id = item.get("id") or str(uuid.uuid4())
                local = conn.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
                if local is None:
                    collision = conn.execute("SELECT * FROM categories WHERE name = ? COLLATE NOCASE", (name,)).fetchone()
                    if collision:
                        local = collision
                if local is None:
                    conn.execute("""
                        INSERT INTO categories (name, created_at, id, updated_at, deleted_at, sync_status)
                        VALUES (?, ?, ?, ?, ?, 'SYNCED')
                    """, (name, item.get("created_at") or now, category_id,
                          item.get("updated_at") or item.get("created_at") or now, item.get("deleted_at")))
                    downloaded += 1
                elif self._remote_is_newer(item.get("updated_at"), local["updated_at"]):
                    # Avoid violating the name primary key on a remote rename collision.
                    collision = conn.execute(
                        "SELECT id FROM categories WHERE name = ? COLLATE NOCASE AND id <> ?", (name, local["id"])
                    ).fetchone()
                    if not collision:
                        conn.execute("""
                            UPDATE categories SET name = ?, created_at = ?, updated_at = ?, deleted_at = ?, sync_status = 'SYNCED'
                            WHERE id = ?
                        """, (name, item.get("created_at") or local["created_at"], item.get("updated_at") or now,
                              item.get("deleted_at"), local["id"]))
                        downloaded += 1

            for item in payload.get("works", []):
                work_id = item.get("id")
                if not work_id or not self._normalize_text(item.get("name")):
                    continue
                local = conn.execute("SELECT * FROM works WHERE id = ?", (work_id,)).fetchone()
                if local is not None and not self._remote_is_newer(item.get("updated_at"), local["updated_at"]):
                    continue
                category = self._normalize_text(item.get("category"))
                self._ensure_category_in_conn(conn, category, item.get("updated_at") or now)
                existing_cover_path = local["cover_path"] if local else None
                same_remote_cover = bool(
                    local
                    and local["cover_remote_id"]
                    and local["cover_remote_id"] == item.get("cover_remote_id")
                    and (local["cover_remote_modified"] or "") == (item.get("cover_remote_modified") or "")
                )
                cover_path = existing_cover_path if same_remote_cover else None

                progress_unit = item.get("progress_unit") if item.get("progress_unit") in self.PROGRESS_UNITS else "Página"
                status = item.get("status") if item.get("status") in self.STATUS_OPTIONS else "Quero ler"
                try:
                    progress_current, progress_total = self._validate_progress(
                        item.get("progress_current", 0), item.get("progress_total")
                    )
                except ValueError:
                    progress_current, progress_total = 0, None
                try:
                    rating = self._validate_rating(item.get("rating"))
                except ValueError:
                    rating = None
                try:
                    start_date = self._validate_iso_date(item.get("start_date"), "Data de início")
                except ValueError:
                    start_date = None
                try:
                    end_date = self._validate_iso_date(item.get("end_date"), "Data de conclusão")
                except ValueError:
                    end_date = None
                status, progress_current, start_date, end_date = self._normalize_reading_state(
                    status, progress_current, progress_total, start_date, end_date
                )

                values = (
                    self._normalize_text(item.get("name")), category, progress_unit,
                    progress_current, progress_total, status, item.get("release_day"), item.get("synopsis", ""),
                    rating, int(bool(item.get("favorite", False))), item.get("personal_notes", ""),
                    start_date, end_date, cover_path, item.get("cover_remote_id"), item.get("cover_filename"),
                    item.get("cover_remote_modified"), item.get("created_at") or now, item.get("updated_at") or now,
                    item.get("deleted_at"),
                )
                if local is None:
                    conn.execute("""
                        INSERT INTO works (
                            id, name, category, progress_unit, progress_current, progress_total,
                            status, release_day, synopsis, rating, favorite, personal_notes,
                            start_date, end_date, cover_path, cover_remote_id, cover_remote_name, cover_remote_modified, cover_deleted,
                            created_at, updated_at, deleted_at, sync_status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, 'SYNCED')
                    """, (work_id,) + values)
                else:
                    conn.execute("""
                        UPDATE works SET name = ?, category = ?, progress_unit = ?, progress_current = ?, progress_total = ?,
                            status = ?, release_day = ?, synopsis = ?, rating = ?, favorite = ?, personal_notes = ?,
                            start_date = ?, end_date = ?, cover_path = ?, cover_remote_id = ?, cover_remote_name = ?,
                            cover_remote_modified = ?, cover_deleted = 0, created_at = ?, updated_at = ?, deleted_at = ?, sync_status = 'SYNCED'
                        WHERE id = ?
                    """, values + (work_id,))
                conn.execute("DELETE FROM work_tags WHERE work_id = ?", (work_id,))
                for tag in item.get("tags", []) or []:
                    tag = self._normalize_text(tag)
                    if tag:
                        conn.execute("INSERT OR IGNORE INTO work_tags (work_id, tag) VALUES (?, ?)", (work_id, tag))
                downloaded += 1

            for item in payload.get("goals", []):
                goal_id = item.get("id")
                if not goal_id:
                    continue
                local = conn.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
                remote_updated = item.get("updated_at") or item.get("created_at") or now
                if local is not None and not self._remote_is_newer(remote_updated, local["updated_at"]):
                    continue
                values = (
                    item.get("title", "Meta"), item.get("goal_type", "books"), int(item.get("target_value", 1) or 1),
                    int(item.get("current_value", 0) or 0), item.get("start_date"), item.get("end_date"),
                    item.get("created_at") or now, remote_updated, item.get("deleted_at"),
                )
                if local is None:
                    conn.execute("""
                        INSERT INTO goals (id, title, goal_type, target_value, current_value, start_date, end_date,
                                           created_at, updated_at, deleted_at, sync_status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'SYNCED')
                    """, (goal_id,) + values)
                else:
                    conn.execute("""
                        UPDATE goals SET title = ?, goal_type = ?, target_value = ?, current_value = ?, start_date = ?,
                            end_date = ?, created_at = ?, updated_at = ?, deleted_at = ?, sync_status = 'SYNCED'
                        WHERE id = ?
                    """, values + (goal_id,))
                downloaded += 1

            for item in payload.get("history", []):
                history_id = item.get("id")
                work_id = item.get("work_id")
                if not history_id or not work_id:
                    continue
                if not conn.execute("SELECT 1 FROM works WHERE id = ?", (work_id,)).fetchone():
                    continue
                if conn.execute("SELECT 1 FROM history WHERE id = ?", (history_id,)).fetchone():
                    continue
                conn.execute("""
                    INSERT INTO history (id, work_id, description, event_type, delta, progress_unit, created_at, sync_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'SYNCED')
                """, (history_id, work_id, item.get("description", ""), item.get("event_type", "progress"),
                      item.get("delta"), item.get("progress_unit"), item.get("created_at") or now))
                downloaded += 1

            # A concurrent work may still reference a category deleted on another device.
            # Active works take precedence so the category menu can never become inconsistent.
            active_categories = conn.execute("""
                SELECT DISTINCT TRIM(category) AS name FROM works
                WHERE deleted_at IS NULL AND TRIM(category) <> ''
            """).fetchall()
            for category_row in active_categories:
                self._ensure_category_in_conn(conn, category_row["name"], now)

        return {"downloaded": downloaded}

    def get_work_sync_rows(self):
        with self._connect() as conn:
            rows = [dict(row) for row in conn.execute("SELECT * FROM works").fetchall()]
        for item in rows:
            item["cover_path"] = self._normalize_cover_path(item.get("cover_path"))
        return rows

    def update_cover_remote(self, work_id, remote_id, remote_name, remote_modified=None):
        with self._connect() as conn:
            conn.execute(
                "UPDATE works SET cover_remote_id = ?, cover_remote_name = ?, cover_remote_modified = ?, cover_deleted = 0 WHERE id = ?",
                (remote_id, remote_name, remote_modified, work_id),
            )

    def set_local_cover_from_remote(self, work_id, local_path):
        with self._connect() as conn:
            conn.execute("UPDATE works SET cover_path = ?, cover_deleted = 0 WHERE id = ?", (str(Path(local_path).resolve()), work_id))

    def clear_local_cover_from_remote(self, work_id):
        with self._connect() as conn:
            conn.execute("UPDATE works SET cover_path = NULL, cover_deleted = 0 WHERE id = ?", (work_id,))

    def mark_all_synced(self):
        with self._connect() as conn:
            conn.execute("UPDATE works SET sync_status = 'SYNCED' WHERE sync_status <> 'SYNCED'")
            conn.execute("UPDATE categories SET sync_status = 'SYNCED' WHERE sync_status <> 'SYNCED'")
            conn.execute("UPDATE goals SET sync_status = 'SYNCED' WHERE sync_status <> 'SYNCED'")
            conn.execute("UPDATE history SET sync_status = 'SYNCED' WHERE sync_status <> 'SYNCED'")

    def prune_orphan_covers(self):
        covers_root = Path(self.covers_dir).resolve()
        if not covers_root.exists():
            return 0
        with self._connect() as conn:
            referenced = {
                Path(self._normalize_cover_path(row["cover_path"])).resolve()
                for row in conn.execute("SELECT cover_path FROM works WHERE cover_path IS NOT NULL").fetchall()
                if row["cover_path"]
            }
        removed = 0
        for path in covers_root.iterdir():
            if not path.is_file():
                continue
            try:
                resolved = path.resolve()
                if resolved not in referenced:
                    path.unlink()
                    removed += 1
            except OSError:
                continue
        return removed

    def pending_sync_count(self):
        with self._connect() as conn:
            counts = []
            for table in ("works", "categories", "goals", "history"):
                counts.append(conn.execute(f"SELECT COUNT(*) AS n FROM {table} WHERE sync_status <> 'SYNCED'").fetchone()["n"])
        return int(sum(counts))
