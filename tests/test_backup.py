import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from PIL import Image

from app.repositories.sqlite_repository import SQLiteWorkRepository
from app.services.backup_service import BackupService


class BackupServiceTests(unittest.TestCase):
    def test_full_backup_restores_metadata_tags_and_cover(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source_repo = SQLiteWorkRepository(root / "source.db", root / "source-covers")
            work = source_repo.create(
                name="Livro com capa",
                category="Livro",
                progress_current=20,
                progress_total=200,
                rating=4.5,
                favorite=True,
                reading_url="https://example.com/ler",
                publication_status="Completo",
            )
            source_repo.set_tags(work.id, ["fantasia", "teste"])
            source_image = root / "cover.png"
            Image.new("RGB", (20, 30), "white").save(source_image)
            source_repo.set_cover(work.id, source_image)

            backup = BackupService(source_repo, root / "source.db", root / "backups")
            zip_path = root / "library.zip"
            backup.export_full_backup(zip_path)
            self.assertTrue(zip_path.is_file())

            target_repo = SQLiteWorkRepository(root / "target.db", root / "target-covers")
            target_backup = BackupService(target_repo, root / "target.db", root / "target-backups")
            target_backup.import_full_backup(zip_path)

            restored = target_repo.list_all()[0]
            self.assertEqual(restored.name, "Livro com capa")
            self.assertEqual(restored.rating, 4.5)
            self.assertTrue(restored.favorite)
            self.assertEqual(restored.publication_status, "Completo")
            self.assertEqual(restored.reading_url, "https://example.com/ler")
            self.assertEqual(target_repo.get_tags(restored.id), ["fantasia", "teste"])
            self.assertTrue(Path(restored.cover_path).is_file())
            self.assertEqual(Path(restored.cover_path).parent, (root / "target-covers").resolve())

    def test_full_backup_rejects_cover_path_outside_internal_covers_folder(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            target = SQLiteWorkRepository(root / "target.db", root / "target-covers")
            existing = target.create(name="Preservada")
            service = BackupService(target, root / "target.db", root / "backups")

            payload = {
                "schema_version": 5,
                "works": [{
                    "id": "bad", "name": "Maliciosa", "category": "",
                    "progress_unit": "Página", "progress_current": 0, "progress_total": None,
                    "status": "Quero ler", "cover_path": "../outside.png",
                }],
                "history": [], "tags": [], "goals": [], "categories": [],
            }
            archive_path = root / "bad.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("library.json", json.dumps(payload))
                archive.writestr("covers/dummy.png", b"not-an-image")

            with self.assertRaises(ValueError):
                service.import_full_backup(archive_path)
            self.assertEqual(target.list_all()[0].id, existing.id)

    def test_json_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = SQLiteWorkRepository(root / "a.db", root / "covers-a")
            repo.create(name="A", category="Livro", rating=3.5)
            service = BackupService(repo, root / "a.db", root / "backups")
            json_path = root / "export.json"
            service.export_json(json_path)

            target = SQLiteWorkRepository(root / "b.db", root / "covers-b")
            target_service = BackupService(target, root / "b.db", root / "backups-b")
            target_service.import_json(json_path)
            self.assertEqual(target.list_all()[0].name, "A")
            self.assertEqual(target.list_all()[0].rating, 3.5)

    def test_category_progress_unit_survives_json_backup(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = SQLiteWorkRepository(root / "a.db", root / "covers-a")
            repo.create_category("Manhwa", "Capítulo")
            service = BackupService(repo, root / "a.db", root / "backups")
            json_path = root / "export.json"
            service.export_json(json_path)

            target = SQLiteWorkRepository(root / "b.db", root / "covers-b")
            target_service = BackupService(target, root / "b.db", root / "backups-b")
            target_service.import_json(json_path)
            restored = target.get_category("Manhwa")
            self.assertIsNotNone(restored)
            self.assertEqual(restored["progress_unit"], "Capítulo")


if __name__ == "__main__":
    unittest.main()
