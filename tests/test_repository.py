import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.repositories.sqlite_repository import SQLiteWorkRepository


class SQLiteWorkRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.repo = SQLiteWorkRepository(
            db_path=str(root / "reader.db"),
            covers_dir=str(root / "covers"),
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_fresh_database_starts_empty(self):
        self.assertEqual(self.repo.list_all(), [])
        self.assertEqual(self.repo.list_categories(), [])
        self.assertEqual(self.repo.list_goals(), [])
        self.assertEqual(self.repo.list_history(), [])

    def test_create_and_edit_work(self):
        work = self.repo.create(
            name="Duna",
            category="Livro",
            progress_unit="Página",
            progress_current=10,
            progress_total=100,
            status="Lendo",
            rating=3.5,
        )
        self.repo.update_work(
            work.id,
            name="Duna - edição",
            category="Livro",
            progress_unit="Capítulo",
            progress_current=12,
            progress_total=24,
            status="Pausado",
            rating=4.5,
            favorite=True,
        )
        updated = self.repo.get_by_id(work.id)
        self.assertEqual(updated.name, "Duna - edição")
        self.assertEqual(updated.progress_unit, "Capítulo")
        self.assertEqual(updated.progress_current, 12)
        self.assertEqual(updated.progress_total, 24)
        self.assertEqual(updated.status, "Pausado")
        self.assertEqual(updated.rating, 4.5)
        self.assertTrue(updated.favorite)
        descriptions = [item["description"] for item in self.repo.list_history()]
        self.assertTrue(any("Progresso" in item for item in descriptions))
        self.assertTrue(any("Status" in item for item in descriptions))

    def test_half_star_ratings(self):
        work = self.repo.create(name="Teste", rating=3.5)
        self.assertEqual(self.repo.get_by_id(work.id).rating, 3.5)
        self.repo.set_rating(work.id, 4.5)
        self.assertEqual(self.repo.get_by_id(work.id).rating, 4.5)
        with self.assertRaises(ValueError):
            self.repo.set_rating(work.id, 4.3)

    def test_filter_by_name_tag_category_status_notes_and_favorite(self):
        one = self.repo.create(
            name="Livro Azul",
            category="Livro",
            progress_unit="Página",
            status="Lendo",
            personal_notes="Personagem excelente",
            favorite=True,
        )
        self.repo.set_tags(one.id, ["fantasia", "favorito pessoal"])
        self.repo.create(
            name="Mangá Vermelho",
            category="Mangá",
            progress_unit="Capítulo",
            status="Concluído",
        )

        self.assertEqual(self.repo.list_filtered(search="Azul")[0].id, one.id)
        self.assertEqual(self.repo.list_filtered(search="fantasia")[0].id, one.id)
        self.assertEqual(self.repo.list_filtered(search="Personagem")[0].id, one.id)
        self.assertEqual(self.repo.list_filtered(category="Livro")[0].id, one.id)
        self.assertEqual(self.repo.list_filtered(status="Lendo")[0].id, one.id)
        self.assertEqual(self.repo.list_filtered(tag="fantasia")[0].id, one.id)
        self.assertEqual(self.repo.list_filtered(favorites_only=True)[0].id, one.id)

    def test_categories_can_be_created_renamed_and_deleted(self):
        self.repo.create_category("Livro")
        self.repo.rename_category("Livro", "Romance")
        self.assertEqual(self.repo.list_categories()[0]["name"], "Romance")
        self.repo.delete_category("Romance")
        self.assertEqual(self.repo.list_categories(), [])

    def test_category_rename_updates_works(self):
        work = self.repo.create(name="Teste", category="Livro")
        self.repo.rename_category("Livro", "Romance")
        self.assertEqual(self.repo.get_by_id(work.id).category, "Romance")

    def test_category_in_use_cannot_be_deleted(self):
        self.repo.create(name="Teste", category="Livro")
        with self.assertRaises(ValueError):
            self.repo.delete_category("Livro")

    def test_increment_auto_starts_and_completes_reading(self):
        work = self.repo.create(name="Teste", progress_total=2, status="Quero ler")
        self.repo.increment_progress(work.id)
        first = self.repo.get_by_id(work.id)
        self.assertEqual(first.status, "Lendo")
        self.assertIsNotNone(first.start_date)
        self.repo.increment_progress(work.id)
        finished = self.repo.get_by_id(work.id)
        self.assertEqual(finished.status, "Concluído")
        self.assertIsNotNone(finished.end_date)
        self.assertEqual(finished.progress_current, 2)
        self.repo.increment_progress(work.id)
        self.assertEqual(self.repo.get_by_id(work.id).progress_current, 2)
        self.repo.increment_progress(work.id, -1)
        reopened = self.repo.get_by_id(work.id)
        self.assertEqual(reopened.progress_current, 1)
        self.assertEqual(reopened.status, "Lendo")
        self.assertIsNone(reopened.end_date)

    def test_status_progress_and_dates_are_normalized(self):
        completed = self.repo.create(
            name="Finalizada", progress_current=20, progress_total=300, status="Concluído"
        )
        completed = self.repo.get_by_id(completed.id)
        self.assertEqual(completed.progress_current, 300)
        self.assertEqual(completed.status, "Concluído")
        self.assertIsNotNone(completed.end_date)

        started = self.repo.create(
            name="Já iniciada", progress_current=5, progress_total=100, status="Quero ler"
        )
        started = self.repo.get_by_id(started.id)
        self.assertEqual(started.status, "Lendo")
        self.assertIsNotNone(started.start_date)
        self.assertIsNone(started.end_date)

        full = self.repo.create(
            name="100 por cento", progress_current=10, progress_total=10, status="Pausado"
        )
        full = self.repo.get_by_id(full.id)
        self.assertEqual(full.status, "Concluído")
        self.assertIsNotNone(full.end_date)

    def test_decrement_never_goes_below_zero(self):
        work = self.repo.create(name="Teste")
        self.repo.increment_progress(work.id, -1)
        self.assertEqual(self.repo.get_by_id(work.id).progress_current, 0)

    def test_deleted_work_tags_do_not_pollute_filter(self):
        work = self.repo.create(name="Teste")
        self.repo.set_tags(work.id, ["tag órfã"])
        self.repo.mark_all_synced()
        self.repo.delete_work(work.id)
        self.assertNotIn("tag órfã", self.repo.list_tags())
        self.assertEqual(self.repo.list_all(), [])

    def test_goals_are_calculated_automatically(self):
        pages = self.repo.create(
            name="Livro",
            progress_unit="Página",
            progress_current=40,
            progress_total=100,
            status="Lendo",
        )
        self.repo.create_goal("Ler páginas", "pages", 100)
        self.repo.create_goal("Concluir obras", "books", 1)
        goals = {goal["goal_type"]: goal for goal in self.repo.list_goals()}
        self.assertEqual(goals["pages"]["current_value"], 40)
        self.assertEqual(goals["books"]["current_value"], 0)
        self.repo.update_work(
            pages.id,
            name="Livro",
            category="",
            progress_unit="Página",
            progress_current=100,
            progress_total=100,
            status="Concluído",
        )
        goals = {goal["goal_type"]: goal for goal in self.repo.list_goals()}
        self.assertEqual(goals["pages"]["current_value"], 100)
        self.assertEqual(goals["books"]["current_value"], 1)

    def test_dated_goal_uses_net_progress_corrections(self):
        work = self.repo.create(name="Livro", progress_total=100, status="Quero ler")
        self.repo.increment_progress(work.id, 10)
        self.repo.increment_progress(work.id, -3)
        self.repo.create_goal("Páginas no período", "pages", 100, start_date="2000-01-01", end_date="2999-12-31")
        goal = self.repo.list_goals()[0]
        self.assertEqual(goal["current_value"], 7)

    def test_sync_export_contains_recalculated_goal_progress(self):
        self.repo.create(name="Livro", progress_unit="Página", progress_current=25, progress_total=100, status="Lendo")
        self.repo.create_goal("Meta", "pages", 100)
        payload = self.repo.export_sync_payload()
        self.assertEqual(payload["goals"][0]["current_value"], 25)

    def test_remote_invalid_optional_fields_do_not_break_library(self):
        remote = {
            "categories": [],
            "works": [{
                "id": "remote-invalid", "name": "Remota", "category": "Livro",
                "progress_unit": "Palavra", "progress_current": "abc", "progress_total": "xyz",
                "status": "Status inexistente", "rating": 9.2, "favorite": False,
                "start_date": "data ruim", "end_date": "outra ruim",
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-02T00:00:00+00:00", "deleted_at": None,
                "tags": [],
            }],
            "goals": [], "history": [],
        }
        self.repo.merge_remote_payload(remote)
        work = self.repo.get_by_id("remote-invalid")
        self.assertEqual(work.progress_unit, "Página")
        self.assertEqual(work.progress_current, 0)
        self.assertIsNone(work.progress_total)
        self.assertEqual(work.status, "Quero ler")
        self.assertIsNone(work.rating)
        self.assertIsNone(work.start_date)
        self.assertIsNone(work.end_date)

    def test_sync_snapshot_merges_newer_remote(self):
        local = self.repo.create(name="Local", category="Livro")
        self.repo.mark_all_synced()
        remote = {
            "categories": [],
            "works": [{
                "id": local.id,
                "name": "Remote newer",
                "category": "Livro",
                "progress_unit": "Página",
                "progress_current": 12,
                "progress_total": 120,
                "status": "Lendo",
                "release_day": None,
                "synopsis": "",
                "rating": 4.5,
                "favorite": True,
                "personal_notes": "",
                "start_date": None,
                "end_date": None,
                "cover_remote_id": None,
                "cover_filename": None,
                "created_at": local.created_at,
                "updated_at": "9999-01-01T00:00:00+00:00",
                "deleted_at": None,
                "tags": ["remota"],
            }],
            "goals": [],
            "history": [],
        }
        result = self.repo.merge_remote_payload(remote)
        self.assertEqual(result["downloaded"], 1)
        updated = self.repo.get_by_id(local.id)
        self.assertEqual(updated.name, "Remote newer")
        self.assertEqual(updated.rating, 4.5)
        self.assertEqual(self.repo.get_tags(local.id), ["remota"])


class MigrationTests(unittest.TestCase):
    def test_old_database_is_migrated_without_seed_data(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "reader.db"
            conn = sqlite3.connect(db)
            conn.execute("""
                CREATE TABLE works (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL,
                    progress_unit TEXT NOT NULL, progress_current INTEGER NOT NULL DEFAULT 0,
                    progress_total INTEGER, status TEXT NOT NULL DEFAULT 'Quero ler',
                    release_day TEXT, synopsis TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    deleted_at TEXT, sync_status TEXT NOT NULL DEFAULT 'PENDING_CREATE'
                )
            """)
            conn.execute("""
                INSERT INTO works VALUES
                ('old-1','Legado','Livro','Página',5,100,'Lendo',NULL,'','2026-01-01','2026-01-02',NULL,'SYNCED')
            """)
            conn.commit()
            conn.close()

            repo = SQLiteWorkRepository(db, Path(td) / "covers")
            works = repo.list_all()
            self.assertEqual(len(works), 1)
            self.assertEqual(works[0].name, "Legado")
            self.assertEqual(repo.list_categories()[0]["name"], "Livro")
            check = sqlite3.connect(db)
            try:
                columns = {row[1] for row in check.execute("PRAGMA table_info(works)")}
            finally:
                check.close()
            self.assertIn("rating", columns)
            self.assertIn("cover_remote_id", columns)


if __name__ == "__main__":
    unittest.main()
