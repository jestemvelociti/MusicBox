import os

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPixmap,
)

from core.cover import extract_cover
from core.stats import format_listening
from core.tags import display_name

CARD_W = 1080
CARD_H = 1920

BG_TOP = QColor("#0a0f1e")
BG_BOTTOM = QColor("#16213a")
ACCENT = QColor("#3d7bff")
ACCENT_LIGHT = QColor("#5c90ff")
MUTED = QColor("#93a4c7")
WHITE = QColor("#ffffff")
CARD_BG = QColor("#111a30")
COVER_BG = QColor("#22304f")

FONT_FAMILY = "Segoe UI"
COVER_SIZE = 150
SIDE_MARGIN = 70


def _top(counts, n):
    items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower()))
    return items[:n]


def _font(pixel_size, weight=QFont.Weight.Normal):
    font = QFont(FONT_FAMILY)
    font.setPixelSize(pixel_size)
    font.setWeight(weight)
    return font


def _cover_pixmap(path):
    data = extract_cover(path)
    if not data:
        return None
    pm = QPixmap()
    if pm.loadFromData(data):
        return pm.scaled(
            COVER_SIZE,
            COVER_SIZE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    return None


def _best_path_for_artist(artist, play_counts):
    best = None
    best_count = -1
    for path, count in play_counts.items():
        from core.stats import _artist_of

        if _artist_of(path) == artist and count > best_count:
            best, best_count = path, count
    return best


def _draw_cover(painter, x, y, pixmap, rank):
    rect = QRectF(x, y, COVER_SIZE, COVER_SIZE)
    painter.save()
    painter.setBrush(COVER_BG if pixmap is None else Qt.BrushStyle.NoBrush)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(rect, 22, 22)
    if pixmap is not None:
        clip = QPainterPath()
        clip.addRoundedRect(rect, 22, 22)
        painter.setClipPath(clip)
        scaled = pixmap.scaled(
            int(rect.width()),
            int(rect.height()),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        offset_x = int(rect.x() + (rect.width() - scaled.width()) / 2)
        offset_y = int(rect.y() + (rect.height() - scaled.height()) / 2)
        painter.drawPixmap(offset_x, offset_y, scaled)
    else:
        painter.setPen(QColor("#5c90ff"))
        painter.setFont(_font(64, QFont.Weight.Bold))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(rank))
    painter.restore()


def _draw_rounded_card(painter, rect, radius=26):
    painter.save()
    painter.setBrush(CARD_BG)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(rect, radius, radius)
    painter.restore()


def _draw_elided(painter, rect, text, font, color):
    painter.save()
    painter.setPen(color)
    painter.setFont(font)
    fm = QFontMetrics(font)
    elided = fm.elidedText(text, Qt.TextElideMode.ElideRight, int(rect.width()))
    painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided)
    painter.restore()


def render_summary_card(profile_name, period_label, summary):
    pixmap = QPixmap(CARD_W, CARD_H)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

    gradient = QLinearGradient(0, 0, 0, CARD_H)
    gradient.setColorAt(0.0, BG_TOP)
    gradient.setColorAt(1.0, BG_BOTTOM)
    painter.fillRect(0, 0, CARD_W, CARD_H, gradient)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(ACCENT)
    painter.drawRect(0, 0, CARD_W, 14)
    painter.setBrush(QColor(ACCENT_LIGHT))
    painter.drawEllipse(CARD_W - 220, 140, 260, 260)
    painter.setBrush(QColor("#1a2745"))
    painter.drawEllipse(-120, CARD_H - 320, 340, 340)

    x = SIDE_MARGIN
    width = CARD_W - 2 * SIDE_MARGIN

    _draw_elided(painter, QRectF(x, 110, width, 52), profile_name.upper(),
                 _font(38, QFont.Weight.DemiBold), MUTED)

    title_font = _font(78, QFont.Weight.Bold)
    _draw_elided(painter, QRectF(x, 170, width, 96), period_label, title_font, WHITE)

    time_card = QRectF(x, 340, width, 260)
    _draw_rounded_card(painter, time_card)
    _draw_elided(painter, QRectF(x + 40, 368, width - 80, 48), "CZAS SŁUCHANIA",
                 _font(28, QFont.Weight.DemiBold), MUTED)
    _draw_elided(painter, QRectF(x + 40, 420, width - 80, 120),
                 format_listening(summary.get("listening_seconds", 0)),
                 _font(88, QFont.Weight.Bold), WHITE)

    total_plays = sum((summary.get("play_counts") or {}).values())
    _draw_elided(painter, QRectF(x + 40, 548, width - 80, 44),
                 f"Liczba odsłuchań: {total_plays}",
                 _font(32, QFont.Weight.DemiBold), ACCENT_LIGHT)

    y = 610
    _draw_elided(painter, QRectF(x, y, width, 52), "TOP UTWORY",
                 _font(38, QFont.Weight.Bold), WHITE)
    y += 76

    play_counts = summary.get("play_counts") or {}
    for i, (path, count) in enumerate(_top(play_counts, 3), start=1):
        row = QRectF(x, y, width, COVER_SIZE)
        _draw_rounded_card(painter, row)
        cover = _cover_pixmap(path)
        _draw_cover(painter, x + 22, y + 14, cover, i)
        name = display_name(path, os.path.splitext(os.path.basename(path))[0])
        _draw_elided(painter, QRectF(x + 200, y + 22, width - 280, 56),
                     name, _font(32, QFont.Weight.DemiBold), WHITE)
        _draw_elided(painter, QRectF(x + 200, y + 86, width - 280, 40),
                     f"{count} odsłuchań", _font(26), MUTED)
        y += COVER_SIZE + 26

    y += 24
    _draw_elided(painter, QRectF(x, y, width, 52), "TOP WYKONAWCY",
                 _font(38, QFont.Weight.Bold), WHITE)
    y += 76

    artist_counts = summary.get("artist_counts") or {}
    for i, (artist, count) in enumerate(_top(artist_counts, 3), start=1):
        row = QRectF(x, y, width, COVER_SIZE)
        _draw_rounded_card(painter, row)
        example_path = _best_path_for_artist(artist, play_counts)
        cover = _cover_pixmap(example_path) if example_path else None
        _draw_cover(painter, x + 22, y + 14, cover, i)
        _draw_elided(painter, QRectF(x + 200, y + 22, width - 280, 56),
                     artist, _font(32, QFont.Weight.DemiBold), WHITE)
        _draw_elided(painter, QRectF(x + 200, y + 86, width - 280, 40),
                     f"{count} odsłuchań", _font(26), MUTED)
        y += COVER_SIZE + 26

    painter.setPen(MUTED)
    painter.setFont(_font(26))
    painter.drawText(QRectF(0, CARD_H - 70, CARD_W, 44),
                     Qt.AlignmentFlag.AlignCenter, "MusicBox by Szymon Mazur")

    painter.end()
    return pixmap


def save_summary_card(profile_name, period_label, summary, path):
    pixmap = render_summary_card(profile_name, period_label, summary)
    try:
        return pixmap.save(path, "PNG")
    except Exception:
        return False
