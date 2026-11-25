#!/usr/bin/env python3
"""Regenerate shorts/catalogue.json from js/books-data.js.

The site's product data is the single source of truth for titles, prices and
handles. This flattens it into the shape the Shorts pipeline wants, so the
pipeline never has to parse JavaScript at runtime.

    python3 shorts/build_catalogue.py
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE_DATA = ROOT / "js" / "books-data.js"
OUT = ROOT / "shorts" / "catalogue.json"
STORE = "https://jenjenivive.com"

# Which JJ_DATA lists become products, and what we call that kind of product.
GROUPS = {
    "books": "book",
    "custom": "custom",
    "merch": "merch",
    "bundles": "bundle",
}


def load_site_data() -> dict:
    src = SITE_DATA.read_text(encoding="utf-8")
    match = re.search(r"window\.JJ_DATA\s*=\s*(\{.*?\})\s*;?\s*$", src, re.S)
    if not match:
        raise SystemExit(f"Could not find window.JJ_DATA in {SITE_DATA}")
    return json.loads(match.group(1))


def cover_for(handle: str) -> str | None:
    rel = Path("assets/covers") / f"{handle}.webp"
    return str(rel) if (ROOT / rel).exists() else None


def main() -> None:
    data = load_site_data()
    best = set(data.get("best", []))
    new = set(data.get("new", []))

    products: list[dict] = []
    seen: set[str] = set()

    for key, kind in GROUPS.items():
        for item in data.get(key, []):
            handle = item["h"]
            if handle in seen:
                continue
            seen.add(handle)
            products.append(
                {
                    "handle": handle,
                    "title": item["t"],
                    "price": item.get("p"),
                    "kind": kind,
                    "bestseller": handle in best,
                    "new": handle in new,
                    "url": f"{STORE}/products/{handle}",
                    "cover": cover_for(handle),
                }
            )

    # Bestsellers first, then new arrivals, then everything else. This is the
    # default running order for the schedule: strongest titles go out first
    # while the channel is still finding its audience.
    def rank(p: dict) -> tuple:
        return (0 if p["bestseller"] else 1 if p["new"] else 2, p["title"].lower())

    products.sort(key=rank)

    OUT.write_text(
        json.dumps({"store": STORE, "products": products}, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    missing = [p["handle"] for p in products if not p["cover"]]
    print(f"Wrote {OUT.relative_to(ROOT)}: {len(products)} products")
    if missing:
        print(f"  {len(missing)} without a local cover image: {', '.join(missing[:5])}"
              + (" ..." if len(missing) > 5 else ""))


if __name__ == "__main__":
    main()
