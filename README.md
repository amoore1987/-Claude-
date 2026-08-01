# Jen Jenivive — concept redesign

A fluid, animation-heavy single-page redesign of [jenjenivive.com](https://jenjenivive.com), built
from the official **JJ Brand Guidelines** (palette, fonts, tone of voice) and the live product
catalogue (154 products, 114 books).

> *Cheeky humour for unserious adults.*

## What's in here

| Path | Purpose |
| --- | --- |
| `index.html` | The site — one page, nine animated sections |
| `css/style.css` | Design system + all animation (brand palette, sticker/blob/squiggle language) |
| `js/main.js` | Vanilla JS: scroll reveals, drag shelf, library filters, slot machine, confetti, parallax |
| `js/books-data.js` | Generated product data (titles, prices, handles) scraped from the live Shopify catalogue |
| `assets/covers/` | All 154 product images (640px webp) |
| `assets/brand/` | Logo roundel + wordmark cut out from the brand guidelines PDF |
| `assets/fonts/` | Montserrat, Libre Franklin, Borel (woff2, latin subsets) |
| `build/inline_artifact.py` | Builds `dist/jenjenivive.html`, a fully self-contained single file |

## Run it

Any static server works:

```bash
python3 -m http.server 8000
# open http://localhost:8000
```

Or build the single-file version (no server needed, everything inlined as base64):

```bash
python3 build/inline_artifact.py   # needs Pillow
open dist/jenjenivive.html
```

## Design notes

- **Palette** (from the brand guidelines): `#FAB3F8` pink · `#CD3A8E` magenta · `#B8A9E0` lilac ·
  `#4E217A` purple · `#275B87` navy · `#FDDD0F` yellow · `#8FC4F7` blue.
- **Type**: Libre Franklin (display), Montserrat (body), Borel standing in for the commercial
  script font *Bakerie* named in the guidelines.
- **Sections**: cheeky age gate → hero with floating covers → marquee → stats → draggable
  best-sellers shelf → full 114-book library (filter/search/shuffle) → personalised books
  slot-machine → book club parcel reveal → merch clothesline → about Jen → real customer
  reviews → footer.
- All motion respects `prefers-reduced-motion`. No frameworks, no build step, no external requests
  (fonts and images are local).
- Every "buy" action links to the real product page on jenjenivive.com.

All books, artwork and questionable puns © Jen Jenivive. This is a concept redesign.
