import json
import random
from pathlib import Path

from config import QUIZ_DIR
from utils.memory import load_memory, save_memory

QUIZ_SIZE = 20
MIX_QUIZ_COUNT = 2


def _load_json(path: Path):
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON array")
    return data


def _is_mix_file(path: Path) -> bool:
    return "mixed" in path.stem.casefold()


def _subject_from_file(path: Path) -> str:
    """Map each supported JSON filename to its exact subject label."""
    stem = path.stem.casefold()

    # Check mixed first because the mixed file contains the word subjects from
    # its content but must always be treated as one ALL-SUBJECTS source.
    if _is_mix_file(path):
        return "ALL SUBJECTS"

    exact_patterns = (
        ("english_grammar", "ENGLISH"),
        ("general_science", "GENERAL SCIENCE"),
        ("reasoning", "REASONING"),
        ("math", "MATH"),
        ("gk", "GK"),
    )
    for pattern, subject in exact_patterns:
        if pattern in stem:
            return subject

    return path.stem.replace("_", " ").upper()


def _select_window(data, counter, count, source_name):
    if len(data) < count:
        raise ValueError(
            f"{source_name} contains only {len(data)} questions; "
            f"at least {count} are required."
        )

    # When the current window reaches the end, start a fresh cycle. This keeps
    # every generated quiz exactly the requested size.
    if counter + count > len(data):
        counter = 0

    batch = data[counter:counter + count]
    if len(batch) != count:
        raise ValueError(
            f"Could not select {count} questions from {source_name} at counter {counter}"
        )
    return batch, counter + count


def fetch_quizzes():
    """Return all quizzes to generate in this run.

    Rules:
      * Every normal JSON file produces exactly one 20-question quiz.
      * The mixed JSON file produces exactly two 20-question quizzes.
      * Each source has its own persistent counter.
      * Questions are shuffled only inside each completed quiz.
    """
    files = sorted(Path(QUIZ_DIR).glob("*.json"))
    if not files:
        raise FileNotFoundError(f"No quiz JSON files found in {QUIZ_DIR}")

    mix_files = [path for path in files if _is_mix_file(path)]
    if len(mix_files) > 1:
        raise ValueError(
            "Only one mixed-question JSON file is supported; found: "
            + ", ".join(path.name for path in mix_files)
        )

    memory = load_memory()
    counters = memory.get("counters")
    if not isinstance(counters, dict):
        counters = {}

    # Every JSON file gets its own counter. A newly added file automatically
    # starts at 0 without disturbing the counters of existing files.
    for path in files:
        counters.setdefault(path.name, 0)

    quizzes = []

    for path in files:
        data = _load_json(path)
        source_key = path.name
        counter = int(counters.get(source_key, 0) or 0)
        subject = _subject_from_file(path)

        quiz_count = MIX_QUIZ_COUNT if _is_mix_file(path) else 1
        required = QUIZ_SIZE * quiz_count

        # A mixed file must provide two complete 20-question batches for every
        # run. If the second batch would cross the end, restart its cycle.
        if len(data) < required:
            raise ValueError(
                f"{path.name} contains {len(data)} questions; "
                f"{required} are required for this run."
            )
        if counter + required > len(data):
            counter = 0

        for batch_number in range(quiz_count):
            start = counter + batch_number * QUIZ_SIZE
            batch = data[start:start + QUIZ_SIZE]
            if len(batch) != QUIZ_SIZE:
                raise ValueError(
                    f"{path.name}: expected exactly {QUIZ_SIZE} questions, "
                    f"got {len(batch)} at counter {start}"
                )

            quiz = list(batch)
            random.shuffle(quiz)
            quizzes.append({
                "questions": quiz,
                "subject": subject,
                "source_file": source_key,
                "quiz_number": batch_number + 1,
                "quiz_count_for_source": quiz_count,
                "counter": start,
            })

        print(
            f"🎯 {subject}: planned {quiz_count} quiz{'zes' if quiz_count != 1 else ''} "
            f"of {QUIZ_SIZE} questions from {path.name}; "
            f"starting counter {counter}"
        )

    print(f"📦 Total quizzes this run: {len(quizzes)}")
    for item in quizzes:
        print(
            f"   • {item['subject']} | {item['source_file']} | "
            f"quiz {item['quiz_number']}/{item['quiz_count_for_source']} | "
            f"{len(item['questions'])} questions"
        )

    return quizzes


def commit_quiz_counter(source_file: str, amount: int = QUIZ_SIZE) -> int:
    """Advance one source counter only after its video/upload succeeds."""
    memory = load_memory()
    counters = memory.get("counters")
    if not isinstance(counters, dict):
        counters = {}

    current = int(counters.get(source_file, 0) or 0)
    new_value = current + int(amount)
    counters[source_file] = new_value
    memory["counters"] = counters
    save_memory(memory)
    print(f"💾 Counter committed: {source_file}: {current} -> {new_value}")
    return new_value
