import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_generator import _select_visual_theme


class PanchangFestivalThemeTests(unittest.TestCase):
    def test_7_november_2026_is_saturday(self):
        self.assertEqual(date(2026, 11, 7).strftime("%A"), "Saturday")

    def test_verified_shivratri_and_hanuman_puja_select_shiva_with_hanuman_scenes(self):
        data = {
            "day": {"date": "2026-11-07", "tithi_name": "Krishna Trayodashi"},
            "verified_festivals": [
                {"name": "Kali Chaudas", "verified": True},
                {"name": "Hanuman Puja", "verified": True},
                {"name": "Masik Shivratri", "verified": True},
            ],
        }
        key, theme, secondary = _select_visual_theme(data)
        self.assertEqual(key, "shiva")
        self.assertEqual(theme["label"], "महादेव की आराधना")
        self.assertIn("hanuman", secondary)

    def test_hindi_festival_names_are_recognized(self):
        data = {
            "verified_festivals": [
                {"name": "हनुमान पूजा"},
                {"name": "मासिक शिवरात्रि"},
            ]
        }
        key, _, secondary = _select_visual_theme(data)
        self.assertEqual(key, "shiva")
        self.assertIn("hanuman", secondary)

    def test_no_festival_does_not_infer_from_weekday(self):
        data = {"day": {"weekday": "Tuesday", "tithi_name": "Krishna Saptami"}}
        key, _, secondary = _select_visual_theme(data)
        self.assertEqual(key, "general")
        self.assertEqual(secondary, [])


if __name__ == "__main__":
    unittest.main()
