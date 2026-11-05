import math
import os
import random
import subprocess
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter


WIDTH = 720
HEIGHT = 1280
FPS = 25
OUTPUT = "daily_panchang.mp4"
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _font(size, bold=False):
    candidates = FONT_CANDIDATES[1:2] + FONT_CANDIDATES[:1] if bold else FONT_CANDIDATES
    for candidate in candidates:
        if os.path.exists(candidate):
            return ImageFont.truetype(candidate, size=size)
    raise FileNotFoundError(
        "No suitable Devanagari font found. Install fonts-noto-core in the workflow."
    )


def _gradient(top, bottom):
    image = Image.new("RGB", (WIDTH, HEIGHT))
    pixels = image.load()
    for y in range(HEIGHT):
        ratio = y / max(1, HEIGHT - 1)
        color = tuple(int(top[i] * (1 - ratio) + bottom[i] * ratio) for i in range(3))
        for x in range(WIDTH):
            pixels[x, y] = color
    return image


def _draw_temple(draw, y_base, color):
    # A simple temple silhouette used as a reusable branded visual motif.
    draw.rectangle((0, y_base, WIDTH, HEIGHT), fill=color)
    draw.rectangle((115, y_base - 105, 605, y_base), fill=color)
    draw.polygon([(245, y_base - 105), (360, y_base - 300), (475, y_base - 105)], fill=color)
    draw.polygon([(285, y_base - 220), (360, y_base - 390), (435, y_base - 220)], fill=color)
    draw.ellipse((345, y_base - 420, 375, y_base - 390), fill=color)
    draw.rectangle((330, y_base - 105, 390, y_base), fill=(30, 17, 30))


def _draw_diya(draw, cx, cy, scale=1.0):
    gold = (255, 184, 75)
    draw.ellipse((cx - int(95*scale), cy - int(15*scale),
                  cx + int(95*scale), cy + int(55*scale)), fill=(173, 76, 35))
    draw.pieslice((cx - int(95*scale), cy - int(55*scale),
                   cx + int(95*scale), cy + int(55*scale)), 0, 180, fill=gold)
    draw.ellipse((cx - int(16*scale), cy - int(130*scale),
                  cx + int(16*scale), cy - int(30*scale)), fill=(255, 218, 125))
    draw.ellipse((cx - int(35*scale), cy - int(105*scale),
                  cx + int(35*scale), cy - int(35*scale)), fill=(255, 245, 192))


VISUAL_THEMES = {
    "vishnu": {"label": "श्रीहरि की भक्ति", "top": (13, 30, 68), "bottom": (170, 112, 48), "glow": (255, 211, 112, 78), "symbol": "lotus"},
    "shiva": {"label": "महादेव की आराधना", "top": (8, 28, 48), "bottom": (70, 112, 124), "glow": (164, 224, 255, 78), "symbol": "trident"},
    "hanuman": {"label": "बजरंगबली की भक्ति", "top": (65, 19, 12), "bottom": (190, 78, 25), "glow": (255, 190, 80, 85), "symbol": "gada"},
    "lakshmi": {"label": "माँ लक्ष्मी की कृपा", "top": (66, 20, 53), "bottom": (190, 115, 42), "glow": (255, 220, 125, 90), "symbol": "lotus"},
    "moon": {"label": "चंद्रमा की शीतल आभा", "top": (8, 19, 49), "bottom": (73, 81, 123), "glow": (215, 226, 255, 95), "symbol": "moon"},
    "general": {"label": "आज का भक्तिमय संदेश", "top": (20, 24, 57), "bottom": (125, 57, 64), "glow": (255, 184, 95, 55), "symbol": "diya"},
}


def _select_visual_theme(panchang):
    """Choose a visual motif only from explicit observance/tithi data."""
    day = panchang.get("day", {}) if isinstance(panchang, dict) else {}
    festival_values = day.get("festivals") or panchang.get("festivals") or []
    if isinstance(festival_values, str):
        festival_values = [festival_values]
    festival_text = " ".join(str(item) for item in festival_values).lower()
    tithi = str(day.get("tithi_name", "")).lower()
    weekday = str(day.get("weekday") or day.get("day_name") or "").lower()

    # Explicit festival/observance names take priority over generic tithi cues.
    if any(word in festival_text for word in ("ekadashi", "vaikuntha", "prabodhini", "devutthana")):
        key = "vishnu"
    elif any(word in festival_text for word in ("shiv", "pradosh", "somvati")):
        key = "shiva"
    elif any(word in festival_text for word in ("hanuman", "bajarang", "sankatmochan")):
        key = "hanuman"
    elif any(word in festival_text for word in ("lakshmi", "deepavali", "diwali", "dhanteras")):
        key = "lakshmi"
    elif any(word in festival_text for word in ("purnima", "pournami", "full moon")):
        key = "moon"
    elif "ekadashi" in tithi:
        key = "vishnu"
    elif "amavasya" in tithi:
        key = "general"
    elif "purnima" in tithi or "poornima" in tithi:
        key = "moon"
    elif weekday == "monday":
        key = "shiva"
    elif weekday == "tuesday":
        key = "hanuman"
    elif weekday == "thursday":
        key = "vishnu"
    elif weekday == "friday":
        key = "lakshmi"
    else:
        key = "general"

    return key, VISUAL_THEMES[key]


def _draw_lotus(draw, cx, cy, scale=1.0, color=(255, 205, 120, 220)):
    for angle in range(0, 360, 45):
        import math
        rad = math.radians(angle)
        dx, dy = math.cos(rad), math.sin(rad)
        px, py = cx + int(dx * 43 * scale), cy + int(dy * 43 * scale)
        draw.ellipse((px-int(22*scale), py-int(38*scale), px+int(22*scale), py+int(38*scale)),
                     fill=color)
    draw.ellipse((cx-int(17*scale), cy-int(17*scale), cx+int(17*scale), cy+int(17*scale)),
                 fill=(255, 238, 180, 245))


def _draw_theme_symbol(draw, symbol, index):
    cx, cy = WIDTH // 2, 610 + (index % 2) * 22
    gold = (255, 218, 150, 225)
    if symbol == "lotus":
        _draw_lotus(draw, cx, cy, 1.45, gold)
    elif symbol == "trident":
        draw.line((cx, cy-115, cx, cy+105), fill=gold, width=13)
        draw.arc((cx-70, cy-130, cx+5, cy+5), 180, 310, fill=gold, width=11)
        draw.arc((cx-5, cy-130, cx+70, cy+5), 230, 360, fill=gold, width=11)
        draw.line((cx-68, cy-122, cx, cy-48, cx+68, cy-122), fill=gold, width=11)
    elif symbol == "gada":
        draw.ellipse((cx-42, cy-108, cx+42, cy-24), outline=gold, width=13)
        draw.line((cx, cy-24, cx, cy+125), fill=gold, width=18)
        draw.line((cx-38, cy+125, cx+38, cy+125), fill=gold, width=13)
    elif symbol == "moon":
        draw.ellipse((cx-82, cy-82, cx+82, cy+82), fill=(230, 235, 255, 220))
        draw.ellipse((cx-30, cy-105, cx+105, cy+30), fill=(30, 40, 78, 255))
    else:
        _draw_diya(draw, cx, cy+45, 1.05)


def _make_scene(index, title, theme):
    palettes = [
        (theme["top"], theme["bottom"]),
        (theme["top"], tuple(min(255, c + 12) for c in theme["bottom"])),
        (tuple(max(0, c - 5) for c in theme["top"]), theme["bottom"]),
        (theme["top"], tuple(min(255, c + 22) for c in theme["bottom"])),
        (theme["top"], theme["bottom"]),
    ]
    top, bottom = palettes[index % len(palettes)]
    image = _gradient(top, bottom).convert("RGBA")
    glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse((95, 160, 625, 700), fill=theme["glow"])
    glow = glow.filter(ImageFilter.GaussianBlur(75))
    image = Image.alpha_composite(image, glow)

    draw = ImageDraw.Draw(image)
    # Stars / floating light particles.
    random.seed(2026 + index)
    for _ in range(95):
        x = random.randint(20, WIDTH - 20)
        y = random.randint(40, 880)
        radius = random.choice([1, 2, 3])
        draw.ellipse((x-radius, y-radius, x+radius, y+radius), fill=(255, 226, 170, 145))

    # The central motif changes with the day's verified Panchang theme.
    _draw_theme_symbol(draw, theme["symbol"], index)
    _draw_temple(draw, 1060, (18, 15, 34, 255))
    if index in (1, 3, 4) or theme["symbol"] == "diya":
        _draw_diya(draw, WIDTH // 2, 900, 0.65)

    # Top and bottom dark translucent bands improve legibility.
    band = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    band_draw = ImageDraw.Draw(band)
    band_draw.rectangle((0, 0, WIDTH, 180), fill=(5, 8, 25, 105))
    band_draw.rectangle((0, 1030, WIDTH, HEIGHT), fill=(5, 8, 25, 120))
    image = Image.alpha_composite(image, band)
    draw = ImageDraw.Draw(image)

    title_font = _font(35, bold=True)
    small_font = _font(22)
    draw.text((WIDTH // 2, 65), "दिव्य कहानियाँ", font=title_font,
              fill=(255, 224, 166), anchor="mm", stroke_width=1, stroke_fill=(65, 30, 25))
    draw.text((WIDTH // 2, 125), title, font=small_font,
              fill=(255, 245, 220), anchor="mm")
    return image.convert("RGB")


def _split_narration(text):
    # Sentence-sized captions; punctuation is retained for natural pauses.
    pieces = []
    current = ""
    for sentence in text.replace("।", "।|").split("|"):
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(current) + len(sentence) <= 88:
            current = (current + " " + sentence).strip()
        else:
            if current:
                pieces.append(current)
            if len(sentence) <= 88:
                current = sentence
            else:
                words = sentence.split()
                current = ""
                for word in words:
                    if len(current) + len(word) + 1 > 78:
                        if current:
                            pieces.append(current)
                        current = word
                    else:
                        current = (current + " " + word).strip()
    if current:
        pieces.append(current)
    return pieces or [text.strip()]


def _write_subtitles(narration, duration, path):
    """Write ASS subtitles; libass/HarfBuzz handles Devanagari shaping."""
    segments = _split_narration(narration)
    weights = [max(1, len(segment)) for segment in segments]
    total = sum(weights)
    cursor = 0.0

    def stamp(seconds):
        centiseconds = int(round(seconds * 100))
        hours, remainder = divmod(centiseconds, 360000)
        minutes, remainder = divmod(remainder, 6000)
        secs, fraction = divmod(remainder, 100)
        return f"{hours}:{minutes:02d}:{secs:02d}.{fraction:02d}"

    with open(path, "w", encoding="utf-8-sig") as file:
        file.write(
            "[Script Info]\n"
            "Title: Divya Kahaniyan Hindi Captions\n"
            "ScriptType: v4.00+\n"
            "WrapStyle: 2\n"
            "ScaledBorderAndShadow: yes\n"
            "PlayResX: 720\n"
            "PlayResY: 1280\n\n"
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: Hindi,Noto Sans Devanagari,34,&H00FFFFFF,&H000000FF,"
            "&HCC09091A,&H80000000,1,0,0,0,100,100,0,0,1,3,1,2,48,48,118,1\n\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, "
            "MarginV, Effect, Text\n"
        )

        for number, (segment, weight) in enumerate(zip(segments, weights), start=1):
            start_time = cursor
            end_time = duration if number == len(segments) else cursor + duration * weight / total
            cursor = end_time
            words = segment.split()
            lines, line = [], ""
            for word in words:
                if len(line) + len(word) + 1 > 32 and line:
                    lines.append(line)
                    line = word
                else:
                    line = (line + " " + word).strip()
            if line:
                lines.append(line)
            subtitle = r"\N".join(lines[:2])
            file.write(f"Dialogue: 0,{stamp(start_time)},{stamp(end_time)},Hindi,,0,0,0,,{subtitle}\n")

def _probe_duration(audio_path):
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", audio_path,
        ],
        check=True, capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def generate_video(narration, audio_file, panchang=None, output=OUTPUT):
    audio_path = Path(audio_file)
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_file}")

    duration = _probe_duration(str(audio_path))
    if duration <= 0:
        raise ValueError("Audio duration is invalid.")

    work_dir = Path("video_work")
    work_dir.mkdir(exist_ok=True)
    scene_titles = [
        "आज का दैनिक पंचांग",
        "तिथि और नक्षत्र",
        "योग और करण",
        "राहुकाल और शुभ विचार",
        "आज का भक्तिमय संदेश",
    ]
    theme_key, theme = _select_visual_theme(panchang or {})
    print(f"Selected devotional visual theme: {theme_key} ({theme['label']})")
    scene_titles[0] = theme["label"]
    scene_paths = []
    for index, title in enumerate(scene_titles):
        scene_path = work_dir / f"scene_{index}.jpg"
        _make_scene(index, title, theme).save(scene_path, quality=92)
        scene_paths.append(scene_path)

    subtitle_path = work_dir / "captions.ass"
    _write_subtitles(narration, duration, subtitle_path)

    # Each still is gently animated with a slow zoom. Scene durations are
    # balanced across the actual voice duration; subtitles follow the narration.
    scene_duration = duration / len(scene_paths)
    inputs = []
    for scene_path in scene_paths:
        inputs.extend(["-framerate", str(FPS), "-loop", "1", "-t", f"{scene_duration:.3f}", "-i", str(scene_path)])

    filter_parts = []
    for index in range(len(scene_paths)):
        filter_parts.append(
            f"[{index}:v]scale=800:1422,zoompan=z='min(zoom+0.00035,1.08)':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d=1:s={WIDTH}x{HEIGHT}:fps={FPS},"
            f"setsar=1[v{index}]"
        )
    concat_inputs = "".join(f"[v{i}]" for i in range(len(scene_paths)))
    filter_parts.append(f"{concat_inputs}concat=n={len(scene_paths)}:v=1:a=0,")
    subtitle_filter = (
        f"subtitles={subtitle_path.as_posix()}:fontsdir=/usr/share/fonts/truetype/noto"
    )
    filter_parts[-1] += subtitle_filter + "[vout]"
    filter_complex = ";".join(filter_parts)

    command = [
        "ffmpeg", "-y", *inputs, "-i", str(audio_path),
        "-filter_complex", filter_complex,
        "-map", "[vout]", "-map", f"{len(scene_paths)}:a",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "128k",
        "-t", f"{duration:.3f}", "-movflags", "+faststart", output,
    ]
    print(f"Rendering vertical video ({duration:.1f} seconds)...")
    subprocess.run(command, check=True)
    print(f"Video generated: {output}")
    return output
