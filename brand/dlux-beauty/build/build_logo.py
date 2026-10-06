#!/usr/bin/env python3
"""
D'LUX — Beauty by Samantha : vector logo generator.

Shapes real type with HarfBuzz (kerning / ligatures / contextual alternates),
bakes every glyph outline into absolute SVG path data (no font dependency),
draws the ring, the hairline-and-heart divider and the sparkles, then writes
every colour variant and lockup as a self-contained SVG.

Usage:  python3 build_logo.py [fonts_dir] [out_dir]
"""
import math
import os
import sys

import uharfbuzz as hb
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.boundsPen import BoundsPen

FONTS_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
OUT_DIR = sys.argv[2] if len(sys.argv) > 2 else "out"
os.makedirs(OUT_DIR, exist_ok=True)


def fmt(v):
    s = f"{v:.2f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


# --------------------------------------------------------------------------
# Fonts
# --------------------------------------------------------------------------
class Face:
    """A font loaded twice: HarfBuzz for shaping, fontTools for outlines."""

    def __init__(self, path, variations=None):
        self.path = path
        blob = hb.Blob.from_file_path(path)
        self.hbfont = hb.Font(hb.Face(blob))
        if variations:
            self.hbfont.set_variations(variations)
        tt = TTFont(path)
        if "fvar" in tt and variations:
            tt = instancer.instantiateVariableFont(tt, variations)
        try:  # Cinzel builds glyphs from overlapping contours; union them
            from fontTools.ttLib.removeOverlaps import removeOverlaps
            removeOverlaps(tt)
        except Exception as e:  # pragma: no cover
            print("removeOverlaps skipped:", e)
        self.tt = tt
        self.upm = tt["head"].unitsPerEm
        self.glyph_order = tt.getGlyphOrder()
        self.glyph_set = tt.getGlyphSet()

    def shape(self, text, features=None):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        feats = {"kern": True, "liga": True, "calt": True, "clig": True}
        if features:
            feats.update(features)
        hb.shape(self.hbfont, buf, feats)
        return list(zip(buf.glyph_infos, buf.glyph_positions))

    def text_paths(self, text, size, x, y, anchor="middle", tracking=0.0,
                   features=None):
        """Return (list_of_path_d, bbox) for `text` at font `size` px with
        the baseline at `y`.  `anchor` is start|middle|end, `tracking` is
        extra letter spacing in px."""
        scale = size / self.upm
        run = self.shape(text, features)
        # total advance (px), including tracking between glyphs
        adv_total = sum(p.x_advance for _, p in run) * scale
        adv_total += tracking * (len(run) - 1)
        if anchor == "middle":
            pen_x = x - adv_total / 2
        elif anchor == "end":
            pen_x = x - adv_total
        else:
            pen_x = x
        paths = []
        bounds = [math.inf, math.inf, -math.inf, -math.inf]
        for i, (info, pos) in enumerate(run):
            gname = self.glyph_order[info.codepoint]
            glyph = self.glyph_set[gname]
            gx = pen_x + pos.x_offset * scale
            gy = y - pos.y_offset * scale
            spen = SVGPathPen(self.glyph_set, ntos=fmt)
            tpen = TransformPen(spen, (scale, 0, 0, -scale, gx, gy))
            glyph.draw(tpen)
            d = spen.getCommands()
            if d:
                paths.append(d)
                bp = BoundsPen(self.glyph_set)
                glyph.draw(TransformPen(bp, (scale, 0, 0, -scale, gx, gy)))
                if bp.bounds:
                    x0, y0, x1, y1 = bp.bounds
                    bounds = [min(bounds[0], x0), min(bounds[1], y0),
                              max(bounds[2], x1), max(bounds[3], y1)]
            pen_x += pos.x_advance * scale + tracking
        return paths, bounds


def F(name):
    return os.path.join(FONTS_DIR, name)


CINZEL = Face(F("Cinzel.ttf"), {"wght": 700})
SCRIPT = Face(F("GreatVibes-Regular.ttf"))


# --------------------------------------------------------------------------
# Geometry helpers
# --------------------------------------------------------------------------
def bar(x0, x1, y, t=2.4):
    """Horizontal hairline as a rounded filled bar (gradient-safe)."""
    r = t / 2
    return (f"M{fmt(x0 + r)} {fmt(y - r)} H{fmt(x1 - r)} A{fmt(r)} {fmt(r)} 0 0 1 {fmt(x1 - r)} {fmt(y + r)} "
            f"H{fmt(x0 + r)} A{fmt(r)} {fmt(r)} 0 0 1 {fmt(x0 + r)} {fmt(y - r)} Z")


def vbar(x, y0, y1, t=2.8):
    r = t / 2
    return (f"M{fmt(x + r)} {fmt(y0 + r)} V{fmt(y1 - r)} A{fmt(r)} {fmt(r)} 0 0 1 {fmt(x - r)} {fmt(y1 - r)} "
            f"V{fmt(y0 + r)} A{fmt(r)} {fmt(r)} 0 0 1 {fmt(x + r)} {fmt(y0 + r)} Z")


def ring_arc(r, gap_deg):
    """Circle of radius r around (CX,CY) with a gap of gap_deg centred at 12 o'clock."""
    a0 = math.radians(-90 + gap_deg / 2)
    a1 = math.radians(-90 - gap_deg / 2 + 360)
    x0, y0 = CX + r * math.cos(a0), CY + r * math.sin(a0)
    x1, y1 = CX + r * math.cos(a1), CY + r * math.sin(a1)
    return f"M{fmt(x0)} {fmt(y0)} A{r} {r} 0 1 1 {fmt(x1)} {fmt(y1)}"


def heart_path(cx, cy, s):
    """Classic heart, `s` ~ half-width."""
    return (f"M{fmt(cx)} {fmt(cy + s * 0.95)} "
            f"C{fmt(cx - s * 0.1)} {fmt(cy + s * 0.75)} {fmt(cx - s)} {fmt(cy + s * 0.25)} {fmt(cx - s)} {fmt(cy - s * 0.25)} "
            f"C{fmt(cx - s)} {fmt(cy - s * 0.8)} {fmt(cx - s * 0.3)} {fmt(cy - s * 0.95)} {fmt(cx)} {fmt(cy - s * 0.35)} "
            f"C{fmt(cx + s * 0.3)} {fmt(cy - s * 0.95)} {fmt(cx + s)} {fmt(cy - s * 0.8)} {fmt(cx + s)} {fmt(cy - s * 0.25)} "
            f"C{fmt(cx + s)} {fmt(cy + s * 0.25)} {fmt(cx + s * 0.1)} {fmt(cy + s * 0.75)} {fmt(cx)} {fmt(cy + s * 0.95)} Z")


def sparkle_path(cx, cy, r, inner=0.22):
    """Four-point star."""
    pts = []
    for i in range(8):
        a = -math.pi / 2 + i * math.pi / 4
        rr = r if i % 2 == 0 else r * inner
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    # smooth the long points with quadratic curves through the inner points
    d = f"M{fmt(pts[0][0])} {fmt(pts[0][1])}"
    for i in range(1, 8, 2):
        q = pts[i]
        p = pts[(i + 1) % 8]
        d += f" Q{fmt(q[0])} {fmt(q[1])} {fmt(p[0])} {fmt(p[1])}"
    return d + " Z"


# --------------------------------------------------------------------------
# Artwork (all coordinates in a 1000 x 1000 box, centre 500,500)
# --------------------------------------------------------------------------
CX, CY = 500, 500


def build_badge():
    """All element groups for the round badge (1000 x 1000)."""
    el = {}
    # Wordmark — the hero, sits just above centre
    el["word"], wb = CINZEL.text_paths("D\u2019LUX", 230, CX, 480, anchor="middle", tracking=10)
    el["word_bounds"] = wb
    # Divider: two hairlines with a heart between (the bit Samantha liked)
    dy = 543
    el["divider_y"] = dy
    el["divider_lines"] = [bar(CX - 268, CX - 32, dy), bar(CX + 32, CX + 268, dy)]
    el["heart"] = heart_path(CX, dy, 13)
    # Script line
    el["script"], sb = SCRIPT.text_paths("Beauty by Samantha", 104, CX, 652, anchor="middle")
    el["script_bounds"] = sb
    # Sparkles — three, restrained, framing the top of the wordmark
    el["sparkles"] = [sparkle_path(236, 296, 11), sparkle_path(744, 254, 8),
                      sparkle_path(782, 306, 4.5)]
    # Tiny heart that breaks the inner hairline ring at the top
    el["ring_heart"] = heart_path(CX, CY - 444, 7)
    return el


# --------------------------------------------------------------------------
# Rendering to SVG
# --------------------------------------------------------------------------
GOLD_DEFS = """
  <linearGradient id="gold" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0"    stop-color="#FFF6CF"/>
    <stop offset="0.18" stop-color="#F0D27A"/>
    <stop offset="0.38" stop-color="#C9A032"/>
    <stop offset="0.52" stop-color="#FBEBA9"/>
    <stop offset="0.68" stop-color="#D2AA3E"/>
    <stop offset="0.86" stop-color="#9B7418"/>
    <stop offset="1"    stop-color="#C79C2E"/>
  </linearGradient>
  <linearGradient id="goldRing" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0"    stop-color="#FFF8DA"/>
    <stop offset="0.22" stop-color="#E7C462"/>
    <stop offset="0.42" stop-color="#A87F1E"/>
    <stop offset="0.56" stop-color="#F7E39F"/>
    <stop offset="0.74" stop-color="#C69B2B"/>
    <stop offset="1"    stop-color="#8F6A14"/>
  </linearGradient>
  <linearGradient id="goldDeep" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0"   stop-color="#A67C1C"/>
    <stop offset="0.5" stop-color="#7A5A10"/>
    <stop offset="1"   stop-color="#5E450C"/>
  </linearGradient>
  <linearGradient id="goldScript" x1="0" y1="0" x2="1" y2="0.3">
    <stop offset="0"    stop-color="#B8891F"/>
    <stop offset="0.35" stop-color="#F3DC8E"/>
    <stop offset="0.6"  stop-color="#C79E2D"/>
    <stop offset="1"    stop-color="#8F6A14"/>
  </linearGradient>
  <radialGradient id="cream" cx="0.5" cy="0.42" r="0.6">
    <stop offset="0"   stop-color="#FFFCF4"/>
    <stop offset="0.7" stop-color="#F7EFDF"/>
    <stop offset="1"   stop-color="#EFE3CB"/>
  </radialGradient>
  <radialGradient id="noir" cx="0.5" cy="0.42" r="0.65">
    <stop offset="0"   stop-color="#2A2622"/>
    <stop offset="0.75" stop-color="#15130F"/>
    <stop offset="1"   stop-color="#0B0A08"/>
  </radialGradient>
"""


class Palette:
    def __init__(self, name, bg_fill, letter_fill, ring_fill, deep_fill,
                 script_fill, knock, bevel=True, shadow=None, flat=False):
        self.name = name
        self.bg_fill = bg_fill        # None = transparent, else fill for disc
        self.letter_fill = letter_fill
        self.ring_fill = ring_fill
        self.deep_fill = deep_fill    # under-layer / outline colour
        self.script_fill = script_fill
        self.knock = knock            # background colour for interlock gaps
        self.bevel = bevel
        self.shadow = shadow
        self.flat = flat


PALETTES = {
    # Full metallic gold on cream disc — the primary mark
    "primary": Palette("primary", "url(#cream)", "url(#gold)", "url(#goldRing)",
                       "url(#goldDeep)", "url(#goldScript)", "#F8F1E2"),
    # Same artwork, no disc — drops onto any pale surface
    "transparent": Palette("transparent", None, "url(#gold)", "url(#goldRing)",
                           "url(#goldDeep)", "url(#goldScript)", None),
    # Gold on near-black — for dark placemats, menus, packaging
    "dark": Palette("dark", "url(#noir)", "url(#gold)", "url(#goldRing)",
                    "url(#goldDeep)", "url(#goldScript)", "#15130F"),
    # Single-colour flat gold (Pantone 871 C / foil / spot print)
    "gold-flat": Palette("gold-flat", None, "#C9A227", "#C9A227", "#C9A227",
                         "#C9A227", None, bevel=False, flat=True),
    # Single-colour black (stamps, laser etch, newspaper, embroidery)
    "black": Palette("black", None, "#111111", "#111111", "#111111",
                     "#111111", None, bevel=False, flat=True),
    # Single-colour white reverse (dark backgrounds, vinyl, glass)
    "white": Palette("white", None, "#FFFFFF", "#FFFFFF", "#FFFFFF",
                     "#FFFFFF", None, bevel=False, flat=True),
}


def metallic_group(paths, pal, bevel_dx=0, bevel_dy=0, outline=1.2):
    """Letter rendering: deep-gold under-layer offset for depth + thin
    outline so the mark holds together at small sizes, then the gradient."""
    out = []
    if pal.bevel and (bevel_dx or bevel_dy):
        out.append(f'<g transform="translate({bevel_dx} {bevel_dy})" fill="{pal.deep_fill}">'
                   + "".join(f'<path d="{d}"/>' for d in paths) + "</g>")
    stroke = "" if pal.flat else f' stroke="{pal.deep_fill}" stroke-width="{outline}" stroke-linejoin="round"'
    out.append(f'<g fill="{pal.letter_fill}"{stroke}>' + "".join(f'<path d="{d}"/>' for d in paths) + "</g>")
    return "".join(out)


def badge_svg(el, pal, size=1000):
    """Round badge, 1000 x 1000 viewBox."""
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1000" width="{size}" height="{size}">',
         f'<title>D’LUX — Beauty by Samantha</title>',
         "<defs>", GOLD_DEFS, "</defs>"]
    # Disc
    if pal.bg_fill:
        o.append(f'<circle cx="{CX}" cy="{CY}" r="478" fill="{pal.bg_fill}"/>')
    # Frame: broad ring + hairline inner ring
    if pal.flat:
        o.append(f'<circle cx="{CX}" cy="{CY}" r="466" fill="none" stroke="{pal.ring_fill}" stroke-width="16"/>')
        o.append(f'<path d="{ring_arc(444, 12)}" fill="none" stroke="{pal.ring_fill}" stroke-width="2.5" stroke-linecap="round"/>')
    else:
        # dark edge under the ring gives the metal some thickness
        o.append(f'<circle cx="{CX}" cy="{CY}" r="466" fill="none" stroke="{pal.deep_fill}" stroke-width="20"/>')
        o.append(f'<circle cx="{CX}" cy="{CY}" r="466" fill="none" stroke="{pal.ring_fill}" stroke-width="15"/>')
        o.append(f'<circle cx="{CX}" cy="{CY}" r="466" fill="none" stroke="#FFF9E0" stroke-width="1.2" opacity="0.55"/>')
        o.append(f'<path d="{ring_arc(444, 12)}" fill="none" stroke="{pal.ring_fill}" stroke-width="2.5" stroke-linecap="round"/>')
        o.append(f'<path d="{ring_arc(444, 12)}" fill="none" stroke="{pal.deep_fill}" stroke-width="0.6" opacity="0.6" stroke-linecap="round"/>')
    # Wordmark
    o.append(metallic_group(el["word"], pal, 2.5, 3.2, outline=1.2))
    # Divider + heart
    o.append(metallic_group(el["divider_lines"], pal, 0.8, 1.0, outline=0.5))
    o.append(metallic_group([el["heart"]], pal, 1, 1.5, outline=0.9))
    # Script
    o.append(f'<g fill="{pal.script_fill}">' + "".join(f'<path d="{d}"/>' for d in el["script"]) + "</g>")
    # Ring heart
    o.append(metallic_group([el["ring_heart"]], pal, 0.6, 0.8, outline=0.6))
    # Sparkles
    o.append(f'<g fill="{pal.script_fill}">' + "".join(f'<path d="{d}"/>' for d in el["sparkles"]) + "</g>")
    o.append("</svg>")
    return "\n".join(o)


def stacked_svg(pal, w=1000, h=520):
    """Stacked wordmark without the ring — for rectangular spaces."""
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 520" width="{w}" height="{h}">',
         f'<title>D\u2019LUX \u2014 Beauty by Samantha (stacked)</title>', "<defs>", GOLD_DEFS, "</defs>"]
    if pal.name == "dark":
        o.append('<rect width="1000" height="520" fill="#15130F"/>')
    elif pal.name == "primary":
        o.append('<rect width="1000" height="520" fill="#F8F1E2"/>')
    word, wb = CINZEL.text_paths("D\u2019LUX", 250, 500, 210, anchor="middle", tracking=12)
    o.append(metallic_group(word, pal, 3, 4, outline=1.5))
    dy = 280
    o.append(metallic_group([bar(wb[0] + 6, 500 - 34, dy, 2.6), bar(500 + 34, wb[2] - 6, dy, 2.6)], pal, 0.8, 1.0, outline=0.5))
    o.append(metallic_group([heart_path(500, dy, 14)], pal, 1, 1.5, outline=0.9))
    script, sb = SCRIPT.text_paths("Beauty by Samantha", 118, 500, 405, anchor="middle")
    o.append(f'<g fill="{pal.script_fill}">' + "".join(f'<path d="{d}"/>' for d in script) + "</g>")
    o.append("</svg>")
    return "\n".join(o)


def horizontal_svg(pal, h=420):
    """One-line lockup: D\u2019LUX  \u2665  Beauty by Samantha — placemat edges, banners.
    The canvas width is fitted to the content."""
    base = 290
    pad = 90
    word, wb = CINZEL.text_paths("D\u2019LUX", 300, pad, base, anchor="start", tracking=14)
    hx = wb[2] + 120
    script, sb = SCRIPT.text_paths("Beauty by Samantha", 190, hx + 110, base - 2, anchor="start")
    W = int(round(sb[2] + pad))
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {h}" width="{W}" height="{h}">',
         f'<title>D\u2019LUX \u2014 Beauty by Samantha (horizontal)</title>', "<defs>", GOLD_DEFS, "</defs>"]
    if pal.name == "dark":
        o.append(f'<rect width="{W}" height="{h}" fill="#15130F"/>')
    elif pal.name == "primary":
        o.append(f'<rect width="{W}" height="{h}" fill="#F8F1E2"/>')
    o.append(metallic_group(word, pal, 3, 4, outline=1.6))
    o.append(metallic_group([vbar(hx, base - 208, base - 134), vbar(hx, base - 66, base + 8)], pal, 0.8, 1.0, outline=0.5))
    o.append(metallic_group([heart_path(hx, base - 100, 17)], pal, 1, 1.5, outline=1.0))
    o.append(f'<g fill="{pal.script_fill}">' + "".join(f'<path d="{d}"/>' for d in script) + "</g>")
    o.append("</svg>")
    return "\n".join(o)


def main():
    el = build_badge()
    print("wordmark bounds", [round(v) for v in el["word_bounds"]],
          "width", round(el["word_bounds"][2] - el["word_bounds"][0]))
    print("script bounds", [round(v) for v in el["script_bounds"]],
          "width", round(el["script_bounds"][2] - el["script_bounds"][0]))
    written = []
    for key, pal in PALETTES.items():
        for kind, svg in (("logo", badge_svg(el, pal)), ("stacked", stacked_svg(pal)),
                          ("horizontal", horizontal_svg(pal))):
            p = os.path.join(OUT_DIR, f"dlux-{kind}-{key}.svg")
            with open(p, "w") as f:
                f.write(svg)
            written.append(p)
    for p in written:
        print("wrote", p, os.path.getsize(p), "bytes")


if __name__ == "__main__":
    main()
