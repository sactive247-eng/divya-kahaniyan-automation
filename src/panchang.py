
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
    # Calendar weekday is deterministic from the ISO date; do not let an
    # upstream label or language model misstate Friday/Saturday.
    weekday_en = today.strftime("%A")
    weekday_hi = {
        "Monday": "सोमवार", "Tuesday": "मंगलवार", "Wednesday": "बुधवार",
        "Thursday": "गुरुवार", "Friday": "शुक्रवार", "Saturday": "शनिवार",
        "Sunday": "रविवार",
    }[weekday_en]
    day["weekday"] = weekday_en
    day["weekday_hi"] = weekday_hi
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


TIMING_KEY_TERMS = (
    "sunrise", "sunset", "moonrise", "moonset", "rahu", "yama",
    "gulika", "gulikai", "karana", "tithi", "nakshatra", "yoga",
    "start_time", "end_time", "starts_at", "ends_at", "start", "end",
    "rise", "set", "kalam", "kaal", "time",
)


def _is_source_timing_key(key):
    key = str(key).lower()
    # Avoid classifying names/numbers as times; require a time-like field name.
    return any(term in key for term in TIMING_KEY_TERMS)


def _source_time_display(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and 0 <= value <= 2879:
        hour, minute = divmod(value, 60)
        return f"{hour:02d}:{minute:02d}"
    if isinstance(value, str):
        text = value.strip()
        if text:
            return text
    return None


def extract_source_timings(payload):
    """Extract every timing-valued field from the original API payload, without mutating it."""
    found = []

    def walk(value, path=""):
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{path}.{key}" if path else str(key)
                if _is_source_timing_key(key):
                    if isinstance(child, list):
                        for index, item in enumerate(child):
                            display = _source_time_display(item)
                            if display is not None:
                                found.append({"path": f"{child_path}[{index}]", "display": display, "raw": item})
                    else:
                        display = _source_time_display(child)
                        if display is not None:
                            found.append({"path": child_path, "display": display, "raw": child})
                if isinstance(child, (dict, list)):
                    walk(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]")

    walk(payload)
    # Deduplicate the same source path if a nested timing structure was traversed.
    unique = {}
    for item in found:
        unique[item["path"]] = item
    return list(unique.values())
