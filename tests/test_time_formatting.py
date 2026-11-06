import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from script_writer import _normalize_next_day_times


class NextDayTimeFormattingTests(unittest.TestCase):
    def test_normalizes_times_beyond_midnight(self):
        text = "चंद्रमा 29:41 पर, नक्षत्र 29:53 तक और योग 27:28 तक रहेगा।"
        expected = (
            "चंद्रमा अगले दिन सुबह 5:41 बजे पर, "
            "नक्षत्र अगले दिन सुबह 5:53 बजे तक और "
            "योग अगले दिन सुबह 3:28 बजे तक रहेगा।"
        )
        self.assertEqual(_normalize_next_day_times(text), expected)

    def test_leaves_normal_times_unchanged(self):
        text = "सूर्योदय 06:37 और सूर्यास्त 17:32 पर होगा।"
        self.assertEqual(_normalize_next_day_times(text), text)

    def test_does_not_change_date_numbers(self):
        text = "आज 7 नवंबर 2026 है।"
        self.assertEqual(_normalize_next_day_times(text), text)


if __name__ == "__main__":
    unittest.main()
