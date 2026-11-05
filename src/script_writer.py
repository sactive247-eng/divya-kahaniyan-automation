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

                if status in RETRYABLE_STATUS_CODES:
                    if attempt < MAX_ATTEMPTS_PER_MODEL:
                        wait_seconds = (5 * (2 ** (attempt - 1))) + random.uniform(0, 3)
                        print(
                            f"Temporary Gemini HTTP {status} from '{model}'. "
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
