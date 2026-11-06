import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from panchang import extract_source_timings
from script_writer import _validate_source_timings, _build_social_caption


class SourceTimingValidationTests(unittest.TestCase):
    def test_extracts_clock_times_and_minute_values_without_mutating_payload(self):
        source = {
            "day": {
                "sunrise": "06:37",
                "sunset": "17:32",
                "tithi_name": "Krishna Trayodashi",
                "tithi_ends": 648,
                "rahu_kalam": 561,
                "yamagandam": 807,
            }
        }
        timings = extract_source_timings(source)
        values = {item["path"]: item["display"] for item in timings}
        self.assertEqual(values["day.sunrise"], "06:37")
        self.assertEqual(values["day.tithi_ends"], "10:48")
        self.assertEqual(values["day.rahu_kalam"], "09:21")
        self.assertEqual(values["day.yamagandam"], "13:27")
        self.assertNotIn("day.tithi_name", values)
        self.assertEqual(source["day"]["tithi_ends"], 648)

    def test_rejects_missing_source_time(self):
        timings = [{"path": "day.sunrise", "display": "06:37"},
                   {"path": "day.sunset", "display": "17:32"}]
        with self.assertRaisesRegex(ValueError, "day.sunset"):
            _validate_source_timings("सूर्योदय 6 बजकर 37 मिनट पर होगा।", timings)

    def test_accepts_all_source_times_in_spoken_hindi(self):
        timings = [{"path": "day.sunrise", "display": "06:37"},
                   {"path": "day.sunset", "display": "17:32"}]
        _validate_source_timings(
            "सूर्योदय 6 बजकर 37 मिनट और सूर्यास्त 17:32 पर होगा।", timings
        )

    def test_caption_has_date_location_and_hashtags(self):
        caption = _build_social_caption({
            "day": {
                "date": "2026-11-07",
                "weekday_hi": "शनिवार",
                "tithi_name": "कृष्ण त्रयोदशी",
                "nakshatra_name": "चित्रा",
            }
        })
        self.assertIn("07 November 2026", caption)
        self.assertIn("दिल्ली", caption)
        self.assertIn("#आजकापंचांग", caption)
        self.assertIn("#दिव्यकहानियाँ", caption)


if __name__ == "__main__":
    unittest.main()
