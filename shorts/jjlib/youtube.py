"""YouTube Data API v3 upload with scheduled publishing.

Quota is the binding constraint, not bandwidth. A default API project gets
10,000 units/day and `videos.insert` costs 1600, so **six uploads per day** is
the ceiling before YouTube starts refusing. The CLI defaults to that and the
schedule is designed to be filled in daily batches over several days — the
publish dates themselves are unaffected, because `publishAt` is set at upload
time and YouTube holds the video private until then.
"""
from __future__ import annotations

import datetime as dt
import json
import random
import time
from pathlib import Path

# videos.insert = 1600 units, thumbnails.set = 50, against a 10,000/day default.
QUOTA_PER_UPLOAD = 1600
QUOTA_PER_THUMBNAIL = 50
DEFAULT_DAILY_QUOTA = 10_000
SAFE_DAILY_UPLOADS = DEFAULT_DAILY_QUOTA // (QUOTA_PER_UPLOAD + QUOTA_PER_THUMBNAIL)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube"]

CATEGORY_ENTERTAINMENT = "24"

IMPORT_HELP = (
    "The upload step needs Google's client libraries:\n"
    "    pip install google-api-python-client google-auth-oauthlib google-auth-httplib2\n"
)


def _load_libs():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        from googleapiclient.http import MediaFileUpload
    except ImportError as exc:
        raise SystemExit(f"{IMPORT_HELP}\n({exc})")
    return Request, Credentials, InstalledAppFlow, build, HttpError, MediaFileUpload


def http_error():
    """The googleapiclient HttpError class, imported lazily."""
    return _load_libs()[4]


def authenticate(client_secrets: Path, token_path: Path):
    """OAuth desktop flow. Opens a browser once, then reuses the saved token."""
    Request, Credentials, InstalledAppFlow, build, _, _ = _load_libs()

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        if not client_secrets.exists():
            raise SystemExit(
                f"Missing {client_secrets}.\n"
                "Create an OAuth client (type: Desktop app) in Google Cloud Console\n"
                "with the YouTube Data API v3 enabled, download the JSON, and save it there.\n"
                "See shorts/README.md for the click-by-click."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets), SCOPES)
        creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
        token_path.chmod(0o600)
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload(
    youtube,
    video: Path,
    title: str,
    description: str,
    tags: list[str],
    publish_at: dt.datetime,
    thumbnail: Path | None = None,
    made_for_kids: bool = False,
) -> str:
    """Upload as private with a publishAt date. Returns the video id."""
    _, _, _, _, HttpError, MediaFileUpload = _load_libs()

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": CATEGORY_ENTERTAINMENT,
        },
        "status": {
            # publishAt is only honoured while the video is private.
            "privacyStatus": "private",
            "publishAt": publish_at.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "selfDeclaredMadeForKids": made_for_kids,
        },
    }

    media = MediaFileUpload(str(video), chunksize=8 * 1024 * 1024, resumable=True,
                            mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    attempt = 0
    while response is None:
        try:
            _, response = request.next_chunk()
        except HttpError as exc:
            if exc.resp.status in (500, 502, 503, 504) and attempt < 5:
                attempt += 1
                time.sleep(min(2 ** attempt, 32) + random.random())
                continue
            raise
    video_id = response["id"]

    if thumbnail and thumbnail.exists():
        try:
            youtube.thumbnails().set(
                videoId=video_id, media_body=MediaFileUpload(str(thumbnail))
            ).execute()
        except HttpError as exc:
            # Custom thumbnails need a verified channel; not worth failing over.
            print(f"    note: thumbnail rejected ({exc.resp.status}) — "
                  "channel may not be verified for custom thumbnails")
    return video_id


def quota_error(exc) -> bool:
    try:
        payload = json.loads(exc.content.decode())
        reasons = {e.get("reason") for e in payload["error"].get("errors", [])}
        return bool(reasons & {"quotaExceeded", "dailyLimitExceeded",
                               "uploadLimitExceeded", "rateLimitExceeded"})
    except Exception:
        return False
