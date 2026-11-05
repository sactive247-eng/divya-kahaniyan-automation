
import asyncio
import edge_tts

VOICES = {
    "female": "hi-IN-SwaraNeural",
    "male": "hi-IN-MadhurNeural"
}

async def create_voice(text, voice, output="panchang.mp3"):
    selected_voice = VOICES.get(voice, VOICES["female"])

    communicate = edge_tts.Communicate(
        text=text,
        voice=selected_voice,
        rate="-5%",
        pitch="+0Hz"
    )

    await communicate.save(output)

def generate_voice(text, voice):
    asyncio.run(create_voice(text, voice))
    return "panchang.mp3"
