"""Renderer podsumowan (karta 1080x1920) w czystym Pillow.

Wspolny dla desktopu i Androida (na Androidzie nie ma PySide6/Qt).
Kontrakt: render_summary_card(profile_name, period_label, summary[, cover_dir])
zwraca obiekt PIL Image; save_summary_card zapisuje PNG i zwraca bool.
"""
import hashlib
import os
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from core.stats import format_listening
from core.tags import display_title

CARD_W = 1080
CARD_H = 1920

BG_TOP = "#0a0f1e"
BG_BOTTOM = "#16213a"
ACCENT = "#3d7bff"
ACCENT_LIGHT = "#5c90ff"
MUTED = "#93a4c7"
WHITE = "#ffffff"
CARD_BG = "#111a30"
COVER_BG = "#22304f"

COVER_SIZE = 150
SIDE_MARGIN = 70

_WEIGHT_FILES = {
    "regular": ["segoeui.ttf", "Roboto-Regular.ttf"],
    "medium": ["segoeuisb.ttf", "Roboto-Medium.ttf", "segoeui.ttf", "Roboto-Regular.ttf"],
    "semibold": ["segoeuisb.ttf", "Roboto-Medium.ttf", "segoeuib.ttf", "Roboto-Bold.ttf"],
    "bold": ["segoeuib.ttf", "Roboto-Bold.ttf"],
}

_FONT_DIRS = [
    r"C:\Windows\Fonts",
    "/system/fonts",
    "/usr/share/fonts/truetype/roboto",
]


@lru_cache(maxsize=32)
def _font_path(weight):
    for directory in _FONT_DIRS:
        if not os.path.isdir(directory):
            continue
        for name in _WEIGHT_FILES.get(weight, _WEIGHT_FILES["regular"]):
            candidate = os.path.join(directory, name)
            if os.path.isfile(candidate):
                return candidate
    return None


@lru_cache(maxsize=64)
def _font(size, weight="regular"):
    path = _font_path(weight)
    if path:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    try:
        return ImageFont.load_default(size)
    except Exception:
        return ImageFont.load_default()


def _top(counts, n):
    items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower()))
    return items[:n]


def _best_path_for_artist(artist, play_counts):
    best = None
    best_count = -1
    for path, count in play_counts.items():
        from core.stats import _artist_of

        if _artist_of(path) == artist and count > best_count:
            best, best_count = path, count
    return best


def _cover_cache_path(path, cover_dir):
    if not cover_dir:
        return None
    try:
        key = hashlib.md5(str(path).encode("utf-8", "replace")).hexdigest()
        candidate = os.path.join(cover_dir, key + ".png")
        return candidate if os.path.isfile(candidate) else None
    except Exception:
        return None


def _cover_image(path, cover_dir, size):
    """Okładka kwadrat (size x size, zaokraglone rogi) albo None."""
    cache = _cover_cache_path(path, cover_dir)
    source = None
    if cache:
        try:
            source = Image.open(cache).convert("RGB")
        except Exception:
            source = None
    if source is None:
        try:
            from io import BytesIO

            from core.cover import extract_cover

            data = extract_cover(path)
            if data:
                source = Image.open(BytesIO(data)).convert("RGB")
        except Exception:
            source = None
    if source is None:
        return None
    w, h = source.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    square = source.crop((left, top, left + side, top + side)).resize((size, size), Image.LANCZOS)

    mask = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, size - 1, size - 1], radius=size // 8, fill=255)
    rounded = Image.new("RGBA", (size, size))
    rounded.paste(square, (0, 0), mask)
    return rounded


def _draw_elided(draw, box, text, font, color):
    x, y, width = box
    fill = color
    if draw.textlength(text, font=font) <= width:
        draw.text((x, y), text, font=font, fill=fill, anchor="lm")
        return
    ellipsis = "\u2026"
    low, high = 0, len(text)
    while low < high:
        mid = (low + high + 1) // 2
        if draw.textlength(text[:mid] + ellipsis, font=font) <= width:
            low = mid
        else:
            high = mid - 1
    draw.text((x, y), text[:low] + ellipsis, font=font, fill=fill, anchor="lm")


def _draw_cover(canvas, draw, image, x, y, size, rank):
    """Rysuje okładke w zaokraglonej ramce; bez obrazka — numer rankingu."""
    radius = 22
    if image is None:
        draw.rounded_rectangle([x, y, x + size - 1, y + size - 1], radius=radius, fill=COVER_BG)
        draw.text(
            (x + size / 2, y + size / 2),
            str(rank),
            font=_font(64, "bold"),
            fill=ACCENT_LIGHT,
            anchor="mm",
        )
        return
    mask = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    padded = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    padded.paste(image, (0, 0), mask)
    canvas.paste(padded, (x, y), padded)


def _gradient_background(width, height, top, bottom):
    base = Image.new("RGB", (1, height))
    top_rgb = _hex_rgb(top)
    bottom_rgb = _hex_rgb(bottom)
    for i in range(height):
        t = i / max(1, height - 1)
        base.putpixel(
            (0, i),
            tuple(int(top_rgb[c] + (bottom_rgb[c] - top_rgb[c]) * t) for c in range(3)),
        )
    return base.resize((width, height), Image.LANCZOS)


def _hex_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def render_summary_card(profile_name, period_label, summary, cover_dir=None):
    """Zwraca PIL Image z karta podsumowania (1080x1920)."""
    summary = summary or {}
    play_counts = summary.get("play_counts") or {}
    artist_counts = summary.get("artist_counts") or {}
    listening = summary.get("listening_seconds", 0)

    img = _gradient_background(CARD_W, CARD_H, BG_TOP, BG_BOTTOM).convert("RGBA")
    draw = ImageDraw.Draw(img, "RGBA")

    draw.rectangle([0, 0, CARD_W, 14], fill=ACCENT)
    draw.ellipse([CARD_W - 220, 140, CARD_W - 220 + 260, 140 + 260], fill=ACCENT_LIGHT)
    draw.ellipse([-120, CARD_H - 320, -120 + 340, CARD_H - 320 + 340], fill="#1a2745")

    x = SIDE_MARGIN
    width = CARD_W - 2 * SIDE_MARGIN

    _draw_elided(draw, (x, 136, width), (profile_name or "").upper(), _font(38, "semibold"), MUTED)
    _draw_elided(draw, (x, 218, width), period_label or "", _font(78, "bold"), WHITE)

    draw.rounded_rectangle([x, 340, x + width - 1, 340 + 260 - 1], radius=26, fill=CARD_BG)
    _draw_elided(draw, (x + 40, 392, width - 80), "CZAS SŁUCHANIA", _font(28, "semibold"), MUTED)
    _draw_elided(draw, (x + 40, 480, width - 80), format_listening(listening), _font(88, "bold"), WHITE)
    total_plays = sum(play_counts.values())
    _draw_elided(
        draw,
        (x + 40, 570, width - 80),
        "Liczba odsłuchań: {}".format(total_plays),
        _font(32, "semibold"),
        ACCENT_LIGHT,
    )

    y = 610
    _draw_elided(draw, (x, y, width), "TOP UTWORY", _font(38, "bold"), WHITE)
    y += 76
    for i, (path, count) in enumerate(_top(play_counts, 3), start=1):
        draw.rounded_rectangle([x, y, x + width - 1, y + COVER_SIZE - 1], radius=26, fill=CARD_BG)
        cover = _cover_image(path, cover_dir, COVER_SIZE)
        _draw_cover(img, draw, cover, x + 22, y + 14, COVER_SIZE, i)
        name = display_title(path, os.path.splitext(os.path.basename(path))[0])
        _draw_elided(draw, (x + 200, y + 50, width - 280), name, _font(32, "semibold"), WHITE)
        _draw_elided(
            draw, (x + 200, y + 106, width - 280), "{} odsłuchań".format(count), _font(26, "regular"), MUTED
        )
        y += COVER_SIZE + 26

    y += 24
    _draw_elided(draw, (x, y, width), "TOP WYKONAWCY", _font(38, "bold"), WHITE)
    y += 76
    for i, (artist, count) in enumerate(_top(artist_counts, 3), start=1):
        draw.rounded_rectangle([x, y, x + width - 1, y + COVER_SIZE - 1], radius=26, fill=CARD_BG)
        example_path = _best_path_for_artist(artist, play_counts)
        cover = _cover_image(example_path, cover_dir, COVER_SIZE) if example_path else None
        _draw_cover(img, draw, cover, x + 22, y + 14, COVER_SIZE, i)
        _draw_elided(draw, (x + 200, y + 50, width - 280), artist, _font(32, "semibold"), WHITE)
        _draw_elided(
            draw, (x + 200, y + 106, width - 280), "{} odsłuchań".format(count), _font(26, "regular"), MUTED
        )
        y += COVER_SIZE + 26

    draw.text((CARD_W / 2, CARD_H - 48), "MusicBox by Szymon Mazur", font=_font(26, "regular"), fill=MUTED, anchor="mm")

    return img.convert("RGB")


def save_summary_card(profile_name, period_label, summary, path, cover_dir=None):
    try:
        image = render_summary_card(profile_name, period_label, summary, cover_dir=cover_dir)
        image.save(path, "PNG")
        return True
    except Exception:
        return False
