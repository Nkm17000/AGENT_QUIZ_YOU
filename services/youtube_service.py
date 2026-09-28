"""YouTube Data API uploader for generated quiz videos."""

from pathlib import Path
from typing import Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from config import (
    YOUTUBE_CATEGORY_ID,
    YOUTUBE_CLIENT_ID,
    YOUTUBE_CLIENT_SECRET,
    YOUTUBE_DEFAULT_TAGS,
    YOUTUBE_LANGUAGE,
    YOUTUBE_MADE_FOR_KIDS,
    YOUTUBE_PRIVACY_STATUS,
    YOUTUBE_REFRESH_TOKEN,
)

YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
YOUTUBE_API_SERVICE = "youtube"
YOUTUBE_API_VERSION = "v3"

# YouTube video titles are limited to 100 characters.
MAX_TITLE_LENGTH = 100
MAX_DESCRIPTION_LENGTH = 5000


def _require_config() -> None:
    missing = []
    if not YOUTUBE_CLIENT_ID:
        missing.append("YOUTUBE_CLIENT_ID")
    if not YOUTUBE_CLIENT_SECRET:
        missing.append("YOUTUBE_CLIENT_SECRET")
    if not YOUTUBE_REFRESH_TOKEN:
        missing.append("YOUTUBE_REFRESH_TOKEN")

    if missing:
        raise RuntimeError(
            "YouTube OAuth is not configured. Missing GitHub/local environment "
            "variables: " + ", ".join(missing)
        )

    if YOUTUBE_PRIVACY_STATUS not in {"public", "private", "unlisted"}:
        raise ValueError(
            "YOUTUBE_PRIVACY_STATUS must be public, private, or unlisted."
        )


def _youtube_client():
    _require_config()

    credentials = Credentials(
        token=None,
        refresh_token=YOUTUBE_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=YOUTUBE_CLIENT_ID,
        client_secret=YOUTUBE_CLIENT_SECRET,
        scopes=[YOUTUBE_UPLOAD_SCOPE],
    )

    # google-auth refreshes the short-lived access token automatically.
    return build(
        YOUTUBE_API_SERVICE,
        YOUTUBE_API_VERSION,
        credentials=credentials,
        cache_discovery=False,
    )


def _title(subject: str, quiz_number: int) -> str:
    if subject == "ALL SUBJECTS":
        title = f"Daily Mixed Quiz #{quiz_number} | 20 Questions | SSC UPSC Banking Railway"
    else:
        title = f"{subject.title()} Quiz #{quiz_number} | 20 Questions | SSC UPSC Banking Railway"
    return title[:MAX_TITLE_LENGTH]


def _description(
    subject: str,
    quiz_number: int,
    description: str,
) -> str:
    extra = (
        f"\n\nSubject: {subject}\n"
        f"Quiz: {quiz_number}\n"
        "\nSubscribe for daily practice quizzes.\n"
        "Smart Learning Lab — Learn • Practice • Grow"
    )
    return (description + extra)[:MAX_DESCRIPTION_LENGTH]


def upload_video_to_youtube(
    video_path: str,
    subject: str,
    quiz_number: int,
    description: str,
) -> dict:
    """Upload one MP4 to the authenticated YouTube channel."""
    path = Path(video_path)
    if not path.is_file():
        raise FileNotFoundError(f"YouTube video not found: {path}")
    if path.stat().st_size <= 0:
        raise ValueError(f"YouTube video is empty: {path}")

    youtube = _youtube_client()

    body = {
        "snippet": {
            "title": _title(subject, quiz_number),
            "description": _description(subject, quiz_number, description),
            "tags": YOUTUBE_DEFAULT_TAGS,
            "categoryId": YOUTUBE_CATEGORY_ID,
            "defaultLanguage": YOUTUBE_LANGUAGE,
            "defaultAudioLanguage": YOUTUBE_LANGUAGE,
        },
        "status": {
            "privacyStatus": YOUTUBE_PRIVACY_STATUS,
            "selfDeclaredMadeForKids": YOUTUBE_MADE_FOR_KIDS,
        },
    }

    media = MediaFileUpload(
        str(path),
        mimetype="video/mp4",
        chunksize=8 * 1024 * 1024,
        resumable=True,
    )

    print(
        f"📤 YouTube upload: {path.name} "
        f"({path.stat().st_size / 1024 / 1024:.1f} MB), "
        f"privacy={YOUTUBE_PRIVACY_STATUS}"
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                print(f"   YouTube upload progress: {status.progress() * 100:.1f}%")
        except HttpError as exc:
            # Let the pipeline fail cleanly. The source counter is committed
            # only after this function returns successfully.
            raise RuntimeError(
                f"YouTube upload failed with HTTP {exc.resp.status}: {exc}"
            ) from exc

    video_id = response.get("id")
    if not video_id:
        raise RuntimeError(f"YouTube upload returned no video ID: {response}")

    url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"🎬 YouTube video published: {url}")
    return {"video_id": video_id, "url": url, "response": response}
