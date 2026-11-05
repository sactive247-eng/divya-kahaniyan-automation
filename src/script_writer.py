
import os
import json
import re
import time

from google import genai

PRIMARY_MODEL = os.getenv(
    "GEMINI_MODEL", "gemini-3.8-flash"
)

BACKUP_MODEL = os.getenv(
    "GEMINI_BACKUP_MODEL", "gemini-3.5-flash-lite"
)


def generate_script(panchang):

    api_key = os.environ["GEMINI_API_KEY"]
    client = genai.Client(api_key=api_key)

    prompt = f"""
You are the Hindi devotional content writer
for Divya Kahaniyan.

Use ONLY this verified Panchang data:
{json.dumps(panchang, ensure_ascii=False)}

Create a 45-60 second Hindi Panchang narration.

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

    models = [PRIMARY_MODEL, BACKUP_MODEL]

    retryable_codes = [429, 500, 502, 503, 504]

    for model in models:

        for attempt in range(3):

            try:
                print(
                    f"Trying {model}, attempt {attempt + 1}"
                )

                response = client.models.generate_content(
                    model=model,
                    contents=prompt
                )

                if not response.text:
                    raise ValueError("Empty Gemini response")

                text = response.text.strip()

                text = re.sub(
                    r"^```(?:json)?\s*|\s*```$",
                    "",
                    text
                ).strip()

                result = json.loads(text)

                if result.get("voice") not in [
                    "female", "male"
                ]:
                    raise ValueError("Invalid voice selection")

                if not result.get("narration"):
                    raise ValueError("Empty narration")

                print(f"Script generated using {model}")

                return result

            except Exception as error:

                status = getattr(error, "code", None)

                if status not in retryable_codes:
                    raise

                if attempt < 2:
                    wait = 2 ** (attempt + 1)

                    print(
                        f"Temporary Gemini error: {error}"
                    )
                    print(f"Retrying in {wait} seconds")

                    time.sleep(wait)

                else:
                    print(
                        f"{model} unavailable after retries"
                    )

    raise RuntimeError(
        "Both Gemini models failed. "
        "Please retry the workflow later."
    )
