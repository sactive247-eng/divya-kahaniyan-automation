import json
import os
import random
import re
import time

import requests
from google import genai


PRIMARY_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
BACKUP_MODEL = os.getenv("GEMINI_BACKUP_MODEL", "gemini-3.5-flash-lite")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
MAX_ATTEMPTS_PER_MODEL = 3
GROQ_MAX_ATTEMPTS = 2
GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"


def _is_transient_error(error):
    """Detect temporary transport failures that have no HTTP status code."""
    if _get_status_code(error) in RETRYABLE_STATUS_CODES:
        return True
    names = ("timeout", "connecterror", "connectionerror", "networkerror", "remoteprotocolerror", "transporterror")
    current = error
    for _ in range(4):
        if current is None:
            break
        if any(token in type(current).__name__.lower() for token in names):
            return True
        current = current.__cause__ or current.__context__
    message = str(error).lower()
    return any(token in message for token in ("server disconnected", "connection reset", "connection aborted", "temporarily unavailable", "timed out"))
def _get_status_code(error):
    """Read HTTP status from different SDK and requests exception versions."""
    for attribute in ("code", "status_code"):
        value = getattr(error, attribute, None)
        try:
            if value is not None:
                return int(value)
        except (TypeError, ValueError):
            pass

    response = getattr(error, "response", None)
    value = getattr(response, "status_code", None)
    try:
        if value is not None:
            return int(value)
    except (TypeError, ValueError):
        pass

    message = str(error)
    match = re.search(r"\\b(408|429|500|502|503|504)\\b", message)
    if match:
        return int(match.group(1))

    for argument in getattr(error, "args", ()):
        match = re.search(r"\\b(408|429|500|502|503|504)\\b", str(argument))
        if match:
            return int(match.group(1))

    return None


def _format_clock(value):
    if not isinstance(value, str):
        return value
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", value.strip())
    if not match:
        return value
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour < 24 or hour > 47 or minute > 59:
        return value
    h = hour - 24
    if h == 0: period, shown = "रात", 12
    elif h < 12: period, shown = "सुबह", h
    elif h < 16: period, shown = "दोपहर", h - 12
    else: period, shown = "शाम", h - 12
    return f"अगले दिन {period} {shown}:{minute:02d} बजे"

def _is_timing_key(key):
    if not isinstance(key, str):
        return False
    key = key.lower()
    return any(term in key for term in (
        "sunrise", "sunset", "moonrise", "moonset",
        "rahu", "yama", "gulika", "gulikai", "karana",
        "tithi", "nakshatra", "yoga", "ends", "end_time",
        "start_time", "rise", "set", "kalam",
    ))


def _format_source_minutes(value):
    """Convert source API minute-of-day integers to HH:MM, retaining next-day hours."""
    if isinstance(value, bool) or not isinstance(value, int):
        return value
    if value < 0 or value > 2879:
        return value
    hour, minute = divmod(value, 60)
    return f"{hour:02d}:{minute:02d}"


def _narration_ready(value, key=None):
    if isinstance(value, dict):
        return {
            child_key: _narration_ready(item, child_key)
            for child_key, item in value.items()
        }
    if isinstance(value, list):
        return [_narration_ready(item, key) for item in value]
    if _is_timing_key(key) and isinstance(value, int) and not isinstance(value, bool):
        value = _format_source_minutes(value)
    return _format_clock(value)

def _normalize_next_day_times(text):
    """Correct next-day times whether the model writes digits or Hindi speech."""
    if not isinstance(text, str):
        return text

    # Spoken Hindi form, e.g. "रात 29 बजकर 41 मिनट".
    text = re.sub(
        r"(?:(?:अगले दिन)\s*)?(?:रात|सुबह|दोपहर|शाम)?\s*"
        r"(2[4-9]|[3-4]\d)\s*बजकर\s*([0-5]\d)\s*मिनट",
        lambda match: (
            f"अगले दिन {('रात' if int(match.group(1)) - 24 == 0 else 'सुबह' if int(match.group(1)) - 24 < 12 else 'दोपहर' if int(match.group(1)) - 24 < 16 else 'शाम')} "
            f"{(int(match.group(1)) - 24) % 12 or 12} बजकर {match.group(2)} मिनट"
        ),
        text,
    )

    # Numeric clock form, e.g. "29:41".
    return re.sub(
        r"(?<!\d)(2[4-9]|[3-4]\d):([0-5]\d)(?!\d)",
        lambda match: _format_clock(f"{match.group(1)}:{match.group(2)}"),
        text,
    )

def _build_prompt(panchang):
    panchang = _narration_ready(panchang)
    return f"""
You are the Hindi devotional content writer for Divya Kahaniyan.

Use ONLY this verified Panchang data. The API stores timing values as minutes from midnight; timing fields have already been converted to clock values. Times after midnight are preformatted in Hindi as the next day.
Treat every supplied timing as LOCKED SOURCE DATA. Copy its exact time and meaning. Never alter, recalculate, round, substitute or infer any timing. If a timing is supplied, it must remain exactly the same in the narration.
{json.dumps(panchang, ensure_ascii=False)}

Create a natural Hindi Panchang narration of approximately 60–75 seconds.
The supplied day.weekday_hi is the authoritative Hindi weekday calculated from
the ISO calendar date. Use it exactly; never infer the weekday yourself.
The supplied day.date is authoritative. If the weekday field is missing, do
not guess a weekday; flag it for review in the caption.
Do not sacrifice important Panchang details to meet the duration.
Include complete start and end timings for Rahu Kaal, Tithi, Nakshatra,
Yoga and Karana wherever available.
If a timing is unavailable in the source, omit it and flag it for review.
Never invent or calculate timings.

RULES:
1. Use simple, natural Hindi.
2. Explain Sanskrit terms in everyday Hindi.
3. Never invent timings or religious facts.
4. Never calculate missing timings.
5. Mention Delhi as the location.
6. Include date and weekday.
7. Include a short devotional thought.
8. Use only entries in verified_festivals for festival names; if the list is empty, do not mention a festival. These entries have been independently matched to the requested Delhi date.
9. When verified_festivals contains entries, mention their exact names naturally and briefly. Do not infer puja methods, timings or significance not present in the data. Preserve the supplied names; do not substitute a different festival.
10. Keep tone respectful and warm.
11. Proofread the complete Hindi narration before returning it. Check Devanagari matras,
    spelling, gender agreement, sentence flow and natural spoken Hindi.
12. Prefer natural spoken phrases such as "द्वादशी तिथि शुरू होगी" instead of
    awkward compounds such as "द्वादशी तिथिारंभ होगी".
13. Preserve the supplied time meaning exactly. Times beginning with अगले दिन must be spoken as written; never say values such as 28:43 बजे. Do not calculate, round or omit a verified time.
14. Do not invent festival names. Mention a festival only when an explicit verified festival field exists in the supplied data.
15. Keep every date and Panchang name exactly as supplied. Do not change,
    infer, round or omit a verified time during proofreading.
16. Read the narration once as if speaking it aloud; remove typographical errors
    and unnatural constructions without changing the facts.
17. Output narration in clean Devanagari. Avoid unnecessary English words.

Return ONLY valid JSON:
{{
  "title": "आज का पंचांग",
  "voice": "female or male",
  "narration": "Complete Hindi narration",
  "caption": "Short Hindi social media caption"
}}

VOICE SELECTION:
- Normal daily Panchang: female.
- Major festival or vrat narration: male.
"""


def _parse_script(response_text, provider):
    if not isinstance(response_text, str) or not response_text.strip():
        raise ValueError(f"{provider} returned an empty response.")

    cleaned = response_text.strip()
    cleaned = re.sub(r"^`{3}(?:json)?\s*|\s*`{3}$", "", cleaned).strip()

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise ValueError(f"{provider} response was not valid JSON.") from error

    if not isinstance(result, dict):
        raise ValueError(f"{provider} returned an invalid JSON object.")
    if result.get("voice") not in {"female", "male"}:
        raise ValueError(f"{provider} returned an invalid voice selection.")
    if not isinstance(result.get("narration"), str) or not result["narration"].strip():
        raise ValueError(f"{provider} returned an empty narration.")
    if not isinstance(result.get("caption"), str):
        raise ValueError(f"{provider} returned an invalid caption.")

    # Normalize Unicode and whitespace before this exact text is sent to both
    # Edge TTS and the subtitle renderer.
    import unicodedata
    result["narration"] = unicodedata.normalize("NFC", result["narration"])
    result["narration"] = re.sub(r"\s+", " ", result["narration"]).strip()
    result["narration"] = _normalize_next_day_times(result["narration"])
    result["caption"] = _normalize_next_day_times(result["caption"])
    if len(result["narration"]) < 120:
        raise ValueError(f"{provider} narration is unexpectedly short; refusing low-quality output.")
    return result


def _generate_with_groq(prompt):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not configured in GitHub Secrets.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are the Hindi devotional content writer for Divya Kahaniyan. "
                    "Follow the user's instructions exactly and return only valid JSON."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.6,
        "max_completion_tokens": 1800,
        "response_format": {"type": "json_object"},
    }

    last_error = None
    for attempt in range(1, GROQ_MAX_ATTEMPTS + 1):
        try:
            print(
                f"Groq: trying model '{GROQ_MODEL}' "
                f"(attempt {attempt}/{GROQ_MAX_ATTEMPTS})"
            )
            response = requests.post(
                GROQ_CHAT_URL,
                headers=headers,
                json=payload,
                timeout=90,
            )
            response.raise_for_status()
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            result = _parse_script(content, "Groq")
            result["generated_by"] = f"Groq ({GROQ_MODEL})"
            print(f"Groq script generated successfully with '{GROQ_MODEL}'.")
            return result

        except Exception as error:
            last_error = error
            status = _get_status_code(error)

            if status in RETRYABLE_STATUS_CODES and attempt < GROQ_MAX_ATTEMPTS:
                wait_seconds = (5 * (2 ** (attempt - 1))) + random.uniform(0, 3)
                print(
                    f"Temporary Groq HTTP {status}; retrying in "
                    f"{wait_seconds:.1f} seconds. Details: {error}"
                )
                time.sleep(wait_seconds)
                continue

            break

    raise RuntimeError(
        f"Groq fallback failed for model '{GROQ_MODEL}'"
        + (f" (HTTP {_get_status_code(last_error)})"
           if _get_status_code(last_error) is not None else "")
        + f": {last_error}"
    ) from last_error


def generate_script(panchang):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured in GitHub Secrets.")

    client = genai.Client(api_key=api_key)
    prompt = _build_prompt(panchang)
    models = list(dict.fromkeys([PRIMARY_MODEL, BACKUP_MODEL]))
    last_error = None

    for model in models:
        for attempt in range(1, MAX_ATTEMPTS_PER_MODEL + 1):
            try:
                print(
                    f"Gemini: trying model '{model}' "
                    f"(attempt {attempt}/{MAX_ATTEMPTS_PER_MODEL})"
                )
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                )
                result = _parse_script(getattr(response, "text", None), "Gemini")
                result["generated_by"] = f"Gemini ({model})"
                print(f"Gemini script generated successfully with '{model}'.")
                return result

            except Exception as error:
                last_error = error
                status = _get_status_code(error)

                if _is_transient_error(error):
                    if attempt < MAX_ATTEMPTS_PER_MODEL:
                        wait_seconds = (5 * (2 ** (attempt - 1))) + random.uniform(0, 3)
                        print(
                            f"Temporary Gemini transport/HTTP failure (status={status}) from '{model}'. "
                            f"Retrying in {wait_seconds:.1f} seconds. Details: {error}"
                        )
                        time.sleep(wait_seconds)
                        continue

                    print(
                        f"Model '{model}' still unavailable after "
                        f"{MAX_ATTEMPTS_PER_MODEL} attempts; switching to next provider/model."
                    )
                    break

                if status == 404:
                    print(
                        f"Model '{model}' returned HTTP 404; "
                        "trying the next configured model/provider."
                    )
                    break

                raise RuntimeError(
                    f"Gemini request failed for model '{model}'"
                    + (f" (HTTP {status})" if status is not None else "")
                    + f": {error}"
                ) from error

    print(
        "Both configured Gemini models failed or were unavailable. "
        "Switching to independent Groq fallback."
    )
    try:
        return _generate_with_groq(prompt)
    except Exception as groq_error:
        raise RuntimeError(
            "Script generation failed with both Gemini models and the Groq fallback. "
            "No narration was created. "
            f"Last Gemini error: {last_error}. Groq error: {groq_error}"
        ) from groq_error
