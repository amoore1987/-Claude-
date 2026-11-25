"""Source matching, the matches sheet, and the day-by-day publish schedule."""
from __future__ import annotations

import csv
import datetime as dt
import difflib
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

from .catalogue import Product
from .media import IMAGE_EXT, VIDEO_EXT

MATCHES_FIELDS = [
    "source", "handle", "title", "kind", "confidence", "media", "seconds", "include",
]
SCHEDULE_FIELDS = [
    "order", "publish_date", "publish_time_local", "publish_at_utc", "handle",
    "title", "youtube_title", "video", "thumbnail", "status", "video_id", "watch_url",
]

# Filenames a camera roll produces carry no meaning; don't pretend otherwise.
GENERIC_NAME = re.compile(r"^(img|image|photo|video|vid|mov|dsc|dcim|pxl|screenshot)[-_ ]?\d*$", re.I)


@dataclass
class Source:
    path: Path
    captured: dt.datetime
    is_video: bool
    seconds: float = 0.0


@dataclass
class Match:
    source: Path
    handle: str
    title: str
    kind: str
    confidence: float
    media: str
    seconds: float
    include: bool = True


def normalise(text: str) -> str:
    text = re.sub(r"\.[A-Za-z0-9]{2,4}$", "", text)
    text = re.sub(r"[_\-.]+", " ", text)
    text = re.sub(r"[^A-Za-z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip().lower()


# --- scanning ---------------------------------------------------------------

def _captured_at(path: Path) -> dt.datetime:
    """Best available capture time: EXIF, then container metadata, then mtime."""
    if path.suffix.lower() in IMAGE_EXT:
        try:
            from PIL import Image

            with Image.open(path) as im:
                exif = im.getexif()
                for tag in (36867, 36868, 306):  # DateTimeOriginal, Digitized, DateTime
                    if raw := exif.get(tag):
                        return dt.datetime.strptime(str(raw), "%Y:%m:%d %H:%M:%S")
        except Exception:
            pass
    else:
        try:
            out = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries",
                 "format_tags=creation_time", "-of", "default=nw=1:nk=1", str(path)],
                capture_output=True, text=True, timeout=20,
            ).stdout.strip()
            if out:
                return dt.datetime.fromisoformat(out.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            pass
    return dt.datetime.fromtimestamp(path.stat().st_mtime)


def scan_sources(folder: Path) -> list[Source]:
    exts = VIDEO_EXT | IMAGE_EXT
    files = [
        p for p in sorted(folder.rglob("*"))
        if p.is_file() and p.suffix.lower() in exts and not p.name.startswith(".")
    ]
    sources = [
        Source(path=p, captured=_captured_at(p), is_video=p.suffix.lower() in VIDEO_EXT)
        for p in files
    ]
    sources.sort(key=lambda s: (s.captured, s.path.name))
    return sources


# --- matching ---------------------------------------------------------------

def score(name: str, product: Product) -> float:
    """0..1 similarity between a filename and a product."""
    candidates = [normalise(product.title), product.handle.replace("-", " ")]
    best = 0.0
    for cand in candidates:
        best = max(best, difflib.SequenceMatcher(None, name, cand).ratio())
        # A filename that simply contains the handle or title is a certain hit.
        if cand and cand in name:
            best = max(best, 0.97)
    return best


def propose(
    sources: list[Source], products: list[Product], exclude: set[str]
) -> list[Match]:
    """Pair each source with a product.

    Filenames that name the product win. Camera-roll filenames carry no signal,
    so those fall back to capture order against the remaining catalogue — which
    is a guess, flagged with zero confidence for the human to correct.
    """
    available = [p for p in products if p.handle not in exclude]
    taken: set[str] = set()
    matches: list[Match] = []
    unresolved: list[Source] = []

    for src in sources:
        name = normalise(src.path.stem)
        if GENERIC_NAME.match(name.replace(" ", "")):
            unresolved.append(src)
            continue
        ranked = sorted(
            ((score(name, p), p) for p in available if p.handle not in taken),
            key=lambda t: t[0], reverse=True,
        )
        if ranked and ranked[0][0] >= 0.62:
            conf, product = ranked[0]
            taken.add(product.handle)
            matches.append(_match(src, product, conf))
        else:
            unresolved.append(src)

    # Leftovers get the next unused product in catalogue order.
    queue = [p for p in available if p.handle not in taken]
    for src in unresolved:
        product = queue.pop(0) if queue else None
        if product is None:
            matches.append(Match(src.path, "", "", "", 0.0,
                                 "video" if src.is_video else "image", src.seconds, False))
            continue
        taken.add(product.handle)
        matches.append(_match(src, product, 0.0))

    matches.sort(key=lambda m: m.source.name)
    return matches


def _match(src: Source, product: Product, conf: float) -> Match:
    return Match(
        source=src.path,
        handle=product.handle,
        title=product.title,
        kind=product.kind,
        confidence=round(conf, 2),
        media="video" if src.is_video else "image",
        seconds=round(src.seconds, 1),
        include=True,
    )


# --- matches sheet ----------------------------------------------------------

def write_matches(path: Path, matches: list[Match], root: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=MATCHES_FIELDS)
        writer.writeheader()
        for m in matches:
            writer.writerow({
                "source": _relpath(m.source, root),
                "handle": m.handle,
                "title": m.title,
                "kind": m.kind,
                "confidence": f"{m.confidence:.2f}",
                "media": m.media,
                "seconds": f"{m.seconds:.1f}",
                "include": "yes" if m.include else "no",
            })


def read_matches(path: Path, root: Path) -> list[Match]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    out: list[Match] = []
    for row in rows:
        if (row.get("include") or "yes").strip().lower() not in ("yes", "y", "true", "1"):
            continue
        handle = (row.get("handle") or "").strip()
        if not handle:
            continue
        src = Path(row["source"])
        out.append(Match(
            source=src if src.is_absolute() else root / src,
            handle=handle,
            title=(row.get("title") or "").strip(),
            kind=(row.get("kind") or "").strip(),
            confidence=float(row.get("confidence") or 0),
            media=(row.get("media") or "video").strip(),
            seconds=float(row.get("seconds") or 0),
        ))
    return out


def _relpath(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path.resolve())


# --- schedule ---------------------------------------------------------------

@dataclass
class Slot:
    order: int
    publish_local: dt.datetime
    handle: str
    title: str
    youtube_title: str
    video: Path
    thumbnail: Path
    status: str = "pending"
    video_id: str = ""

    @property
    def publish_utc(self) -> dt.datetime:
        return self.publish_local.astimezone(dt.timezone.utc)


def resolve_tz(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except Exception as exc:  # pragma: no cover - depends on host tzdata
        raise SystemExit(
            f"Unknown timezone {name!r} ({exc}). If this is a fresh Python install, "
            "run: pip install tzdata"
        )


def build_slots(
    items: list[tuple[str, str, str, Path, Path]],
    start: dt.date,
    time_of_day: dt.time,
    tz: ZoneInfo,
    every_days: int = 1,
) -> list[Slot]:
    """One item per slot, `every_days` apart, at the same local time each day.

    Local time is fixed, so a schedule that crosses a DST boundary keeps
    landing at the hour the audience expects rather than drifting by an hour.
    """
    slots: list[Slot] = []
    for i, (handle, title, yt_title, video, thumb) in enumerate(items):
        day = start + dt.timedelta(days=i * every_days)
        local = dt.datetime.combine(day, time_of_day, tzinfo=tz)
        slots.append(Slot(i + 1, local, handle, title, yt_title, video, thumb))
    return slots


def write_schedule(path: Path, slots: list[Slot], root: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=SCHEDULE_FIELDS)
        writer.writeheader()
        for s in slots:
            writer.writerow({
                "order": s.order,
                "publish_date": s.publish_local.date().isoformat(),
                "publish_time_local": s.publish_local.strftime("%H:%M %Z"),
                "publish_at_utc": s.publish_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "handle": s.handle,
                "title": s.title,
                "youtube_title": s.youtube_title,
                "video": _relpath(s.video, root),
                "thumbnail": _relpath(s.thumbnail, root),
                "status": s.status,
                "video_id": s.video_id,
                "watch_url": f"https://youtu.be/{s.video_id}" if s.video_id else "",
            })


def read_schedule(path: Path, root: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def update_schedule_row(path: Path, handle: str, **updates: str) -> None:
    """Rewrite one row in place so an interrupted upload run can resume."""
    with path.open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    for row in rows:
        if row["handle"] == handle:
            row.update({k: str(v) for k, v in updates.items()})
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=SCHEDULE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
