"""Fetch location-specific festival dates from ShastraPanchangam."""
import requests

FESTIVAL_URL = "https://shastrapanchangam.com/api/v1/festivals.json"
SOURCE = "ShastraPanchangam festivals API"


def _date_matches(value, target):
    if isinstance(value, str):
        return value[:10] == target
    if isinstance(value, list):
        return any(_date_matches(item, target) for item in value)
    if isinstance(value, dict):
        # Date maps may use the date as a key, or store dates in their values.
        return target in value or any(_date_matches(item, target) for item in value.values())
    return False


def _records(payload):
    """Normalize list, wrapped-list, and keyed-object API response formats."""
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        raise ValueError(f"Unexpected festival response type: {type(payload).__name__}")

    for key in ("festivals", "items", "data", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            payload = value
            break

    # Some feeds are keyed by festival slug/name or by year instead of
    # returning a top-level array. Preserve the key as a fallback name.
    records = []
    for key, value in payload.items():
        if isinstance(value, dict):
            record = dict(value)
            record.setdefault("name", key)
            records.append(record)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    record = dict(item)
                    record.setdefault("name", key)
                    records.append(record)

    if records:
        return records
    raise ValueError(
        "Unrecognized festival API response structure; "
        f"top-level keys: {', '.join(map(str, payload.keys())) or '(none)'}"
    )


def get_verified_festivals(date, city="delhi"):
    """Return only festival records explicitly dated for the requested city."""
    if not isinstance(date, str) or len(date) < 10:
        raise ValueError(f"Invalid Panchang date: {date!r}")

    response = requests.get(FESTIVAL_URL, timeout=30)
    response.raise_for_status()
    payload = response.json()
    records = _records(payload)
    matches = []

    for item in records:
        if not isinstance(item, dict):
            continue
        local_dates = item.get("local_dates")
        city_dates = local_dates.get(city) if isinstance(local_dates, dict) else None
        dates = city_dates if city_dates is not None else item.get("dates")
        if dates is None:
            dates = item.get("date")
        if not _date_matches(dates, date[:10]):
            continue

        name = (
            item.get("name")
            or item.get("display_name")
            or item.get("title")
            or item.get("festival")
        )
        if not isinstance(name, str) or not name.strip():
            continue

        matches.append({
            "name": name.strip(),
            "date": date[:10],
            "city": city.title(),
            "source": SOURCE,
            "verified": True,
        })

    return matches
