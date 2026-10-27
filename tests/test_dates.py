import unittest
from datetime import date

from app.utils.dates import br_to_iso, iso_to_br, next_release_label, next_weekday_date, normalize_weekday


class DateUtilityTests(unittest.TestCase):
    def test_brazilian_date_round_trip(self):
        self.assertEqual(br_to_iso("26/10/2026"), "2026-10-26")
        self.assertEqual(iso_to_br("2026-10-26"), "26/10/2026")

    def test_iso_input_remains_compatible(self):
        self.assertEqual(br_to_iso("2026-10-26"), "2026-10-26")

    def test_invalid_brazilian_date_is_rejected(self):
        with self.assertRaises(ValueError):
            br_to_iso("31/02/2026")

    def test_weekday_normalization(self):
        self.assertEqual(normalize_weekday("terça-feira"), "Terça-feira")
        self.assertEqual(normalize_weekday("SABADO"), "Sábado")

    def test_next_release_is_calculated_from_weekday(self):
        monday = date(2026, 10, 26)
        self.assertEqual(next_weekday_date("Quarta-feira", monday).isoformat(), "2026-10-28")
        self.assertEqual(next_release_label("Segunda-feira", monday), "Hoje, 26/10/2026")


if __name__ == "__main__":
    unittest.main()
