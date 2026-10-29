import copy
import tempfile
import unittest
from pathlib import Path

from app.repositories.sqlite_repository import SQLiteWorkRepository
from app.services.sync_engine import SyncEngine


class FakeSettings:
    def __init__(self, enabled=True):
        self.data = {
            "sync_enabled": enabled,
            "google": {
                "credentials_file": "fake.json",
                "spreadsheet_id": "",
                "spreadsheet_name": "The Reader Codex",
                "drive_folder_id": "",
            },
        }

    def load(self):
        return copy.deepcopy(self.data)

    def update_google_identifiers(self, spreadsheet_id=None):
        if spreadsheet_id:
            self.data["google"]["spreadsheet_id"] = spreadsheet_id
        return self.load()


class FakeAdapter:
    def __init__(self, remote=None):
        self.remote = copy.deepcopy(remote or {"works": [], "categories": [], "goals": [], "history": []})
        self.uploaded = None
        self.spreadsheet_id = "sheet-123"
        self.deleted_covers = []

    def connect(self):
        return {"spreadsheet_id": self.spreadsheet_id, "spreadsheet_name": "The Reader Codex"}

    def download_payload(self):
        return copy.deepcopy(self.remote)

    def upload_payload(self, payload):
        self.uploaded = copy.deepcopy(payload)
        self.remote = copy.deepcopy(payload)

    def upload_cover(self, local_path, remote_id=None):
        return remote_id or "cover-123", Path(local_path).name

    def delete_cover(self, remote_id):
        self.deleted_covers.append(remote_id)

    def download_cover(self, remote_id, destination):
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        Path(destination).write_bytes(b"fake")
        return str(Path(destination).resolve())


class SyncEngineTests(unittest.TestCase):
    def test_disabled_sync_is_truthfully_reported(self):
        with tempfile.TemporaryDirectory() as td:
            repo = SQLiteWorkRepository(Path(td) / "db.sqlite", Path(td) / "covers")
            repo.create(name="Local")
            settings = FakeSettings(enabled=False)
            engine = SyncEngine(repo, settings, adapter_factory=lambda _cfg: FakeAdapter())
            result = engine.sync()
            self.assertEqual(result["status"], "not_configured")
            self.assertGreater(result["pending"], 0)

    def test_local_changes_are_uploaded_and_marked_synced(self):
        with tempfile.TemporaryDirectory() as td:
            repo = SQLiteWorkRepository(Path(td) / "db.sqlite", Path(td) / "covers")
            work = repo.create(
                name="Local", category="Manhwa", rating=4.5,
                progress_unit="Capítulo", progress_current=12,
                publication_status="Em lançamento", release_schedule_type="Semanal",
                release_days=["Segunda-feira"], reading_url="https://example.com/ler",
            )
            repo.set_tags(work.id, ["tag"])
            settings = FakeSettings(enabled=True)
            adapter = FakeAdapter()
            engine = SyncEngine(repo, settings, adapter_factory=lambda _cfg: adapter)
            result = engine.sync()
            self.assertEqual(result["status"], "synced")
            self.assertEqual(repo.pending_sync_count(), 0)
            self.assertEqual(adapter.uploaded["works"][0]["name"], "Local")
            self.assertEqual(adapter.uploaded["works"][0]["tags"], ["tag"])
            self.assertEqual(adapter.uploaded["works"][0]["publication_status"], "Em lançamento")
            self.assertEqual(adapter.uploaded["works"][0]["release_schedule_type"], "Semanal")
            self.assertEqual(adapter.uploaded["works"][0]["reading_url"], "https://example.com/ler")
            self.assertEqual(settings.data["google"]["spreadsheet_id"], "sheet-123")

    def test_changed_remote_cover_version_is_downloaded(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = SQLiteWorkRepository(root / "db.sqlite", root / "covers")
            source = root / "local.jpg"
            source.write_bytes(b"old")
            work = repo.create(name="Com capa")
            repo.set_cover(work.id, source)
            repo.update_cover_remote(work.id, "cover-1", "cover.jpg", "v1")
            repo.mark_all_synced()

            remote = repo.export_sync_payload()
            remote["works"][0]["updated_at"] = "9999-01-01T00:00:00+00:00"
            remote["works"][0]["cover_remote_modified"] = "v2"
            adapter = FakeAdapter(remote)
            settings = FakeSettings(enabled=True)
            engine = SyncEngine(repo, settings, adapter_factory=lambda _cfg: adapter)

            result = engine.sync()
            self.assertEqual(result["status"], "synced")
            self.assertEqual(result["covers_downloaded"], 1)
            refreshed = repo.get_by_id(work.id)
            self.assertIsNotNone(refreshed.cover_path)
            self.assertEqual(Path(refreshed.cover_path).read_bytes(), b"fake")

    def test_newer_remote_change_is_downloaded_then_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            repo = SQLiteWorkRepository(Path(td) / "db.sqlite", Path(td) / "covers")
            work = repo.create(name="Local")
            repo.mark_all_synced()
            remote = repo.export_sync_payload()
            remote["works"][0]["name"] = "Remote"
            remote["works"][0]["publication_status"] = "Em hiato"
            remote["works"][0]["reading_url"] = "https://example.com/remoto"
            remote["works"][0]["updated_at"] = "9999-01-01T00:00:00+00:00"
            adapter = FakeAdapter(remote)
            settings = FakeSettings(enabled=True)
            engine = SyncEngine(repo, settings, adapter_factory=lambda _cfg: adapter)
            result = engine.sync()
            self.assertEqual(result["status"], "synced")
            refreshed = repo.get_by_id(work.id)
            self.assertEqual(refreshed.name, "Remote")
            self.assertEqual(refreshed.publication_status, "Em hiato")
            self.assertEqual(refreshed.reading_url, "https://example.com/remoto")
            self.assertEqual(adapter.uploaded["works"][0]["name"], "Remote")


if __name__ == "__main__":
    unittest.main()
