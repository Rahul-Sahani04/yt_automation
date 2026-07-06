# YT AI Upload Automation

Automates: extract audio from a recorded video → transcribe (Gemini) → generate
title/description/tags (NVIDIA NIM, DeepSeek V4 Flash) → upload to YouTube
(resumable, OAuth2) → wait for processing → publish. Includes a Streamlit
dashboard for running it and viewing history/stats.

## Requirements

- Python 3.10+
- `ffmpeg` on PATH (`brew install ffmpeg`)
- Google Gemini API key
- NVIDIA NIM API key
- Google Cloud OAuth2 client (Desktop app) with YouTube Data API v3 enabled

## Setup

```bash
cd yt_automation
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in:

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `GEMINI_API_KEY` | Google Gemini API key (transcription only) |
| `NIM_API_KEY` | NVIDIA NIM API key (title/description/tags) |
| `NIM_MODEL` | Default `deepseek-ai/deepseek-v4-flash` |
| `YT_CLIENT_SECRETS_FILE` | Path to your Google OAuth2 client secrets JSON (Desktop app type) |
| `YT_TOKEN_FILE` | Where the cached OAuth token gets written (auto-created) |
| `SOURCE_DIR` | Folder to drop new videos into (`incoming/`) |
| `UPLOADED_DIR` | Videos get moved here after successful publish |
| `WORK_DIR` | Scratch space for extracted audio |
| `DB_PATH` | SQLite file tracking run history |
| `REPORT_DIR` | Where static chart PNGs get saved |

`.env` and any `client_secret*.json` are gitignored — never commit them.

## One-time login

```bash
python main.py login
```

Opens a browser, log into the YouTube-owning Google account, grants upload
scope. Caches a refresh token in `YT_TOKEN_FILE` — no need to log in again
unless you revoke access.

## Run the pipeline

Drop a video file (`.mp4`, `.mov`, `.mkv`) into `incoming/`, then:

```bash
python main.py run
```

Processes one video end-to-end: transcribe → generate metadata → upload →
wait for YouTube processing → publish → move file to `uploaded/`. Cron it for
hands-off automation:

```cron
*/15 * * * * cd /path/to/yt_automation && .venv/bin/python main.py run >> data/pipeline.log 2>&1
```

## Dashboard (recommended)

```bash
python main.py dashboard
```

Opens an interactive Streamlit page: a "Run pipeline now" button with live
per-stage progress, success/failure metrics, charts (outcomes, uploads/day,
avg stage duration), a thumbnail showcase of published videos, and the full
run history table.

## Static report only

```bash
python main.py report
```

Writes `data/reports/report.png` without launching the dashboard.

## Troubleshooting

- **Upload stuck / fails immediately**: check `YT_TOKEN_FILE` isn't stale —
  delete it and re-run `python main.py login`.
- **ffmpeg: command not found**: install ffmpeg and confirm it's on PATH.
- **NIM 401**: check `NIM_API_KEY` is a valid `integrate.api.nvidia.com` key,
  not a Gemini key.
- Every run is logged to the `runs` table in `DB_PATH` regardless of outcome —
  check the dashboard's run history table or query the DB directly for the
  `error` column on failures.
