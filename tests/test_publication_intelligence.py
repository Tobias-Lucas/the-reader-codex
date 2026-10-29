import tempfile
import unittest
from datetime import date
from pathlib import Path

from app.repositories.sqlite_repository import SQLiteWorkRepository
from app.utils.releases import release_dates_between, next_release_date


class PublicationIntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.repo = SQLiteWorkRepository(root / "reader.db", root / "covers")

    def tearDown(self):
        self.temp.cleanup()

    def test_publication_status_and_reading_status_are_independent(self):
        work = self.repo.create(
            name="Serial", progress_unit="Capítulo", progress_current=12,
            status="Lendo", publication_status="Em lançamento",
            release_schedule_type="Semanal", release_days=["Segunda-feira"],
        )
        loaded = self.repo.get_by_id(work.id)
        self.assertEqual(loaded.status, "Lendo")
        self.assertEqual(loaded.publication_status, "Em lançamento")

    def test_completed_serial_requires_total(self):
        with self.assertRaises(ValueError):
            self.repo.create(
                name="Completo sem total", progress_unit="Capítulo",
                publication_status="Completo", progress_total=None,
            )

    def test_reading_url_is_validated(self):
        work = self.repo.create(name="Online", reading_url="https://example.com/read")
        self.assertEqual(self.repo.get_by_id(work.id).reading_url, "https://example.com/read")
        with self.assertRaises(ValueError):
            self.repo.create(name="Inválido", reading_url="javascript:alert(1)")

    def test_weekly_release_digest_yesterday_today_tomorrow(self):
        reference = date(2026, 10, 28)  # Wednesday
        self.repo.create(
            name="Terça", progress_unit="Capítulo", publication_status="Em lançamento",
            release_schedule_type="Semanal", release_days=["Terça-feira"],
        )
        self.repo.create(
            name="Quarta", progress_unit="Capítulo", publication_status="Em lançamento",
            release_schedule_type="Semanal", release_days=["Quarta-feira"],
        )
        self.repo.create(
            name="Quinta", progress_unit="Capítulo", publication_status="Em lançamento",
            release_schedule_type="Semanal", release_days=["Quinta-feira"],
        )
        digest = self.repo.list_release_digest(reference)
        self.assertEqual([x["title"] for x in digest["yesterday"]], ["Terça"])
        self.assertEqual([x["title"] for x in digest["today"]], ["Quarta"])
        self.assertEqual([x["title"] for x in digest["tomorrow"]], ["Quinta"])

    def test_pending_release_is_acknowledged_one_chapter_at_a_time(self):
        work = self.repo.create(
            name="Semanal", progress_unit="Capítulo", progress_current=100,
            publication_status="Em lançamento", release_schedule_type="Semanal",
            release_days=["Segunda-feira"], status="Lendo",
        )
        with self.repo._connect() as conn:
            conn.execute("UPDATE works SET last_release_read_date = '2026-10-12' WHERE id = ?", (work.id,))
        state = self.repo.get_release_state(work.id, reference=date(2026, 10, 26))
        self.assertEqual(state["pending_count"], 2)
        with self.repo._connect() as conn:
            acknowledged = self.repo._acknowledge_scheduled_releases_in_conn(conn, work.id, 1, reference=date(2026, 10, 26))
        self.assertEqual(acknowledged, "2026-10-19")
        state = self.repo.get_release_state(work.id, reference=date(2026, 10, 26))
        self.assertEqual(state["pending_count"], 1)

    def test_hiatus_preserves_schedule(self):
        work = self.repo.create(
            name="Hiato", progress_unit="Capítulo", progress_current=5,
            publication_status="Em lançamento", release_schedule_type="Semanal",
            release_days=["Sexta-feira"],
        )
        self.repo.set_publication_status(work.id, "Em hiato")
        paused = self.repo.get_by_id(work.id)
        self.assertEqual(paused.publication_status, "Em hiato")
        self.assertEqual(paused.release_schedule_type, "Semanal")
        self.assertIn("Sexta-feira", paused.release_days)
        self.repo.set_publication_status(work.id, "Em lançamento")
        resumed = self.repo.get_by_id(work.id)
        self.assertEqual(resumed.release_schedule_type, "Semanal")

    def test_inactivity_auto_pauses_reading_status(self):
        work = self.repo.create(
            name="Parado", progress_unit="Capítulo", progress_current=5,
            publication_status="Em lançamento", status="Lendo",
        )
        with self.repo._connect() as conn:
            conn.execute("UPDATE history SET created_at = '2026-08-01T12:00:00+00:00' WHERE work_id = ?", (work.id,))
            conn.execute("UPDATE works SET start_date = '2026-08-01' WHERE id = ?", (work.id,))
        changed = self.repo.apply_inactivity_rules(30, reference=date(2026, 10, 26))
        self.assertEqual(changed, 1)
        self.assertEqual(self.repo.get_by_id(work.id).status, "Pausado")

    def test_biweekly_and_monthly_schedules(self):
        fortnight = release_dates_between("Quinzenal", None, None, "2026-10-05", date(2026,10,1), date(2026,11,5))
        self.assertEqual([d.isoformat() for d in fortnight], ["2026-10-05", "2026-10-19", "2026-11-02"])
        monthly = release_dates_between("Mensal", None, 31, None, date(2026,2,1), date(2026,3,31))
        self.assertEqual([d.isoformat() for d in monthly], ["2026-02-28", "2026-03-31"])


if __name__ == "__main__":
    unittest.main()
