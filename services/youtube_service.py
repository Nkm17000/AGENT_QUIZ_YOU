"""YouTube Data API uploader for generated quiz videos."""

from pathlib import Path
from datetime import datetime, timezone

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
    YOUTUBE_PLAYLIST_TITLE,
    YOUTUBE_PRIVACY_STATUS,
    YOUTUBE_REFRESH_TOKEN,
)

YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
YOUTUBE_PLAYLIST_SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"
YOUTUBE_API_SERVICE = "youtube"
YOUTUBE_API_VERSION = "v3"
_PLAYLIST_ID = None

# YouTube video titles are limited to 100 characters.
MAX_TITLE_LENGTH = 100
MAX_DESCRIPTION_LENGTH = 5000


class YouTubeUploadLimitError(RuntimeError):
    """Raised when YouTube blocks uploads because the channel upload limit was reached."""

    def __init__(self, message: str, retry_after_hours: int = 24):
        super().__init__(message)
        self.retry_after_hours = retry_after_hours


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
        scopes=[YOUTUBE_UPLOAD_SCOPE, YOUTUBE_PLAYLIST_SCOPE],
    )

    # google-auth refreshes the short-lived access token automatically.
    return build(
        YOUTUBE_API_SERVICE,
        YOUTUBE_API_VERSION,
        credentials=credentials,
        cache_discovery=False,
    )


def _subject_code(subject: str) -> str:
    return {
        "ALL SUBJECTS": "MIX",
        "ENGLISH": "ENG",
        "GENERAL SCIENCE": "SCI",
        "GK": "GK",
        "MATH": "MATH",
        "REASONING": "REAS",
    }.get(subject, "GEN")


def _video_identifier(subject: str, quiz_number: int) -> str:
    # Human-readable identifier shown in both the title and description.
    # UTC keeps the ID stable across local machines and GitHub runners.
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"SLL-{_subject_code(subject)}-{stamp}-Q{quiz_number}"


def _title(subject: str, quiz_number: int, video_identifier: str) -> str:
    if subject == "ALL SUBJECTS":
        base = f"Daily Mixed Quiz #{quiz_number} | 20 Questions | SSC UPSC Banking Railway"
    else:
        base = f"{subject.title()} Quiz #{quiz_number} | 20 Questions | SSC UPSC Banking Railway"
    title = f"[{video_identifier}] {base}"
    return title[:MAX_TITLE_LENGTH]


def _description(
    subject: str,
    quiz_number: int,
    description: str,
    video_identifier: str,
) -> str:
    extra = (
        f"\n\nVideo ID: {video_identifier}\n"
        f"Subject: {subject}\n"
        f"Quiz: {quiz_number}\n"
        "\nUse the Video ID above when referring to this quiz.\n"
        "Subscribe for daily practice quizzes.\n"
        "Smart Learning Lab — Learn • Practice • Grow"
    )
    return (description + extra)[:MAX_DESCRIPTION_LENGTH]


def _find_or_create_playlist(youtube) -> str:
    """Return the ID of the configured playlist, creating it if necessary."""
    page_token = None
    while True:
        response = youtube.playlists().list(
            part="id,snippet",
            mine=True,
            maxResults=50,
            pageToken=page_token,
        ).execute()
        for playlist in response.get("items", []):
            if playlist.get("snippet", {}).get("title", "").strip().casefold() == YOUTUBE_PLAYLIST_TITLE.casefold():
                playlist_id = playlist.get("id")
                if playlist_id:
                    return playlist_id
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    created = youtube.playlists().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": YOUTUBE_PLAYLIST_TITLE,
                "description": "Smart Learning Lab daily quiz videos.",
            },
            "status": {"privacyStatus": "public"},
        },
    ).execute()
    playlist_id = created.get("id")
    if not playlist_id:
        raise RuntimeError(f"YouTube playlist creation returned no ID: {created}")
    print(f"📚 YouTube playlist ready: {YOUTUBE_PLAYLIST_TITLE} ({playlist_id})")
    return playlist_id


def prepare_youtube_destination() -> str:
    """Authenticate and ensure the target playlist exists before video generation."""
    global _PLAYLIST_ID
    if _PLAYLIST_ID:
        return _PLAYLIST_ID
    youtube = _youtube_client()
    _PLAYLIST_ID = _find_or_create_playlist(youtube)
    return _PLAYLIST_ID


def _add_to_playlist(youtube, playlist_id: str, video_id: str, video_identifier: str) -> None:
    youtube.playlistItems().insert(
        part="snippet,contentDetails",
        body={
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {"kind": "youtube#video", "videoId": video_id},
            },
            "contentDetails": {"note": video_identifier},
        },
    ).execute()
    print(f"📚 Added {video_identifier} to playlist: {YOUTUBE_PLAYLIST_TITLE}")



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
    playlist_id = prepare_youtube_destination()

    video_identifier = _video_identifier(subject, quiz_number)

    body = {
        "snippet": {
            "title": _title(subject, quiz_number, video_identifier),
            "description": _description(subject, quiz_number, description, video_identifier),
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
            details = str(exc)
            if "uploadLimitExceeded" in details or "exceeded the number of videos" in details:
                raise YouTubeUploadLimitError(
                    "YouTube upload limit reached. YouTube requires waiting before "
                    "additional uploads can be accepted; no source counter was advanced."
                ) from exc

            raise RuntimeError(
                f"YouTube upload failed with HTTP {exc.resp.status}: {exc}"
            ) from exc

    video_id = response.get("id")
    if not video_id:
        raise RuntimeError(f"YouTube upload returned no video ID: {response}")

    try:
        _add_to_playlist(youtube, playlist_id, video_id, video_identifier)
    except HttpError as exc:
        raise RuntimeError(
            f"YouTube playlist update failed with HTTP {exc.resp.status}: {exc}"
        ) from exc

    url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"🎬 YouTube video published: {url}")
    return {"video_id": video_id, "url": url, "playlist_id": playlist_id, "video_identifier": video_identifier, "response": response}
