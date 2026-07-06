import logging
import time

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

logger = logging.getLogger(__name__)

RETRIABLE_STATUS_CODES = (500, 502, 503, 504)
MAX_UPLOAD_RETRIES = 5


def _service(creds):
    return build("youtube", "v3", credentials=creds)


def upload_video(creds, file_path: str, title: str, description: str, tags: list[str],
                  category_id: str = "20", privacy_status: str = "unlisted") -> str:
    """Resumable upload with chunked progress + retry on transient server errors."""
    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags,
            "categoryId": category_id,
        },
        "status": {"privacyStatus": privacy_status},
    }
    media = MediaFileUpload(file_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    request = _service(creds).videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    error = None
    retries = 0
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                logger.info("Upload progress: %d%%", int(status.progress() * 100))
        except HttpError as exc:
            if exc.resp.status in RETRIABLE_STATUS_CODES:
                error = exc
            else:
                raise
        if error:
            retries += 1
            if retries > MAX_UPLOAD_RETRIES:
                raise error
            delay = 2 ** retries
            logger.warning("Retriable upload error (%s), retrying in %ds", error, delay)
            time.sleep(delay)
            error = None

    return response["id"]


def wait_until_processed(creds, video_id: str, timeout: int = 600, poll_interval: int = 15) -> bool:
    """Poll YouTube until the uploaded video finishes processing."""
    deadline = time.time() + timeout
    service = _service(creds)
    while time.time() < deadline:
        resp = service.videos().list(part="processingDetails", id=video_id).execute()
        items = resp.get("items", [])
        if not items:
            time.sleep(poll_interval)
            continue
        status = items[0]["processingDetails"]["processingStatus"]
        if status == "succeeded":
            return True
        if status == "failed":
            return False
        time.sleep(poll_interval)
    logger.warning("Timed out waiting for video %s to process", video_id)
    return False


def set_privacy_status(creds, video_id: str, status: str = "public"):
    _service(creds).videos().update(
        part="status", body={"id": video_id, "status": {"privacyStatus": status}}
    ).execute()
