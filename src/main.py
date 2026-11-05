import os
import json
import requests

from panchang import get_panchang
from script_writer import generate_script
from voice_generator import generate_voice
from video_generator import generate_video


def send_telegram(message, audio_file=None, video_file=None):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    base = f"https://api.telegram.org/bot{token}"

    requests.post(
        f"{base}/sendMessage",
        data={"chat_id": chat_id, "text": message},
        timeout=30,
    ).raise_for_status()

    if audio_file:
        with open(audio_file, "rb") as audio:
            response = requests.post(
                f"{base}/sendAudio",
                data={"chat_id": chat_id, "title": "Divya Kahaniyan - Aaj Ka Panchang"},
                files={"audio": audio},
                timeout=120,
            )
            response.raise_for_status()

    if video_file:
        with open(video_file, "rb") as video:
            response = requests.post(
                f"{base}/sendVideo",
                data={
                    "chat_id": chat_id,
                    "caption": "🙏 दिव्य कहानियाँ | आज का पंचांग",
                    "supports_streaming": "true",
                },
                files={"video": video},
                timeout=300,
            )
            response.raise_for_status()


def main():
    print("Fetching Delhi Panchang...")
    data = get_panchang()

    print("Generating Hindi script...")
    script = generate_script(data)

    with open("daily_script.json", "w", encoding="utf-8") as file:
        json.dump(script, file, ensure_ascii=False, indent=2)

    print("Generating Hindi voice...")
    audio = generate_voice(script["narration"], script["voice"])

    print("Generating vertical Panchang video...")
    video = generate_video(script["narration"], audio)

    provider = script.get("generated_by", "AI provider")
    message = (
        "🙏 DIVYA KAHANIYAN\\n"
        "आज का पंचांग\\n"
        f"Script provider: {provider}\\n\\n"
        + script["narration"]
        + "\\n\\nSource: shastrapanchangam.com"
    )

    print("Sending text, audio and video to Telegram...")
    send_telegram(message, audio, video)

    print("Phase 3 video generation completed successfully!")


if __name__ == "__main__":
    main()
