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


def _make_scene(index, title):
    palettes = [
        ((16, 20, 52), (118, 48, 64)),
        ((20, 27, 67), (150, 73, 48)),
        ((16, 38, 58), (93, 91, 67)),
        ((45, 22, 50), (135, 65, 44)),
        ((13, 23, 49), (100, 54, 76)),
    ]
    top, bottom = palettes[index % len(palettes)]
    image = _gradient(top, bottom).convert("RGBA")
    glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse((130, 180, 590, 640), fill=(255, 184, 95, 48))
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

    if index in (0, 1, 4):
        _draw_temple(draw, 1040, (26, 17, 35, 255))
    if index in (2, 3, 4):
        _draw_diya(draw, WIDTH // 2, 870, 0.9 if index == 2 else 0.65)

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


def generate_video(narration, audio_file, output=OUTPUT):
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
    scene_paths = []
    for index, title in enumerate(scene_titles):
        scene_path = work_dir / f"scene_{index}.jpg"
        _make_scene(index, title).save(scene_path, quality=92)
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
