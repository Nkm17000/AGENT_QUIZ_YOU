from pathlib import Path
from datetime import datetime, timezone, timedelta
import os

from config import APP_NAME, EDUAPPNAME, FACEBOOK_PAGE_URL, INSTAGRAM_PAGES, OUTPUT_DIR, PAGE_URL
from services.youtube_service import (
    prepare_youtube_destination,
    upload_video_to_youtube,
    YouTubeUploadLimitError,
)
from services.quiz_service import QUIZ_SIZE, commit_quiz_counter, fetch_quizzes
from services.video_service import create_video, generate_images
from utils.file_utils import cleanup
from utils.memory import load_memory, save_memory


YOUTUBE_COOLDOWN_KEY = "youtube_upload_blocked_until"
YOUTUBE_COOLDOWN_HOURS = 24


def _load_youtube_cooldown():
    memory = load_memory()
    raw = memory.get(YOUTUBE_COOLDOWN_KEY)
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _youtube_upload_blocked() -> bool:
    blocked_until = _load_youtube_cooldown()
    if not blocked_until:
        return False
    now = datetime.now(timezone.utc)
    if blocked_until <= now:
        memory = load_memory()
        memory.pop(YOUTUBE_COOLDOWN_KEY, None)
        save_memory(memory)
        return False
    print(
        "⏸️ YouTube upload cooldown active until "
        f"{blocked_until.strftime('%Y-%m-%d %H:%M:%S UTC')}. "
        "Skipping video generation."
    )
    return True


def _set_youtube_cooldown() -> None:
    blocked_until = datetime.now(timezone.utc) + timedelta(hours=YOUTUBE_COOLDOWN_HOURS)
    memory = load_memory()
    memory[YOUTUBE_COOLDOWN_KEY] = blocked_until.isoformat()
    save_memory(memory)
    print(
        "⏸️ YouTube upload limit reached. Cooldown saved until "
        f"{blocked_until.strftime('%Y-%m-%d %H:%M:%S UTC')}."
    )


def _caption(subject: str) -> str:
    if subject == "ALL SUBJECTS":
        heading = "📊 ALL Subject Exam Focus"
        hashtags = "#sscpreparation #upsc #bankexam #railwayexam #ras #ias #mocktest #govtexams #studyreels"
    else:
        display_subject = {
            "ENGLISH": "English",
            "GENERAL SCIENCE": "General Science",
            "GK": "GK",
            "MATH": "Math",
            "REASONING": "Reasoning",
        }.get(subject, subject.title())
        heading = f"📊 {display_subject} Exam Focus"
        hashtags = "#sscpreparation #upsc #bankexam #railwayexam #mocktest #aptitude #reasoning #govtjobs #studyreels"

    return f"""{heading}

📚 {APP_NAME} | Daily practice for serious aspirants

🎯 SSC | UPSC | Banking | Railway | RAS | IAS

For more quizzes, visit: {EDUAPPNAME or PAGE_URL}

Follow us on Instagram: {" | ".join(INSTAGRAM_PAGES)}
Facebook: {FACEBOOK_PAGE_URL}

💬 Drop your answer below

{hashtags}"""


def _safe_name(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")


def _output_path(item) -> Path:
    subject = _safe_name(item["subject"])
    source = _safe_name(Path(item["source_file"]).stem)
    number = item["quiz_number"]
    return OUTPUT_DIR / f"quiz_{subject}_{source}_{number}.mp4"


def _generate_one(item):
    quiz = item["questions"]
    if len(quiz) != QUIZ_SIZE:
        raise RuntimeError(
            f"{item['source_file']} quiz {item['quiz_number']} must contain "
            f"exactly {QUIZ_SIZE} questions; got {len(quiz)}"
        )

    print("\n" + "=" * 80)
    print(
        f"🎯 Generating {item['subject']} quiz "
        f"{item['quiz_number']}/{item['quiz_count_for_source']} "
        f"from {item['source_file']}"
    )
    print(f"📊 Questions: {len(quiz)} | source counter: {item['counter']}")
    print("=" * 80)

    print("🖼️ Rendering slides...")
    images = generate_images(quiz, subject=item["subject"])
    output_video = _output_path(item)
    output_video.unlink(missing_ok=True)

    try:
        print("🎬 Creating video...")
        create_video(quiz, output_video, subject=item["subject"])

        if not output_video.is_file():
            raise RuntimeError(f"Video file was not created: {output_video}")

        caption = _caption(item["subject"])
        print(f"📤 Uploading to YouTube: {caption.splitlines()[0]}")
        result = upload_video_to_youtube(
            str(output_video),
            subject=item["subject"],
            quiz_number=item["quiz_number"],
            description=caption,
        )
        print(f"✅ Uploaded {item['subject']} quiz {item['quiz_number']}: {result.get('url')}")

        # Advance the source counter only after the YouTube upload succeeds.
        # This prevents a failed upload from silently consuming 20 questions.
        new_counter = commit_quiz_counter(item["source_file"], QUIZ_SIZE)

        # Keep a small audit trail so history.json records which source/quiz
        # most recently completed successfully. This is informational only;
        # counters remain the source of truth.
        memory = load_memory()
        last_run = memory.setdefault("last_run", {})
        last_run[item["source_file"]] = {
            "subject": item["subject"],
            "quiz_number": item["quiz_number"],
            "source_counter_after": new_counter,
        }
        save_memory(memory)
        return str(output_video)
    finally:
        cleanup(images)


def run_pipeline():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if _youtube_upload_blocked():
        return

    print("🔐 Validating YouTube OAuth and playlist access...")
    prepare_youtube_destination()
    print("📥 Preparing quizzes for YouTube...")
    quiz_jobs = fetch_quizzes()
    if not quiz_jobs:
        print("🚫 No quizzes available")
        return

    event = os.getenv("GITHUB_EVENT_NAME", "").strip().lower()
    is_manual_run = event in {"workflow_dispatch", "push", ""}
    jobs_to_process = quiz_jobs[:1] if is_manual_run else quiz_jobs

    if is_manual_run:
        print("🖐️ Manual/push run: exactly 1 YouTube video will be generated.")
    else:
        print(f"🗓️ Scheduled run: generating {len(jobs_to_process)} YouTube videos (one per subject/source).")

    completed = 0
    failed = 0
    for item in jobs_to_process:
        try:
            _generate_one(item)
            completed += 1
        except YouTubeUploadLimitError as exc:
            failed += 1
            _set_youtube_cooldown()
            print(f"⏸️ Stopping run after YouTube upload-limit error: {exc}")
            break
        except Exception as exc:
            failed += 1
            print(f"❌ Failed {item['subject']} quiz {item['quiz_number']} from {item['source_file']}: {exc}")
            # Continue with the remaining subjects. A failure in one source
            # must not prevent the other scheduled subjects from publishing.

    print("\n" + "=" * 80)
    print(f"✅ Completed videos: {completed}/{len(jobs_to_process)}")
    print(f"❌ Failed videos: {failed}/{len(jobs_to_process)}")
    print("=" * 80)
