
import os
import json
from google import genai

def generate_script(panchang):
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    prompt = f"""
You are the Hindi devotional content writer for Divya Kahaniyan.

Use ONLY the following verified Panchang data:
{json.dumps(panchang, ensure_ascii=False)}

Create a 45-60 second Hindi Panchang narration.

Rules:
1. Use simple, natural Hindi.
2. Explain Sanskrit terms in simple Hindi.
3. Never invent timings or religious facts.
4. Do not calculate missing timings.
5. Mention Delhi as the location.
6. Include date and weekday.
7. Include a short devotional thought.
8. Do not make unsupported festival or vrat claims.
9. Keep the tone respectful and warm.

Return ONLY valid JSON:
{{
  "title": "आज का पंचांग",
  "voice": "female or male",
  "narration": "Complete Hindi narration",
  "caption": "Short Hindi social media caption"
}}

Voice selection:
- Normal daily Panchang: female.
- Major festival or vrat narration: male.
"""
    response = client.models.generate_content(
        model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
        contents=prompt
    )

    text = response.text.strip()
    text = text.replace("```json", "").replace("```", "").strip()

    result = json.loads(text)

    if result["voice"] not in ["female", "male"]:
        raise ValueError("Invalid voice selection")

    if not result.get("narration"):
        raise ValueError("Empty narration")

    return result
