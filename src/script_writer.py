import json
import os
import random
import re
import time

from google import genai


PRIMARY_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
BACKUP_MODEL = os.getenv("GEMINI_BACKUP_MODEL", "gemini-3.5-flash-lite")

RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
MAX_ATTEMPTS_PER_MODEL = 3


def _get_status_code(error):
    """Read the HTTP status from different google-genai exception versions."""
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

    # google-genai versions differ in how APIError exposes the HTTP status.
    # Fall back to the rendered exception text, e.g. "503 UNAVAILABLE".
    message = str(error)
    match = re.search(r"\\b(408|429|500|502|503|504)\\b", message)
    if match:
        return int(match.group(1))

    # Some SDK exceptions keep the response details in args rather than
    # exposing a numeric .code or .status_code attribute.
    for argument in getattr(error, "args", ()):
        match = re.search(r"\\b(408|429|500|502|503|504)\\b", str(argument))
        if match:
            return int(match.group(1))

    return None


def _build_prompt(panchang):
    return f"""
You are the Hindi devotional content writer for Divya Kahaniyan.

Use ONLY this verified Panchang data:
{json.dumps(panchang, ensure_ascii=False)}

Create a natural Hindi Panchang narration of approximately 60–75 seconds.
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
8. Avoid unsupported festival claims.
9. Keep tone respectful and warm.

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


def _parse_script(response):
    response_text = getattr(response, "text", None)
    if not response_text:
        raise ValueError("Gemini returned an empty response.")

    cleaned = response_text.strip()
    cleaned = re.sub(r"^\x60{3}(?:json)?\s*|\s*\x60{3}$", "", cleaned).strip()

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise ValueError("Gemini response was not valid JSON.") from error

    if result.get("voice") not in {"female", "male"}:
        raise ValueError("Gemini returned an invalid voice selection.")
    if not isinstance(result.get("narration"), str) or not result["narration"].strip():
        raise ValueError("Gemini returned an empty narration.")
    if not isinstance(result.get("caption"), str):
        raise ValueError("Gemini returned an invalid caption.")

    return result


def generate_script(panchang):
    api_key = os.environ["GEMINI_API_KEY"]
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
                result = _parse_script(response)

                print(f"Gemini script generated successfully with '{model}'.")
                return result

            except Exception as error:
                last_error = error
                status = _get_status_code(error)

                if status in RETRYABLE_STATUS_CODES:
                    if attempt < MAX_ATTEMPTS_PER_MODEL:
                        # Exponential backoff plus a small random delay.
                        wait_seconds = (5 * (2 ** (attempt - 1))) + random.uniform(0, 3)
                        print(
                            f"Temporary Gemini HTTP {status} from '{model}'. "
                            f"Retrying in {wait_seconds:.1f} seconds. "
                            f"Details: {error}"
                        )
                        time.sleep(wait_seconds)
                        continue

                    print(
                        f"Model '{model}' still unavailable after "
                        f"{MAX_ATTEMPTS_PER_MODEL} attempts; switching to backup."
                    )
                    break

                # A 404 may mean this particular model is unavailable to the
                # account, so try the configured backup. Authentication,
                # permission and other non-transient errors should fail clearly.
                if status == 404:
                    print(
                        f"Model '{model}' returned HTTP 404; "
                        "trying the next configured model."
                    )
                    break

                raise RuntimeError(
                    f"Gemini request failed for model '{model}'"
                    + (f" (HTTP {status})" if status is not None else "")
                    + f": {error}"
                ) from error

    raise RuntimeError(
        "Gemini script generation failed with all configured models. "
        "The Panchang fetch may have succeeded, but no narration was created. "
        f"Last error: {last_error}"
    ) from last_error
