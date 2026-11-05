
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

BASE_URL = "https://shastrapanchangam.com/api/v1"

def get_panchang():
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    url = f"{BASE_URL}/day/delhi/{today.isoformat()}.json"

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    data = response.json()

    if data.get("day", {}).get("date") != today.isoformat():
        raise ValueError("Panchang date mismatch")

    day = data.get("day", {})

    required = [
        "sunrise", "sunset", "tithi_name",
        "nakshatra_name", "yoga_name",
        "karana_name"
    ]

    missing = [key for key in required if day.get(key) is None]

    if missing:
        raise ValueError(f"Missing Panchang fields: {missing}")

    return data
