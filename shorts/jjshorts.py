#!/usr/bin/env python3
"""Jen Jenivive — YouTube Shorts pipeline.

Four steps, in order:

    match     Pair the clips in your photos folder with catalogue products.
    build     Render branded 1080x1920 Shorts + thumbnails.
    schedule  Lay them out one per day and write the publish calendar.
    upload    Push to YouTube as private-with-publishAt, in quota-safe batches.

Run `python3 shorts/jjshorts.py <step> --help` for the options on each.
"""
from __future__ import annotations

import argparse
import datetime as dt
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from jjlib import brand, catalogue, media, plan, youtube  # noqa: E402
from jjlib.catalogue import Product  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "shorts" / "out"
MATCHES_CSV = OUT / "matches.csv"
SCHEDULE_CSV = OUT / "schedule.csv"
VIDEO_DIR = OUT / "video"
THUMB_DIR = OUT / "thumb"
WORK_DIR = OUT / "work"

# Already live on the channel — never re-cut, never re-upload.
PUBLISHED = ROOT / "shorts" / "published.txt"


def published_handles() -> set[str]:
    if not PUBLISHED.exists():
        return set()
    return {
        line.strip() for line in PUBLISHED.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


# --- match ------------------------------------------------------------------

def cmd_match(args: argparse.Namespace) -> int:
    folder = Path(args.folder).expanduser().resolve()
    if not folder.is_dir():
        print(f"No such folder: {folder}", file=sys.stderr)
        return 1

    sources = plan.scan_sources(folder)
    if not sources:
        print(f"No photos or videos found under {folder}")
        return 1

    # Duration is only needed for the sheet's information column.
    if shutil.which("ffprobe"):
        for s in sources:
            if s.is_video:
                try:
                    s.seconds = media.probe(s.path).duration
                except Exception:
                    pass

    skip = published_handles()
    matches = plan.propose(sources, catalogue.load(), exclude=skip)
    plan.write_matches(MATCHES_CSV, matches, ROOT)

    sure = [m for m in matches if m.confidence >= 0.62]
    guessed = [m for m in matches if 0 < m.confidence < 0.62]
    blind = [m for m in matches if m.confidence == 0 and m.handle]
    orphan = [m for m in matches if not m.handle]

    print(f"Scanned {len(sources)} file(s) in {folder}")
    print(f"  {len(sure)} matched from the filename")
    if guessed:
        print(f"  {len(guessed)} matched loosely")
    if blind:
        print(f"  {len(blind)} had camera-roll filenames — assigned in capture order (a guess)")
    if orphan:
        print(f"  {len(orphan)} left over, no product free")
    if skip:
        print(f"  {len(skip)} product(s) skipped as already published: {', '.join(sorted(skip))}")
    print()
    print(f"Wrote {MATCHES_CSV.relative_to(ROOT)}")
    if blind or guessed:
        print("Open it and fix the `handle` column before building — anything with a low")
        print("confidence is a guess. Set `include` to no to drop a file.")
    return 0


# --- build ------------------------------------------------------------------

def cmd_build(args: argparse.Namespace) -> int:
    try:
        media.require_ffmpeg()
    except media.FFmpegMissing as exc:
        print(exc, file=sys.stderr)
        return 1

    if not MATCHES_CSV.exists():
        print(f"{MATCHES_CSV.relative_to(ROOT)} not found — run `match` first.", file=sys.stderr)
        return 1

    matches = plan.read_matches(MATCHES_CSV, ROOT)
    products = catalogue.by_handle()
    skip = published_handles()

    # Several clips can belong to one product; they become one Short in order.
    grouped: dict[str, list[plan.Match]] = {}
    for m in matches:
        if m.handle in skip:
            continue
        grouped.setdefault(m.handle, []).append(m)

    if args.only:
        grouped = {h: v for h, v in grouped.items() if h in set(args.only)}
    if args.limit:
        grouped = dict(list(grouped.items())[: args.limit])

    for d in (VIDEO_DIR, THUMB_DIR, WORK_DIR):
        d.mkdir(parents=True, exist_ok=True)

    music = Path(args.music).expanduser().resolve() if args.music else None
    if music and not music.exists():
        print(f"Music track not found: {music}", file=sys.stderr)
        return 1

    ok = failed = skipped = 0
    for index, (handle, clips) in enumerate(sorted(grouped.items())):
        product = products.get(handle)
        if product is None:
            print(f"  ! {handle}: not in the catalogue — skipping")
            failed += 1
            continue

        dest = VIDEO_DIR / f"{handle}.mp4"
        if dest.exists() and not args.force:
            skipped += 1
            continue

        print(f"[{index + 1}/{len(grouped)}] {product.title}")
        try:
            _render_one(product, clips, dest, music, args)
            ok += 1
        except Exception as exc:
            print(f"  ! failed: {exc}")
            dest.unlink(missing_ok=True)
            failed += 1

    print()
    print(f"Built {ok}, skipped {skipped} (already rendered), failed {failed}")
    print(f"Videos: {VIDEO_DIR.relative_to(ROOT)}   Thumbnails: {THUMB_DIR.relative_to(ROOT)}")
    if skipped and not args.force:
        print("Pass --force to re-render existing files.")
    return 0 if failed == 0 else 1


def _render_one(
    product: Product,
    clips: list[plan.Match],
    dest: Path,
    music: Path | None,
    args: argparse.Namespace,
) -> None:
    accent = brand.accent_for(product.handle)
    work = WORK_DIR / product.handle
    work.mkdir(parents=True, exist_ok=True)

    caption = "Bestseller" if product.bestseller else ("New" if product.new else None)
    overlay = work / "overlay.png"
    brand.title_overlay(product.title, accent, caption).save(overlay)

    endcard_png = work / "endcard.png"
    brand.end_card(product.title, product.price, accent, product.cover_path).save(endcard_png)

    # Share the clip budget so a multi-clip Short still lands near the target.
    per_clip = max(args.max_seconds / max(len(clips), 1), 3.0)

    segments: list[Path] = []
    for i, clip in enumerate(clips):
        if not clip.source.exists():
            raise FileNotFoundError(f"source missing: {clip.source}")
        seg = work / f"seg{i:02d}.mp4"
        if clip.media == "image" or clip.source.suffix.lower() in media.IMAGE_EXT:
            media.render_still_segment(clip.source, overlay, seg,
                                       seconds=min(per_clip, args.still_seconds))
        else:
            media.render_video_segment(clip.source, overlay, seg,
                                       max_seconds=per_clip, mute=args.mute)
        segments.append(seg)

    if not args.no_end_card:
        end_seg = work / "end.mp4"
        media.render_end_card(endcard_png, end_seg, seconds=args.end_seconds)
        segments.append(end_seg)

    media.concat(segments, dest, music=music)

    thumb = THUMB_DIR / f"{product.handle}.jpg"
    brand.thumbnail(product.title, accent, product.cover_path).save(thumb, quality=88)

    length = media.duration_of(dest)
    print(f"    {dest.name}  {length:.1f}s")
    if length > 179:
        print("    ! longer than 3 minutes — YouTube will treat this as a normal video,"
              " not a Short")

    if not args.keep_work:
        for f in work.glob("*"):
            f.unlink(missing_ok=True)
        work.rmdir()


# --- schedule ---------------------------------------------------------------

def cmd_schedule(args: argparse.Namespace) -> int:
    products = catalogue.by_handle()
    skip = published_handles()

    if not VIDEO_DIR.exists():
        print(f"No rendered videos in {VIDEO_DIR.relative_to(ROOT)} — run `build` first.",
              file=sys.stderr)
        return 1

    videos = {p.stem: p for p in sorted(VIDEO_DIR.glob("*.mp4")) if p.stem not in skip}
    if not videos:
        print("Nothing to schedule.", file=sys.stderr)
        return 1

    # Catalogue order is already bestsellers → new → the rest, which is the
    # order you want to go out in.
    ordered = [p for p in catalogue.load() if p.handle in videos]

    tz = plan.resolve_tz(args.timezone)
    start = (dt.date.fromisoformat(args.start) if args.start
             else dt.date.today() + dt.timedelta(days=1))
    hour, _, minute = args.at.partition(":")
    time_of_day = dt.time(int(hour), int(minute or 0))

    now_local = dt.datetime.now(tz)
    first = dt.datetime.combine(start, time_of_day, tzinfo=tz)
    if first <= now_local:
        print(f"! {first:%Y-%m-%d %H:%M %Z} is in the past — YouTube rejects a publishAt "
              "that isn't in the future.", file=sys.stderr)
        return 1

    items = [
        (p.handle, p.title, catalogue.youtube_title(p), videos[p.handle],
         THUMB_DIR / f"{p.handle}.jpg")
        for p in ordered
    ]
    slots = plan.build_slots(items, start, time_of_day, tz, every_days=args.every_days)

    # Keep any ids already recorded so re-running schedule doesn't lose them.
    if SCHEDULE_CSV.exists():
        previous = {r["handle"]: r for r in plan.read_schedule(SCHEDULE_CSV, ROOT)}
        for s in slots:
            if old := previous.get(s.handle):
                s.status = old.get("status") or s.status
                s.video_id = old.get("video_id") or ""

    plan.write_schedule(SCHEDULE_CSV, slots, ROOT)

    last = slots[-1].publish_local
    print(f"Scheduled {len(slots)} Shorts, one every {args.every_days} day(s) at "
          f"{time_of_day:%H:%M} {tz.key}")
    print(f"  first: {slots[0].publish_local:%a %d %b %Y %H:%M %Z}  — {slots[0].title}")
    print(f"  last:  {last:%a %d %b %Y %H:%M %Z}  — {slots[-1].title}")
    print(f"  that's {(last.date() - slots[0].publish_local.date()).days + 1} days of content")
    print()
    print(f"Wrote {SCHEDULE_CSV.relative_to(ROOT)}")
    return 0


# --- upload -----------------------------------------------------------------

def cmd_upload(args: argparse.Namespace) -> int:
    yt = youtube

    if not SCHEDULE_CSV.exists():
        print(f"{SCHEDULE_CSV.relative_to(ROOT)} not found — run `schedule` first.",
              file=sys.stderr)
        return 1

    rows = plan.read_schedule(SCHEDULE_CSV, ROOT)
    pending = [r for r in rows if r.get("status") != "uploaded"]
    if not pending:
        print("Everything in the schedule is already uploaded.")
        return 0

    limit = args.limit if args.limit is not None else yt.SAFE_DAILY_UPLOADS
    batch = pending[:limit]
    products = catalogue.by_handle()

    print(f"{len(pending)} pending, uploading {len(batch)} now "
          f"(~{len(batch) * (yt.QUOTA_PER_UPLOAD + yt.QUOTA_PER_THUMBNAIL)} quota units "
          f"of {yt.DEFAULT_DAILY_QUOTA}/day).")
    if len(pending) > len(batch):
        days = -(-len(pending) // max(limit, 1))
        print(f"Run this again tomorrow — {len(pending)} left is about {days} more day(s).")
    print()

    if args.dry_run:
        for r in batch:
            print(f"  would upload {r['video']}")
            print(f"    title:      {r['youtube_title']}")
            print(f"    publish at: {r['publish_at_utc']} ({r['publish_time_local']} local)")
        return 0

    service = yt.authenticate(
        Path(args.client_secrets).expanduser(), Path(args.token).expanduser()
    )
    HttpError = yt.http_error()

    done = 0
    for r in batch:
        product = products.get(r["handle"])
        if product is None:
            print(f"  ! {r['handle']}: not in the catalogue — skipping")
            continue
        video = ROOT / r["video"]
        thumb = ROOT / r["thumbnail"]
        if not video.exists():
            print(f"  ! {video} missing — skipping")
            continue

        publish_at = dt.datetime.strptime(r["publish_at_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=dt.timezone.utc
        )
        if publish_at <= dt.datetime.now(dt.timezone.utc):
            print(f"  ! {product.title}: publish time has passed — re-run `schedule`")
            continue

        print(f"  uploading {product.title} → live {r['publish_date']} {r['publish_time_local']}")
        try:
            video_id = yt.upload(
                service, video,
                title=r["youtube_title"],
                description=catalogue.youtube_description(product),
                tags=catalogue.youtube_tags(product),
                publish_at=publish_at,
                thumbnail=thumb if thumb.exists() else None,
            )
        except HttpError as exc:
            if yt.quota_error(exc):
                print("  ! daily quota exhausted — stopping. Progress is saved; "
                      "run again tomorrow.")
                break
            print(f"  ! failed: {exc}")
            continue

        plan.update_schedule_row(
            SCHEDULE_CSV, r["handle"], status="uploaded", video_id=video_id,
            watch_url=f"https://youtu.be/{video_id}",
        )
        print(f"    https://youtu.be/{video_id}")
        done += 1

    print()
    print(f"Uploaded {done}. {len(pending) - done} still pending.")
    return 0


# --- status -----------------------------------------------------------------

def cmd_status(args: argparse.Namespace) -> int:
    total = len(catalogue.load())
    live = published_handles()
    built = len(list(VIDEO_DIR.glob("*.mp4"))) if VIDEO_DIR.exists() else 0

    print(f"Catalogue      {total} products")
    print(f"Already live   {len(live)}" + (f" ({', '.join(sorted(live))})" if live else ""))
    print(f"Rendered       {built}")

    if SCHEDULE_CSV.exists():
        rows = plan.read_schedule(SCHEDULE_CSV, ROOT)
        uploaded = [r for r in rows if r.get("status") == "uploaded"]
        pending = [r for r in rows if r.get("status") != "uploaded"]
        print(f"Scheduled      {len(rows)}")
        print(f"  uploaded     {len(uploaded)}")
        print(f"  pending      {len(pending)}")
        if pending:
            nxt = pending[0]
            print(f"  next up      {nxt['title']} on {nxt['publish_date']} "
                  f"{nxt['publish_time_local']}")
        if pending:
            print(f"  upload days  ~{-(-len(pending) // youtube.SAFE_DAILY_UPLOADS)} at "
                  f"{youtube.SAFE_DAILY_UPLOADS}/day API quota")
    else:
        print("Scheduled      — (run `schedule`)")
    return 0


# --- CLI --------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="jjshorts", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    m = sub.add_parser("match", help="pair source clips with catalogue products")
    m.add_argument("folder", help="folder holding the original photos/videos")
    m.set_defaults(func=cmd_match)

    b = sub.add_parser("build", help="render the Shorts")
    b.add_argument("--max-seconds", type=float, default=55.0,
                   help="target length per Short (default: 55; YouTube's limit is 180)")
    b.add_argument("--still-seconds", type=float, default=7.0,
                   help="seconds to hold each still image (default: 7)")
    b.add_argument("--end-seconds", type=float, default=2.5,
                   help="length of the closing card (default: 2.5)")
    b.add_argument("--no-end-card", action="store_true", help="skip the closing card")
    b.add_argument("--mute", action="store_true", help="drop original audio")
    b.add_argument("--music", help="audio file to lay under every Short")
    b.add_argument("--only", nargs="+", metavar="HANDLE", help="build just these products")
    b.add_argument("--limit", type=int, help="build at most N")
    b.add_argument("--force", action="store_true", help="re-render files that already exist")
    b.add_argument("--keep-work", action="store_true", help="keep intermediate files")
    b.set_defaults(func=cmd_build)

    s = sub.add_parser("schedule", help="lay the Shorts out one per day")
    s.add_argument("--start", help="first publish date, YYYY-MM-DD (default: tomorrow)")
    s.add_argument("--at", default="17:00", help="local publish time (default: 17:00)")
    s.add_argument("--timezone", default="Europe/London", help="default: Europe/London")
    s.add_argument("--every-days", type=int, default=1,
                   help="gap between videos (default: 1 = daily)")
    s.set_defaults(func=cmd_schedule)

    u = sub.add_parser("upload", help="upload to YouTube with scheduled publishing")
    u.add_argument("--limit", type=int,
                   help=f"how many to upload now "
                        f"(default: {youtube.SAFE_DAILY_UPLOADS}, the API quota ceiling)")
    u.add_argument("--client-secrets", default=str(ROOT / "shorts" / "client_secret.json"))
    u.add_argument("--token", default=str(ROOT / "shorts" / ".token.json"))
    u.add_argument("--dry-run", action="store_true", help="show what would be uploaded")
    u.set_defaults(func=cmd_upload)

    st = sub.add_parser("status", help="show pipeline progress")
    st.set_defaults(func=cmd_status)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
