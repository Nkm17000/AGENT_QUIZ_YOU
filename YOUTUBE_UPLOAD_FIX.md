# YouTube Quiz Publishing Behavior

- Manual `workflow_dispatch` or a normal `push`: exactly 1 quiz video.
- Scheduled workflow: exactly 6 videos per run when the 6 JSON sources are present: English, General Science, GK, Math, Reasoning, and Mixed.
- Each source produces one 20-question quiz per scheduled run.
- The mixed JSON produces one quiz per run, not two.
- Source counters advance only after successful YouTube publishing.
- If YouTube returns `uploadLimitExceeded`, the run stops immediately and saves a 24-hour cooldown; no remaining videos are generated.
- Scheduled runs continue to the next subject when a non-limit source error occurs.
- Quiz counters are committed with `if: always()` so successful uploads earlier in a partially failed run are not lost.
