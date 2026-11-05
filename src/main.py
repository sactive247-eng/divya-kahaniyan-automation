
import os
import json
import requests

from panchang import get_panchang
from script_writer import generate_script
from voice_generator import generate_voice

def send_telegram(message, audio_file=None):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    base = f"https://api.telegram.org/bot{token}"

    requests.post(
        f"{base}/sendMessage",
        data={
            "chat_id": chat_id,
            "text": message
        },
        timeout=30
    ).raise_for_status()

    if audio_file:
        with open(audio_file, "rb") as audio:
            response = requests.post(
                f"{base}/sendAudio",
                data={"chat_id": chat_id},
                files={"audio": audio},
                timeout=120
            )
            response.raise_for_status()

def main():
    print("Fetching Delhi Panchang...")
    data = get_panchang()

    print("Generating Hindi script...")
    script = generate_script(data)

    with open("daily_script.json", "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)

    print("Generating Hindi voice...")
    audio = generate_voice(
        script["narration"],
        script["voice"]
    )

    message = (
        "🙏 DIVYA KAHANIYAN\n"
        "आज का पंचांग\n\n"
        + script["narration"]
        + "\n\nSource: shastrapanchangam.com"
    )

    print("Sending results to Telegram...")
    send_telegram(message, audio)

    print("Phase 2 test completed successfully!")

if __name__ == "__main__":
    main()
