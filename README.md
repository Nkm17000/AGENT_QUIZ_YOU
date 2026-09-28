
## YouTube visual update

The YouTube renderer now uses the same professional visual system as the updated
quiz-video renderer:

- Separate English, General Science, GK, Math, Reasoning, and All Subjects themes.
- Clean gradient backgrounds with soft shapes only; no diagonal/cross lines or inner frame.
- A/B/C/D markers have a fixed gap from the option text.
- Four options are kept inside the 720x1280 canvas.
- Answer slides reserve a dedicated high-contrast explanation panel below all four options.
- Hindi and English explanation text use coordinated, high-contrast colors.
- The final MP4 explicitly maps only video and audio streams and disables subtitle streams (`-sn`).
- Subject is passed from `pipeline.py` through `video_service.py` into the renderer.

# Smart Learning Lab — Quiz Video Generator

Automated quiz-video generation and **YouTube channel upload** pipeline.

## Pipeline

```text
JSON question banks
        ↓
Quiz planner
        ↓
20-question batches
        ↓
Shuffle each batch
        ↓
Pillow bilingual slide renderer
        ↓
Edge TTS question narration
        ↓
FFmpeg video + audio mixer
        ↓
MP4 validation
        ↓
YouTube Data API upload
        ↓
Commit source counter
```

## What changed

- Removed Facebook Page publishing.
- Removed Instagram publishing code.
- Added YouTube Data API v3 upload.
- Added OAuth 2.0 refresh-token authentication for unattended GitHub Actions runs.
- Upload is resumable using Google's YouTube client library.
- Source counters advance **only after a successful YouTube upload**.
- The generated video title, description, tags, category and privacy status are configurable.
- The workflow still supports push, manual `workflow_dispatch`, and the existing schedule.

## YouTube setup

Google's YouTube Data API requires OAuth authorization for uploads. An API key alone is not enough. The upload scope used here is:

`https://www.googleapis.com/auth/youtube.upload`

Google documents `videos.insert` as the API method for uploading videos and supports resumable media uploads. See:

- YouTube `videos.insert`: https://developers.google.com/youtube/v3/docs/videos/insert
- YouTube upload guide: https://developers.google.com/youtube/v3/guides/uploading_a_video
- OAuth 2.0 for server-side applications: https://developers.google.com/youtube/v3/guides/auth/server-side-web-apps

### 1. Create a Google Cloud project

In Google Cloud:

1. Create/select a project.
2. Enable **YouTube Data API v3**.
3. Configure the OAuth consent screen.
4. Create an OAuth 2.0 client for a desktop/installed application.
5. Download the client JSON file locally.

Do not commit the JSON file to Git.

### 2. Generate the refresh token once

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Run:

```bash
python scripts/get_youtube_refresh_token.py client_secret.json
```

A browser window will open. Sign in with the Google account that owns/manages the YouTube channel and approve YouTube upload access.

The script prints:

```text
YOUTUBE_CLIENT_ID=...
YOUTUBE_CLIENT_SECRET=...
YOUTUBE_REFRESH_TOKEN=...
```

Keep the refresh token private.

### 3. Add GitHub Actions secrets

Repository → **Settings → Secrets and variables → Actions → New repository secret**

Add:

- `YOUTUBE_CLIENT_ID`
- `YOUTUBE_CLIENT_SECRET`
- `YOUTUBE_REFRESH_TOKEN`

No Facebook secrets are required by this project.

### 4. YouTube upload settings

The workflow currently uses:

```text
YOUTUBE_PRIVACY_STATUS=public
YOUTUBE_CATEGORY_ID=27
YOUTUBE_MADE_FOR_KIDS=false
YOUTUBE_LANGUAGE=en
```

Change these in `.github/workflows/run.yml` if required.

### Important YouTube API limitation

Google currently states that videos uploaded through `videos.insert` by **unverified API projects created after July 28, 2020** are restricted to private viewing until the API project completes the required audit. Therefore, the workflow can request `public`, but an affected unverified project may still result in a private upload. See the official `videos.insert` documentation for the current rule.

### Quota

YouTube currently documents a default allowance of **100 `videos.insert` calls per day** in its dedicated upload quota bucket. This project makes one `videos.insert` call per generated video. If the daily upload limit is reached, the affected job fails and its quiz counter is not advanced.

## Schedule

The workflow runs at:

- 02:00 UTC
- 08:00 UTC
- 14:00 UTC
- 20:00 UTC

It also runs on every push to `main` except when the only changed file is `data/history/history.json`, and it can be started manually with `workflow_dispatch`.

## Quiz rules

- Normal JSON source: 1 × 20-question quiz.
- Mixed JSON source: 2 × 20-question quizzes.
- Questions are selected sequentially from each source counter and shuffled inside the generated quiz.
- Counters advance only after the video is generated and successfully uploaded to YouTube.
- If one source fails, other sources continue processing.
- If a mixed-source quiz fails, the next mixed quiz is skipped for that run so the source counter cannot silently jump over an unsuccessful batch.

## Run locally

Set the YouTube variables in `.env`:

```text
YOUTUBE_CLIENT_ID=...
YOUTUBE_CLIENT_SECRET=...
YOUTUBE_REFRESH_TOKEN=...
YOUTUBE_PRIVACY_STATUS=public
```

Then:

```bash
python -m pip install -r requirements.txt
python app.py
```

FFmpeg and FFprobe must be installed and available on `PATH`.

## Security

Never commit:

- `client_secret.json`
- YouTube refresh tokens
- `.env`
- GitHub Actions secrets

The project `.gitignore` already excludes these credential files.
