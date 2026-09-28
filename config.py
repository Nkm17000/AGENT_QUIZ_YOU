import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
QUIZ_DIR = Path(os.getenv("QUIZ_DIR", ASSETS_DIR / "quiz_data")).expanduser()
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", BASE_DIR / "output")).expanduser()
OUTPUT_VIDEO = Path(os.getenv("OUTPUT_VIDEO", OUTPUT_DIR / "quiz_video.mp4")).expanduser()
QUESTION_AUDIO_DIR = Path(
    os.getenv("QUESTION_AUDIO_DIR", ASSETS_DIR / "question_audio")
).expanduser()

VIDEO_WIDTH = int(os.getenv("VIDEO_WIDTH", "720"))
VIDEO_HEIGHT = int(os.getenv("VIDEO_HEIGHT", "1280"))
FPS = int(os.getenv("FPS", "15"))

COUNTDOWN_SECONDS = float(os.getenv("COUNTDOWN_SECONDS", "3"))
POST_AUDIO_WAIT_SECONDS = float(os.getenv("POST_AUDIO_WAIT_SECONDS", "3"))
ANSWER_SLIDE_DURATION = float(os.getenv("ANSWER_SLIDE_DURATION", "3"))

BACKGROUND_VOLUME = float(os.getenv("BACKGROUND_VOLUME", "0.30"))
TICK_VOLUME = float(os.getenv("TICK_VOLUME", "0.80"))
CORRECT_VOLUME = float(os.getenv("CORRECT_VOLUME", "1.00"))

TTS_VOICE = os.getenv("TTS_VOICE", "en-IN-NeerjaNeural")
TTS_RATE = os.getenv("TTS_RATE", "+0%")
TTS_VOLUME = os.getenv("TTS_VOLUME", "+0%")

BACKGROUND_AUDIO = ASSETS_DIR / "bg_music.mp3"
TICK_AUDIO = ASSETS_DIR / "tick.mp3"
CORRECT_AUDIO = ASSETS_DIR / "correct.mp3"
LOGO_FILE = ASSETS_DIR / "logo.png"

PAGE_URL = os.getenv("PAGE_URL", "https://smartlearninglab-react.pages.dev").strip()
YOUTUBE_CLIENT_ID = (os.getenv("YOUTUBE_CLIENT_ID") or "").strip()
YOUTUBE_CLIENT_SECRET = (os.getenv("YOUTUBE_CLIENT_SECRET") or "").strip()
YOUTUBE_REFRESH_TOKEN = (os.getenv("YOUTUBE_REFRESH_TOKEN") or "").strip()
YOUTUBE_PLAYLIST_TITLE = (os.getenv("YOUTUBE_PLAYLIST_TITLE", "SMART LEARNING LAB") or "SMART LEARNING LAB").strip()
YOUTUBE_PRIVACY_STATUS = (os.getenv("YOUTUBE_PRIVACY_STATUS", "public") or "public").strip().lower()
YOUTUBE_CATEGORY_ID = (os.getenv("YOUTUBE_CATEGORY_ID", "27") or "27").strip()
YOUTUBE_MADE_FOR_KIDS = (os.getenv("YOUTUBE_MADE_FOR_KIDS", "false") or "false").strip().lower() == "true"
YOUTUBE_LANGUAGE = (os.getenv("YOUTUBE_LANGUAGE", "en") or "en").strip()
YOUTUBE_DEFAULT_TAGS = [
    tag.strip() for tag in
    (os.getenv("YOUTUBE_DEFAULT_TAGS",
     "smart learning lab,quiz,competitive exams,ssc,upsc,banking,railway,ras,ias,gk,mock test").split(","))
    if tag.strip()
]

# Keep TTS generation concurrent so a 20-question quiz does not wait for
# 20 network requests one after another.
TTS_CONCURRENCY = max(1, int(os.getenv("TTS_CONCURRENCY", "6")))

# Faster/lighter H.264 encoding for GitHub Actions.
VIDEO_CRF = int(os.getenv("VIDEO_CRF", "30"))
