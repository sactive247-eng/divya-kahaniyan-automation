import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from script_writer import _normalize_next_day_times, _narration_ready


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



    def test_converts_api_minutes_from_midnight(self):
        source = {
            "rahu_kalam": 561,
            "yamagandam": 807,
            "gulikai": 397,
            "karana_ends": 648,
            "sunrise": "06:37",
        }
        expected = {
            "rahu_kalam": "09:21",
            "yamagandam": "13:27",
            "gulikai": "06:37",
            "karana_ends": "10:48",
            "sunrise": "06:37",
        }
        self.assertEqual(_narration_ready(source), expected)

    def test_converts_minutes_beyond_midnight(self):
        source = {"moonrise": 1781, "nakshatra_ends": 1793, "yoga_ends": 1648}
        expected = {
            "moonrise": "अगले दिन सुबह 5:41 बजे",
            "nakshatra_ends": "अगले दिन सुबह 5:53 बजे",
            "yoga_ends": "अगले दिन सुबह 3:28 बजे",
        }
        self.assertEqual(_narration_ready(source), expected)

    def test_does_not_convert_unrelated_numeric_fields(self):
        source = {"date_number": 7, "weekday_number": 6}
        self.assertEqual(_narration_ready(source), source)


if __name__ == "__main__":
    unittest.main()
