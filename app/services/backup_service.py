import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from app.paths import BACKUPS_DIR, COVERS_DIR, DB_PATH


class BackupService:
    def __init__(self, repository, db_path=None, backup_dir=None, max_backups=10):
        self.repository = repository
        self.db_path = str(Path(db_path or DB_PATH).resolve())
        self.backup_dir = str(Path(backup_dir or BACKUPS_DIR).resolve())
        self.covers_dir = Path(getattr(repository, "covers_dir", COVERS_DIR)).resolve()
        self.max_backups = int(max_backups)
        Path(self.backup_dir).mkdir(parents=True, exist_ok=True)

    def _is_supported_schema_version(self, version):
        try:
            version = int(version)
        except (TypeError, ValueError):
            return False
        current = int(getattr(self.repository, "SCHEMA_VERSION", 1))
        return 1 <= version <= current

    def export_json(self, file_path):
        payload = self.repository.export_payload()
        payload["exported_at"] = datetime.now().isoformat()
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        return str(file_path)

    def import_json(self, file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        version = payload.get("schema_version")
        if not self._is_supported_schema_version(version):
            raise ValueError("Versão de backup não suportada.")
        self.repository.replace_from_payload(payload)
        self.repository.prune_orphan_covers()

    def export_full_backup(self, file_path):
        file_path = Path(file_path)
        if file_path.suffix.lower() != ".zip":
            file_path = file_path.with_suffix(".zip")
        payload = self.repository.export_payload()
        payload["exported_at"] = datetime.now().isoformat()
        payload["backup_type"] = "full"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            covers_root = root / "covers"
            covers_root.mkdir(parents=True, exist_ok=True)
            for work in payload.get("works", []):
                cover = work.get("cover_path")
                if not cover:
                    continue
                source = Path(cover)
                if not source.is_absolute():
                    source = (Path(self.repository.covers_dir) / source.name).resolve()
                if not source.is_file():
                    work["cover_path"] = None
                    continue
                destination = covers_root / source.name
                shutil.copy2(source, destination)
                work["cover_path"] = f"covers/{source.name}"

            (root / "library.json").write_text(
                json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            with zipfile.ZipFile(file_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.write(root / "library.json", "library.json")
                for cover in covers_root.iterdir():
                    if cover.is_file():
                        archive.write(cover, f"covers/{cover.name}")
        return str(file_path)

    def import_full_backup(self, file_path):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with zipfile.ZipFile(file_path, "r") as archive:
                for member in archive.infolist():
                    target = (root / member.filename).resolve()
                    if root.resolve() not in target.parents and target != root.resolve():
                        raise ValueError("Backup ZIP contém caminho inválido.")
                archive.extractall(root)
            json_path = root / "library.json"
            if not json_path.is_file():
                raise ValueError("Backup completo inválido: library.json não encontrado.")
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            if not self._is_supported_schema_version(payload.get("schema_version")):
                raise ValueError("Versão de backup não suportada.")

            self.covers_dir.mkdir(parents=True, exist_ok=True)
            covers_root = (root / "covers").resolve()
            copied = []
            try:
                for work in payload.get("works", []):
                    relative = work.get("cover_path")
                    if not relative:
                        continue
                    source = (root / Path(relative)).resolve()
                    if covers_root not in source.parents or not source.is_file():
                        raise ValueError("Backup completo inválido: caminho de capa fora da pasta covers/.")
                    destination = (self.covers_dir / source.name).resolve()
                    shutil.copy2(source, destination)
                    copied.append(destination)
                    work["cover_path"] = str(destination)
                self.repository.replace_from_payload(payload)
            except Exception:
                # If database restoration fails, do not leave unreferenced imported covers behind.
                self.repository.prune_orphan_covers()
                raise
            self.repository.prune_orphan_covers()

    def _backup_sqlite(self, destination):
        destination = str(destination)
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        source_conn = sqlite3.connect(self.db_path)
        try:
            target_conn = sqlite3.connect(destination)
            try:
                source_conn.backup(target_conn)
            finally:
                target_conn.close()
        finally:
            source_conn.close()

    def create_automatic_backup(self):
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup_dir = Path(self.backup_dir)
        db_backup = backup_dir / f"reader-{timestamp}.db"
        json_backup = backup_dir / f"reader-{timestamp}.json"
        zip_backup = backup_dir / f"reader-{timestamp}.zip"

        if Path(self.db_path).exists():
            self._backup_sqlite(db_backup)
        self.export_json(json_backup)
        self.export_full_backup(zip_backup)
        self._rotate_backups()
        return {
            "db": str(db_backup) if db_backup.exists() else None,
            "json": str(json_backup),
            "zip": str(zip_backup),
        }

    def _rotate_backups(self):
        files = sorted(
            [
                path for path in Path(self.backup_dir).iterdir()
                if path.is_file() and path.name.startswith("reader-")
            ],
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        groups = {}
        for path in files:
            stem = path.stem
            # reader-<timestamp> where timestamp contains '-' but extension differs.
            groups.setdefault(stem, []).append(path)
        sorted_groups = sorted(
            groups.items(),
            key=lambda item: max(path.stat().st_mtime for path in item[1]),
            reverse=True,
        )
        for _, paths in sorted_groups[self.max_backups:]:
            for path in paths:
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
