import logging
import shutil
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

from . import auth, config, db, gemini_client, nim_client, youtube_uploader

logger = logging.getLogger(__name__)

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv"}


@contextmanager
def _timed_stage(run_id: int, stage: str, on_progress=None):
    if on_progress:
        on_progress(stage, "started")
    start = time.monotonic()
    try:
        yield
    finally:
        db.record_stage(run_id, stage, time.monotonic() - start)
        if on_progress:
            on_progress(stage, "done")


def _next_video_file() -> Path | None:
    candidates = sorted(
        (p for p in config.SOURCE_DIR.iterdir() if p.suffix.lower() in VIDEO_EXTENSIONS),
        key=lambda p: p.stat().st_mtime,
    )
    return candidates[0] if candidates else None


def _extract_audio(video_path: Path, run_id: int, on_progress=None) -> Path:
    audio_path = config.WORK_DIR / f"{video_path.stem}.wav"
    with _timed_stage(run_id, "extract_audio", on_progress):
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(video_path),
                "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                str(audio_path),
            ],
            check=True, capture_output=True,
        )
    return audio_path


def run_once(on_progress=None) -> bool:
    """Process a single queued video end to end. Returns True if a video was processed.

    on_progress(stage: str, event: 'started'|'done') is called around each stage,
    letting callers (e.g. the dashboard) render live progress.
    """
    db.init_db()
    nim_client.load_skills()
    video_path = _next_video_file()
    if video_path is None:
        logger.info("No video files waiting in %s", config.SOURCE_DIR)
        return False

    run_id = db.start_run(str(video_path))
    logger.info("Run %d: processing %s", run_id, video_path.name)

    try:
        audio_path = _extract_audio(video_path, run_id, on_progress)

        with _timed_stage(run_id, "transcribe", on_progress):
            transcript = gemini_client.transcribe_audio(str(audio_path))

        with _timed_stage(run_id, "generate_metadata", on_progress):
            title = nim_client.generate_title(transcript)
            description = nim_client.generate_description(transcript)
            tags = nim_client.generate_tags(transcript)

        creds = auth.get_credentials()

        with _timed_stage(run_id, "upload", on_progress):
            video_id = youtube_uploader.upload_video(
                creds, str(video_path), title, description, tags, privacy_status="unlisted"
            )

        with _timed_stage(run_id, "wait_processing", on_progress):
            processed = youtube_uploader.wait_until_processed(creds, video_id)

        if not processed:
            db.finish_run(run_id, "failed", video_id=video_id, error="processing_failed")
            return True

        with _timed_stage(run_id, "publish", on_progress):
            youtube_uploader.set_privacy_status(creds, video_id, "public")

        shutil.move(str(video_path), str(config.UPLOADED_DIR / video_path.name))
        audio_path.unlink(missing_ok=True)

        db.finish_run(run_id, "success", video_id=video_id)
        logger.info("Run %d: published as %s", run_id, video_id)
        return True

    except Exception as exc:
        logger.exception("Run %d failed", run_id)
        db.finish_run(run_id, "failed", error=str(exc))
        return True
