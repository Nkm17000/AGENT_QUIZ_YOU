from pathlib import Path

from config import OUTPUT_DIR, PAGE_URL
from services.youtube_service import upload_video_to_youtube
from services.quiz_service import QUIZ_SIZE, commit_quiz_counter, fetch_quizzes
from services.video_service import create_video, generate_images
from utils.file_utils import cleanup
from utils.memory import load_memory, save_memory


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

📚 Daily practice for serious aspirants

🎯 SSC | UPSC | Banking | Railway | RAS | IAS

For more quizzes, visit: {PAGE_URL}

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
    images = generate_images(quiz)
    output_video = _output_path(item)
    output_video.unlink(missing_ok=True)

    try:
        print("🎬 Creating video...")
        create_video(quiz, output_video)

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

    print("📥 Preparing all quizzes...")
    quiz_jobs = fetch_quizzes()
    if not quiz_jobs:
        print("🚫 No quizzes available")
        return

    print(f"🚀 This run will generate {len(quiz_jobs)} videos")
    completed = 0
    failed = 0
    failed_sources = set()

    for item in quiz_jobs:
        # For the mixed source, quiz 2 depends on quiz 1 being successfully
        # completed. If quiz 1 fails, do not consume/skip the next 20 questions.
        if item["source_file"] in failed_sources:
            print(
                f"⏭️ Skipping {item['subject']} quiz {item['quiz_number']} "
                f"because an earlier quiz from the same source failed."
            )
            failed += 1
            continue

        try:
            _generate_one(item)
            completed += 1
        except Exception as exc:
            failed += 1
            failed_sources.add(item["source_file"])
            # Continue to the next source so one failed source does not prevent
            # unrelated subject videos from being generated and uploaded.
            print(
                f"❌ Failed {item['subject']} quiz {item['quiz_number']} "
                f"from {item['source_file']}: {exc}"
            )

    print("\n" + "=" * 80)
    print(f"✅ Completed videos: {completed}/{len(quiz_jobs)}")
    print(f"❌ Failed videos: {failed}/{len(quiz_jobs)}")
    print("=" * 80)

    if failed:
        raise RuntimeError(f"{failed} quiz video job(s) failed")
