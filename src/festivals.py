"""Fetch location-specific festival dates from ShastraPanchangam."""
import requests

FESTIVAL_URL = "https://shastrapanchangam.com/api/v1/festivals.json"


def _date_matches(value, target):
    if isinstance(value, str):
        return value[:10] == target
    if isinstance(value, list):
        return any(_date_matches(item, target) for item in value)
    if isinstance(value, dict):
        return any(_date_matches(item, target) for item in value.values())
    return False


def _records(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("festivals", "items", "data", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    raise ValueError("Unrecognized festival API response structure")


def get_verified_festivals(date, city="delhi"):
    """Return only festival records explicitly dated for the requested city."""
    response = requests.get(FESTIVAL_URL, timeout=30)
    response.raise_for_status()
    records = _records(response.json())
    matches = []
    for item in records:
        if not isinstance(item, dict):
            continue
        city_dates = item.get("local_dates", {}).get(city) if isinstance(item.get("local_dates"), dict) else None
        dates = city_dates if city_dates is not None else item.get("dates")
        if not _date_matches(dates, date):
            continue
        name = item.get("name") or item.get("display_name") or item.get("title") or item.get("festival")
        if not isinstance(name, str) or not name.strip():
            continue
        matches.append({
            "name": name.strip(),
            "date": date,
            "city": city.title(),
            "source": "ShastraPanchangam festivals API",
            "verified": True,
        })
    return matches
