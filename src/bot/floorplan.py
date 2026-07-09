"""Схема зала казино (одинаковая для всех) с подсветкой выбранного стола.

Планировка взята со скетча: слева вверху — стол 1, слева внизу — вход,
сверху — стол 2 (у входа в основной зал), в основном зале столы 3–6.
"""

from __future__ import annotations

import io
import os

from PIL import Image, ImageDraw, ImageFont

# Шрифт с кириллицей. Встроенный load_default() глифов кириллицы не имеет
# (рисует квадратики), поэтому ищем системный TTF. На сервере (Ubuntu) —
# fonts-dejavu-core: apt-get install -y fonts-dejavu-core.
_FONT_CANDIDATES = [
    os.environ.get("FLOORPLAN_FONT", ""),
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]
_FONT_PATH = next((p for p in _FONT_CANDIDATES if p and os.path.exists(p)), None)

W, H = 900, 680
BG = (255, 255, 255)
WALL = (214, 69, 65)          # красные стены (как на скетче)
TABLE_FILL = (232, 234, 237)
TABLE_BORDER = (60, 63, 68)
HILITE_FILL = (52, 168, 83)   # подсвеченный стол
HILITE_TEXT = (255, 255, 255)
TEXT = (33, 37, 41)

# комнаты: (x0, y0, x1, y1)
ROOMS = [
    (430, 90, 690, 250),   # верхняя комната (стол 2)
    (90, 250, 360, 430),   # левая верхняя (стол 1)
    (90, 430, 360, 590),   # вход
    (360, 250, 820, 640),  # основной зал
]

# столы: номер -> центр (cx, cy)
TABLE_POS = {
    2: (560, 170),
    1: (225, 340),
    3: (500, 370),
    4: (690, 370),
    5: (500, 545),
    6: (690, 545),
}
TW, TH = 130, 66


def _font(size: int):
    if _FONT_PATH:
        return ImageFont.truetype(_FONT_PATH, size)
    try:
        return ImageFont.load_default(size=size)  # Pillow >= 10.1 (без кириллицы)
    except TypeError:  # pragma: no cover
        return ImageFont.load_default()


def _text_center(draw: ImageDraw.ImageDraw, cx: float, cy: float, s: str, font, fill) -> None:
    left, top, right, bottom = draw.textbbox((0, 0), s, font=font)
    draw.text((cx - (right - left) / 2, cy - (bottom - top) / 2), s, font=font, fill=fill)


def render_floorplan(highlight: int | None = None) -> bytes:
    """PNG-байты схемы зала; если задан highlight (1–6) — стол подсвечен."""
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    _text_center(d, W / 2, 45, "Схема зала казино", _font(30), TEXT)

    for room in ROOMS:
        d.rectangle(room, outline=WALL, width=5)

    _text_center(d, 225, 510, "Вход", _font(34), TEXT)

    fnum = _font(30)
    for num, (cx, cy) in TABLE_POS.items():
        box = (cx - TW / 2, cy - TH / 2, cx + TW / 2, cy + TH / 2)
        if num == highlight:
            d.rounded_rectangle(box, radius=12, fill=HILITE_FILL, outline=HILITE_FILL, width=3)
            _text_center(d, cx, cy, str(num), fnum, HILITE_TEXT)
        else:
            d.rounded_rectangle(box, radius=12, fill=TABLE_FILL, outline=TABLE_BORDER, width=3)
            _text_center(d, cx, cy, str(num), fnum, TEXT)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
