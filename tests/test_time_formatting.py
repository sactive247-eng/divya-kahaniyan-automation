import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from script_writer import _normalize_next_day_times


class NextDayTimeFormattingTests(unittest.TestCase):
    def test_normalizes_numeric_next_day_time(self):
        self.assertEqual(
            _normalize_next_day_times("नक्षत्र 29:53 तक रहेगा।"),
            "नक्षत्र अगले दिन सुबह 5:53 बजे तक रहेगा।",
        )

    def test_normalizes_spoken_hindi_next_day_time(self):
        self.assertEqual(
            _normalize_next_day_times("चंद्रमा रात 29 बजकर 41 मिनट पर उदय होगा।"),
            "चंद्रमा अगले दिन सुबह 5 बजकर 41 मिनट पर उदय होगा।",
        )

    def test_leaves_normal_times_unchanged(self):
        text = "सूर्योदय 06:37 और सूर्यास्त 17:32 पर होगा।"
        self.assertEqual(_normalize_next_day_times(text), text)

    def test_does_not_change_date_numbers(self):
        text = "आज 7 नवंबर 2026 है।"
        self.assertEqual(_normalize_next_day_times(text), text)


if __name__ == "__main__":
    unittest.main()
