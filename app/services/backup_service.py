import json
import os
import shutil
from datetime import datetime


class BackupService:
    def __init__(
        self,
        repository,
        db_path="data/reader.db",
        backup_dir="data/backups",
        max_backups=10,
    ):
        self.repository = repository
        self.db_path = db_path
        self.backup_dir = backup_dir
        self.max_backups = max_backups
        os.makedirs(self.backup_dir, exist_ok=True)

    def export_json(self, file_path):
        payload = self.repository.export_payload()
        payload["exported_at"] = datetime.now().isoformat()

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        return file_path

    def import_json(self, file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        if payload.get("schema_version") != 1:
            raise ValueError("Versão de backup não suportada.")

        self.repository.replace_from_payload(payload)
        return True

    def create_automatic_backup(self):
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

        db_backup = os.path.join(
            self.backup_dir,
            f"reader-{timestamp}.db",
        )
        json_backup = os.path.join(
            self.backup_dir,
            f"reader-{timestamp}.json",
        )

        if os.path.exists(self.db_path):
            shutil.copy2(self.db_path, db_backup)

        self.export_json(json_backup)
        self._rotate_backups()

        return {
            "db": db_backup if os.path.exists(db_backup) else None,
            "json": json_backup,
        }

    def _rotate_backups(self):
        files = sorted(
            [
                os.path.join(self.backup_dir, name)
                for name in os.listdir(self.backup_dir)
                if name.startswith("reader-")
            ],
            key=os.path.getmtime,
            reverse=True,
        )

        groups = {}
        for path in files:
            stem = os.path.splitext(os.path.basename(path))[0]
            groups.setdefault(stem, []).append(path)

        sorted_groups = sorted(
            groups.items(),
            key=lambda item: max(os.path.getmtime(p) for p in item[1]),
            reverse=True,
        )

        for _, paths in sorted_groups[self.max_backups:]:
            for path in paths:
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass
