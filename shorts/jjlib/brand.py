"""Brand constants and overlay rendering.

Overlays are drawn with Pillow rather than ffmpeg's drawtext because we need
real typography: the brand fonts, wrapped multi-line titles, rounded bands and
alpha. ffmpeg then just composites the finished PNG over the video.
"""
from __future__ import annotations

import textwrap
import zlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_DIR = Path(__file__).resolve().parent.parent / "fonts"

# JJ Brand Guidelines palette.
PINK = "#FAB3F8"
MAGENTA = "#CD3A8E"
LILAC = "#B8A9E0"
PURPLE = "#4E217A"
NAVY = "#275B87"
YELLOW = "#FDDD0F"
BLUE = "#8FC4F7"
INK = "#2B1141"

# Accent colours, spread across the catalogue so the channel grid does not
# read as one flat colour. Deep enough that white type stays legible on them.
ACCENTS = [MAGENTA, PURPLE, NAVY]

WIDTH, HEIGHT = 1080, 1920

# YouTube's own UI (channel name, description, action buttons) sits over the
# bottom of a Short and the right-hand rail. Keep anything that must stay
# readable inside these margins.
SAFE_TOP = 220
SAFE_BOTTOM = 520
SAFE_SIDE = 72


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / f"{name}.ttf"), size)


def _hex(value: str, alpha: int = 255) -> tuple[int, int, int, int]:
    value = value.lstrip("#")
    r, g, b = (int(value[i : i + 2], 16) for i in (0, 2, 4))
    return (r, g, b, alpha)


def accent_for(handle: str) -> str:
    """Pick an accent from the handle, not from position in the build queue.

    Keyed on the handle so `build --only <handle> --force` reproduces exactly
    the colour the first full run gave it. zlib.crc32 is used rather than
    hash() because hash() is randomised per process.
    """
    return ACCENTS[zlib.crc32(handle.encode()) % len(ACCENTS)]


def _fit_lines(
    text: str, fnt_name: str, max_size: int, max_width: int, max_lines: int
) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    """Shrink the point size until the title wraps into at most `max_lines`."""
    for size in range(max_size, 28, -4):
        fnt = font(fnt_name, size)
        # Estimate characters per line from the average glyph width, then let
        # textwrap do the word-boundary work.
        avg = max(fnt.getlength("abcdefghijklmnopqrstuvwxyz") / 26, 1)
        lines = textwrap.wrap(text, width=max(int(max_width / avg), 8)) or [text]
        if len(lines) <= max_lines and all(fnt.getlength(l) <= max_width for l in lines):
            return fnt, lines
    fnt = font(fnt_name, 32)
    return fnt, textwrap.wrap(text, width=30)[:max_lines] or [text]


def _rounded_band(
    draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], colour: str, alpha: int = 235
) -> None:
    draw.rounded_rectangle(box, radius=28, fill=_hex(colour, alpha))


def title_overlay(title: str, accent: str, caption: str | None = None) -> Image.Image:
    """Persistent overlay: title band at the top, store tag at the bottom.

    Kept on screen for the whole Short. A viewer who lands mid-scroll still
    learns what the book is called, which is most of the job of a Short.
    """
    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    max_text_width = WIDTH - 2 * SAFE_SIDE - 80
    fnt, lines = _fit_lines(title.upper(), "librefranklin-900", 92, max_text_width, 3)
    line_h = int(fnt.size * 1.12)
    text_h = line_h * len(lines)

    band_top = SAFE_TOP - 40
    band_bottom = band_top + text_h + 72
    _rounded_band(draw, (SAFE_SIDE, band_top, WIDTH - SAFE_SIDE, band_bottom), accent)

    y = band_top + 36
    for line in lines:
        w = draw.textlength(line, font=fnt)
        draw.text(((WIDTH - w) / 2, y), line, font=fnt, fill=_hex("#FFFFFF"))
        y += line_h

    if caption:
        cap_fnt = font("montserrat-700", 40)
        cap_w = draw.textlength(caption, font=cap_fnt)
        cap_y = band_bottom + 22
        _rounded_band(
            draw,
            (int((WIDTH - cap_w) / 2) - 28, cap_y, int((WIDTH + cap_w) / 2) + 28, cap_y + 68),
            YELLOW,
            245,
        )
        draw.text(((WIDTH - cap_w) / 2, cap_y + 12), caption, font=cap_fnt, fill=_hex(INK))

    # Bottom tag sits just above YouTube's own chrome.
    tag = "jenjenivive.com"
    tag_fnt = font("montserrat-700", 38)
    tag_w = draw.textlength(tag, font=tag_fnt)
    tag_y = HEIGHT - SAFE_BOTTOM
    _rounded_band(
        draw,
        (int((WIDTH - tag_w) / 2) - 32, tag_y, int((WIDTH + tag_w) / 2) + 32, tag_y + 66),
        PURPLE,
        225,
    )
    draw.text(((WIDTH - tag_w) / 2, tag_y + 12), tag, font=tag_fnt, fill=_hex("#FFFFFF"))

    return img


def end_card(title: str, price: str | None, accent: str, cover: Path | None) -> Image.Image:
    """Full-frame closing card: cover, title, price, call to action."""
    img = Image.new("RGBA", (WIDTH, HEIGHT), _hex(accent))
    draw = ImageDraw.Draw(img)

    if cover and cover.exists():
        art = Image.open(cover).convert("RGBA")
        side = 720
        art.thumbnail((side, side), Image.LANCZOS)
        shadow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        sx, sy = (WIDTH - art.width) // 2, 430
        shadow.paste(_hex(INK, 90), (sx + 16, sy + 20, sx + art.width + 16, sy + art.height + 20))
        img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(22)))
        img.alpha_composite(art, (sx, sy))

    head_fnt = font("borel-400", 86)
    head = "Out now"
    hw = draw.textlength(head, font=head_fnt)
    draw.text(((WIDTH - hw) / 2, 250), head, font=head_fnt, fill=_hex(YELLOW))

    fnt, lines = _fit_lines(title.upper(), "librefranklin-900", 78, WIDTH - 2 * SAFE_SIDE, 3)
    y = 1230
    for line in lines:
        w = draw.textlength(line, font=fnt)
        draw.text(((WIDTH - w) / 2, y), line, font=fnt, fill=_hex("#FFFFFF"))
        y += int(fnt.size * 1.1)

    if price:
        price_fnt = font("montserrat-700", 52)
        ptxt = f"£{price}"
        pw = draw.textlength(ptxt, font=price_fnt)
        draw.text(((WIDTH - pw) / 2, y + 18), ptxt, font=price_fnt, fill=_hex(PINK))
        y += 88

    cta_fnt = font("montserrat-700", 46)
    cta = "jenjenivive.com"
    cw = draw.textlength(cta, font=cta_fnt)
    cy = y + 40
    _rounded_band(
        draw, (int((WIDTH - cw) / 2) - 40, cy, int((WIDTH + cw) / 2) + 40, cy + 84), YELLOW, 255
    )
    draw.text(((WIDTH - cw) / 2, cy + 16), cta, font=cta_fnt, fill=_hex(INK))

    return img


def thumbnail(title: str, accent: str, cover: Path | None) -> Image.Image:
    """1280x720 thumbnail. Shorts autogenerate one, but a custom image is used
    anywhere the video shows up as a normal watch-page entry."""
    img = Image.new("RGB", (1280, 720), tuple(_hex(accent)[:3]))
    draw = ImageDraw.Draw(img)

    if cover and cover.exists():
        art = Image.open(cover).convert("RGBA")
        art.thumbnail((560, 560), Image.LANCZOS)
        img.paste(art, (1280 - art.width - 70, (720 - art.height) // 2), art)

    fnt, lines = _fit_lines(title.upper(), "librefranklin-900", 82, 560, 4)
    y = (720 - int(fnt.size * 1.12) * len(lines)) // 2
    for line in lines:
        draw.text((70, y), line, font=fnt, fill=tuple(_hex("#FFFFFF")[:3]))
        y += int(fnt.size * 1.12)

    return img
