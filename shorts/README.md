# YouTube Shorts pipeline

Turns the original clips in your photos folder into branded vertical Shorts, one
per catalogue product, and schedules them to publish **one a day, automatically**.

`My Beaver Loves Wood` and `Coming` are listed in `published.txt`, so the
pipeline skips them everywhere.

---

## Install once

```bash
# ffmpeg does the video work
brew install ffmpeg                 # macOS
sudo apt install ffmpeg             # Ubuntu/Debian
winget install Gyan.FFmpeg          # Windows

# Python bits
pip install Pillow
pip install google-api-python-client google-auth-oauthlib google-auth-httplib2
```

Python 3.11 or newer.

---

## The four steps

```bash
cd /path/to/this/repo

# 1. Pair your clips with products  (point it at your photos folder)
python3 shorts/jjshorts.py match ~/Pictures/JJ-originals

# 2. Render the Shorts
python3 shorts/jjshorts.py build

# 3. Lay them out one per day
python3 shorts/jjshorts.py schedule --start 2026-09-15 --at 17:00

# 4. Upload (YouTube holds each one until its date)
python3 shorts/jjshorts.py upload
```

`python3 shorts/jjshorts.py status` shows where you are at any point.

---

## Step 1 — match

Scans the folder (including subfolders) for videos and images, then pairs each
one with a product.

- A filename that names the book — `my-beaver-loves-wood.mov`, `Coming final
  cut.mp4` — matches on its own with high confidence.
- A camera-roll filename — `IMG_4821.MOV` — carries no information. Those get
  assigned in **capture order** against the remaining catalogue, which is a
  guess, and are written with `confidence` of `0.00`.

It writes `shorts/out/matches.csv`. **Open that in a spreadsheet and fix the
`handle` column** for anything with a low confidence — that column is what
decides which book each clip becomes. Set `include` to `no` to drop a file.
Several rows can share a handle; those clips become one Short, in filename
order.

Valid handles are the `handle` values in `shorts/catalogue.json` — they match
the product URLs on jenjenivive.com.

## Step 2 — build

Renders each Short at 1080×1920, 30fps, H.264/AAC:

- source fitted over a blurred, darkened copy of itself, so square and landscape
  footage gets a backdrop instead of black bars
- stills get a slow Ken Burns push
- persistent title band in the brand palette, plus a `jenjenivive.com` tag
  placed above YouTube's own on-screen controls
- closing card with the cover, price and call to action
- a 1280×720 thumbnail per video

Useful options:

| Option | Does |
| --- | --- |
| `--max-seconds 55` | target length (default 55; YouTube's Shorts limit is 180) |
| `--music bed.mp3` | lays a track under everything, ducked under original audio |
| `--mute` | drops original audio |
| `--only my-beaver-hates-wood` | build a single product, e.g. to check the look |
| `--force` | re-render files that already exist |

Already-rendered files are skipped, so you can stop and restart freely.

## Step 3 — schedule

Assigns one Short per day, same time each day, in catalogue order —
**bestsellers first, then new arrivals, then the rest** — on the theory that the
strongest titles should go out while the channel is still finding an audience.

```bash
python3 shorts/jjshorts.py schedule --start 2026-09-15 --at 17:00 --timezone Europe/London
```

`--every-days 2` spaces them out instead. Times are local and stay local across
a daylight-saving change. Writes `shorts/out/schedule.csv` — edit the
`publish_date` column there if you want to hand-place any of them.

## Step 4 — upload

Each video is uploaded **private with a `publishAt` date**. YouTube flips it to
public on the day by itself; nothing needs to be running.

### The quota ceiling — read this one

The YouTube API gives a new project **10,000 quota units a day**, and one upload
costs **1,600**. That is **six uploads per day**, no matter how fast your
connection is.

So `upload` does six at a time and stops:

```
138 pending, uploading 6 now (~9900 quota units of 10000/day).
Run this again tomorrow — 138 left is about 23 more day(s).
```

**This does not affect the publish dates.** `publishAt` is set at upload time,
so you can spend three weeks feeding videos in while the channel publishes one
a day for four months. Just run `upload` once a day until `status` shows
nothing pending. Progress is saved after every video, so stopping mid-way is
fine.

If you want it faster, request a quota increase in the Google Cloud console
(YouTube Data API → Quotas). Approval takes weeks and is not guaranteed.

### Getting the OAuth credentials

One-off, about five minutes:

1. <https://console.cloud.google.com/> → create a project.
2. **APIs & Services → Library** → enable **YouTube Data API v3**.
3. **APIs & Services → OAuth consent screen** → External → fill in the app name
   and your email → add yourself under **Test users**.
4. **APIs & Services → Credentials → Create credentials → OAuth client ID** →
   application type **Desktop app**.
5. Download the JSON, save it as `shorts/client_secret.json`.

First `upload` run opens a browser to authorise the channel. The token is saved
to `shorts/.token.json` and reused. Both files are gitignored — they are
account credentials, keep them off GitHub.

Check it without uploading anything:

```bash
python3 shorts/jjshorts.py upload --dry-run
```

---

## Files

| Path | What |
| --- | --- |
| `jjshorts.py` | the CLI |
| `jjlib/brand.py` | palette, fonts, overlay and end-card artwork |
| `jjlib/media.py` | ffmpeg probing and rendering |
| `jjlib/plan.py` | matching, the matches sheet, the schedule |
| `jjlib/catalogue.py` | product data and YouTube title/description/tags |
| `jjlib/youtube.py` | OAuth and upload |
| `catalogue.json` | 140 products, generated from `js/books-data.js` |
| `build_catalogue.py` | regenerate that after a catalogue change |
| `published.txt` | handles already live — skipped everywhere |
| `fonts/` | brand fonts as static TTFs for ffmpeg and Pillow |
| `out/` | everything generated (gitignored) |

## Troubleshooting

**`ffmpeg not found`** — install it, then reopen the terminal.

**A Short came out wrong** — fix its row in `matches.csv`, then
`build --only <handle> --force`.

**`publishAt` rejected** — the date is in the past. Re-run `schedule` with a
later `--start`.

**Thumbnail rejected** — custom thumbnails need a phone-verified channel
(<https://youtube.com/verify>). The video still uploads fine without one.

**Video treated as a normal upload, not a Short** — it is over 3 minutes or not
9:16. `build` warns when it renders something over 179 seconds.
