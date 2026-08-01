#!/usr/bin/env python3
"""Build dist/jenjenivive.html — a fully self-contained single-file version of the site.

Inlines CSS, JS, fonts (base64 woff2) and every referenced image (base64 webp/png).
Featured covers (hero, best sellers, personalised, club) stay at full 640px;
library/merch covers are downscaled to 384px to keep the file lean.
"""
import base64, json, os, re, sys
from io import BytesIO

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def read(p):
    with open(os.path.join(ROOT, p), encoding="utf8") as f:
        return f.read()

def b64(data, mime):
    return "data:" + mime + ";base64," + base64.b64encode(data).decode()

def file_b64(p, mime):
    with open(os.path.join(ROOT, p), "rb") as f:
        return b64(f.read(), mime)

html = read("index.html")
css = read("css/style.css")
main_js = read("js/main.js")
data_js = read("js/books-data.js")
data = json.loads(data_js.split("=", 1)[1].strip().rstrip(";"))

# ---- fonts into css ----
def font_repl(m):
    return "url(" + file_b64("assets/fonts/" + m.group(1), "font/woff2") + ") format('woff2')"
css = re.sub(r"url\('\.\./assets/fonts/([\w.-]+\.woff2)'\) format\('woff2'\)", font_repl, css)

# ---- covers map ----
featured = set(data["best"]) | set(m["h"] for m in data["custom"]) | {data["club"]["h"]}
covers = {}
for m in data["books"] + data["custom"] + data["merch"] + data["bundles"] + [data["club"]]:
    h = m["h"]
    if h in covers:
        continue
    path = os.path.join(ROOT, "assets", "covers", h + ".webp")
    if h in featured:
        with open(path, "rb") as f:
            covers[h] = b64(f.read(), "image/webp")
    else:
        im = Image.open(path)
        if im.width > 384:
            im = im.resize((384, round(im.height * 384 / im.width)), Image.LANCZOS)
        buf = BytesIO()
        im.save(buf, "WEBP", quality=78)
        covers[h] = b64(buf.getvalue(), "image/webp")

img_js = "window.JJ_IMG = " + json.dumps(covers) + ";\n"

# ---- brand images in html ----
# favicon: use the small webp instead of the 440KB png
html = html.replace('href="assets/brand/roundel.png" type="image/png"',
                    'href="' + file_b64("assets/brand/roundel-sm.webp", "image/webp") + '" type="image/webp"')
for brand in ["roundel-sm.webp", "roundel.webp", "wordmark.webp"]:
    html = html.replace("assets/brand/" + brand, file_b64("assets/brand/" + brand, "image/webp"))

# ---- stitch ----
html = html.replace('<link rel="stylesheet" href="css/style.css">',
                    "<style>\n" + css + "\n</style>")
html = html.replace('<script src="js/books-data.js"></script>',
                    "<script>\n" + data_js + img_js + "</script>")
html = html.replace('<script src="js/main.js"></script>',
                    "<script>\n" + main_js + "\n</script>")

os.makedirs(os.path.join(ROOT, "dist"), exist_ok=True)
out = os.path.join(ROOT, "dist", "jenjenivive.html")
with open(out, "w", encoding="utf8") as f:
    f.write(html)
print("wrote", out, f"{os.path.getsize(out) / 1024 / 1024:.2f} MB")
