import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from app.repositories.sqlite_repository import SQLiteWorkRepository


class ReleaseScheduleTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.repo = SQLiteWorkRepository(db_path=root / "reader.db", covers_dir=root / "covers")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_release_day_is_normalized(self):
        work = self.repo.create(
            name="Manhwa", progress_unit="Capítulo", progress_current=305,
            progress_total=None, status="Lendo", release_day="terça-feira",
        )
        self.assertEqual(self.repo.get_by_id(work.id).release_day, "Terça-feira")

    def test_calendar_includes_next_release_for_ongoing_chapter_work(self):
        work = self.repo.create(
            name="Manhwa", progress_unit="Capítulo", progress_current=305,
            progress_total=None, status="Lendo", release_day="Quarta-feira",
        )
        # The implementation uses date.today internally; assert semantics rather than a fixed date.
        events = self.repo.list_calendar_events()
        release = [e for e in events if e["work_id"] == work.id and e["type"] == "Próximo lançamento"]
        self.assertEqual(len(release), 1)
        self.assertGreaterEqual(release[0]["date"], date.today().isoformat())


if __name__ == "__main__":
    unittest.main()
