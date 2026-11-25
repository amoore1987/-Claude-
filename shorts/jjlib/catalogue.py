"""Product catalogue access and YouTube metadata generation."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CATALOGUE = ROOT / "shorts" / "catalogue.json"

# YouTube's hard limits. Exceeding them makes the API reject the whole upload,
# so metadata is clamped at generation time rather than at upload time.
MAX_TITLE = 100
MAX_DESCRIPTION = 5000
MAX_TAG_CHARS = 500


@dataclass(frozen=True)
class Product:
    handle: str
    title: str
    price: str | None
    kind: str
    bestseller: bool
    new: bool
    url: str
    cover: str | None

    @property
    def cover_path(self) -> Path | None:
        return ROOT / self.cover if self.cover else None


def load() -> list[Product]:
    if not CATALOGUE.exists():
        raise SystemExit(
            f"{CATALOGUE} is missing — run: python3 shorts/build_catalogue.py"
        )
    raw = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    return [Product(**p) for p in raw["products"]]


def by_handle() -> dict[str, Product]:
    return {p.handle: p for p in load()}


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


# --- YouTube metadata -------------------------------------------------------

HOOKS = {
    "book": "The book they'll never admit they laughed at.",
    "custom": "Personalised with their name — which makes it so much worse.",
    "merch": "Wear it. Watch them read it. Enjoy the silence.",
    "bundle": "Every questionable decision, in one box.",
}

BASE_TAGS = [
    "Jen Jenivive",
    "funny books",
    "gag gift",
    "adult humour",
    "novelty book",
    "secret santa",
    "birthday gift idea",
    "rude books",
]


def youtube_title(product: Product) -> str:
    """Short, searchable, and always under the 100-character API limit."""
    suffix = " #shorts"
    base = product.title
    if product.kind == "merch":
        tail = " | Jen Jenivive"
    else:
        tail = " | Funny Gift Book | Jen Jenivive"

    if len(base) + len(tail) + len(suffix) <= MAX_TITLE:
        return f"{base}{tail}{suffix}"
    if len(base) + len(suffix) <= MAX_TITLE:
        return f"{base}{suffix}"
    # Pathological title length — truncate on a word boundary.
    room = MAX_TITLE - len(suffix) - 1
    return base[:room].rsplit(" ", 1)[0] + "…" + suffix


def youtube_description(product: Product) -> str:
    blocks = [
        f"{product.title} — out now.",
        HOOKS.get(product.kind, HOOKS["book"]),
    ]
    if product.price:
        blocks.append(f"£{product.price} — ships from the UK.")
    blocks += [
        f"Grab it here: {product.url}\nBrowse the whole shelf: https://jenjenivive.com",
        "Cheeky humour for unserious adults. New book every day on this channel —\n"
        "subscribe so you don't have to explain your watch history twice.",
        "#shorts #jenjenivive #funnybooks #gaggift #adulthumour #giftideas",
    ]
    return "\n\n".join(blocks)[:MAX_DESCRIPTION]


def youtube_tags(product: Product) -> list[str]:
    tags = [product.title, *BASE_TAGS]
    if product.bestseller:
        tags.append("bestseller")
    if product.kind == "custom":
        tags.append("personalised gift")
    if product.kind == "merch":
        tags += ["funny mug", "funny t shirt"]

    # The API counts the total characters across all tags, not each tag.
    out: list[str] = []
    used = 0
    for tag in tags:
        cost = len(tag) + 2  # quoting overhead YouTube applies per tag
        if used + cost > MAX_TAG_CHARS:
            break
        out.append(tag)
        used += cost
    return out
