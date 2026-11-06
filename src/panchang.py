
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

BASE_URL = "https://shastrapanchangam.com/api/v1"


def _log_timing_fields(value, path=""):
    """Log source-provided inauspicious-period and Karana fields for schema review."""
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key).lower()
            item_path = f"{path}.{key}" if path else str(key)
            if any(term in key_text for term in ("rahu", "yama", "gulika", "karana")):
                preview = repr(item)
                if len(preview) > 500:
                    preview = preview[:497] + "..."
                print(f"Panchang timing field [{item_path}]: {preview}")
            if isinstance(item, (dict, list)):
                _log_timing_fields(item, item_path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            if isinstance(item, (dict, list)):
                _log_timing_fields(item, f"{path}[{index}]")

def get_panchang():
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    url = f"{BASE_URL}/day/delhi/{today.isoformat()}.json"

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    data = response.json()

    if data.get("day", {}).get("date") != today.isoformat():
        raise ValueError("Panchang date mismatch")

    day = data.get("day", {})
    _log_timing_fields(data)

    required = [
        "sunrise", "sunset", "tithi_name",
        "nakshatra_name", "yoga_name",
        "karana_name"
    ]

    missing = [key for key in required if day.get(key) is None]

    if missing:
        raise ValueError(f"Missing Panchang fields: {missing}")

    return data
