import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from googleapiclient.discovery import build

from src import auth, config, db, nim_client, pipeline

STAGE_LABELS = {
    "extract_audio": "Extract audio",
    "transcribe": "Transcribe",
    "generate_metadata": "Generate title/description/tags",
    "upload": "Upload to YouTube",
    "wait_processing": "Wait for YouTube processing",
    "publish": "Publish (make public)",
}

st.set_page_config(page_title="YT AI Upload Automation", layout="wide")
db.init_db()
nim_client.load_skills()


def fetch_runs():
    with db.connect() as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("SELECT * FROM runs ORDER BY started_at DESC").fetchall()


st.title("YT AI Upload Automation")

col_a, col_b = st.columns([1, 3])
with col_a:
    if st.button("Run pipeline now", type="primary"):
        stage_keys = list(STAGE_LABELS)
        progress_bar = st.progress(0.0)
        step_rows = {key: st.empty() for key in stage_keys}
        for key in stage_keys:
            step_rows[key].write(f"⬜ {STAGE_LABELS[key]}")

        def on_progress(stage, event):
            label = STAGE_LABELS.get(stage, stage)
            if event == "started":
                step_rows[stage].write(f"🔵 {label}...")
            else:
                step_rows[stage].write(f"✅ {label}")
                progress_bar.progress((stage_keys.index(stage) + 1) / len(stage_keys))

        processed = pipeline.run_once(on_progress=on_progress)
        if processed:
            latest = fetch_runs()[0]
            if latest["status"] == "success" and latest["video_id"]:
                st.session_state["last_uploaded_url"] = f"https://youtu.be/{latest['video_id']}"
        else:
            st.info("Nothing to process")
        st.rerun()

if url := st.session_state.get("last_uploaded_url"):
    st.success(f"Uploaded! Visit: {url}")

runs = fetch_runs()

total = len(runs)
successes = sum(1 for r in runs if r["status"] == "success")
failures = sum(1 for r in runs if r["status"] == "failed")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total runs", total)
m2.metric("Successful uploads", successes)
m3.metric("Failed", failures)
m4.metric("Success rate", f"{(successes / total * 100):.0f}%" if total else "n/a")
st.progress(successes / total if total else 0)

st.subheader("Recent uploads")
published = [r for r in runs if r["status"] == "success" and r["video_id"]][:8]
if not published:
    st.write("No published videos yet.")
else:
    cols = st.columns(4)
    for i, r in enumerate(published):
        with cols[i % 4]:
            st.image(f"https://img.youtube.com/vi/{r['video_id']}/hqdefault.jpg")
            st.markdown(f"[Watch](https://youtu.be/{r['video_id']})")
            st.caption(datetime.fromtimestamp(r["started_at"]).strftime("%Y-%m-%d %H:%M"))

st.subheader("Pending uploads")


def _thumbnail_for(video_path: Path) -> Path | None:
    thumb_path = config.WORK_DIR / f"{video_path.stem}_thumb.jpg"
    if thumb_path.exists() and thumb_path.stat().st_mtime >= video_path.stat().st_mtime:
        return thumb_path
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-ss", "1", "-i", str(video_path), "-frames:v", "1", str(thumb_path)],
            check=True, capture_output=True,
        )
        return thumb_path
    except Exception:
        return None


pending_files = sorted(
    (p for p in config.SOURCE_DIR.iterdir() if p.suffix.lower() in pipeline.VIDEO_EXTENSIONS),
    key=lambda p: p.stat().st_mtime,
)
if not pending_files:
    st.write("Nothing queued.")
else:
    cols = st.columns(4)
    for i, p in enumerate(pending_files):
        with cols[i % 4]:
            thumb = _thumbnail_for(p)
            if thumb:
                st.image(str(thumb))
            size_mb = p.stat().st_size / (1024 * 1024)
            st.caption(f"{p.name}\n{size_mb:.1f} MB")

st.subheader("Video performance (last 5)")


@st.cache_data(ttl=60)
def fetch_video_stats(video_ids: tuple[str, ...]):
    creds = auth.get_credentials()
    youtube = build("youtube", "v3", credentials=creds)
    resp = youtube.videos().list(part="statistics,snippet", id=",".join(video_ids)).execute()
    return {item["id"]: item for item in resp.get("items", [])}


recent_ids = tuple(r["video_id"] for r in runs if r["status"] == "success" and r["video_id"])[:5]
if not recent_ids:
    st.write("No published videos yet.")
else:
    try:
        stats = fetch_video_stats(recent_ids)
        cols = st.columns(len(recent_ids))
        for i, vid in enumerate(recent_ids):
            item = stats.get(vid)
            with cols[i]:
                st.image(f"https://img.youtube.com/vi/{vid}/hqdefault.jpg")
                st.markdown(f"[{(item['snippet']['title'][:40] if item else vid)}](https://youtu.be/{vid})")
                if item:
                    s = item["statistics"]
                    st.caption(
                        f"{int(s.get('viewCount', 0)):,} views · "
                        f"{int(s.get('likeCount', 0)):,} likes · "
                        f"{int(s.get('commentCount', 0)):,} comments"
                    )
                else:
                    st.caption("Stats unavailable")
    except Exception as e:
        st.warning(f"Could not fetch video stats: {e}")

st.subheader("Run history")
st.dataframe(
    [
        {
            "id": r["id"],
            "source_file": r["source_file"].split("/")[-1],
            "started": datetime.fromtimestamp(r["started_at"]).strftime("%Y-%m-%d %H:%M:%S"),
            "status": r["status"],
            "video_id": r["video_id"] or "",
            "error": r["error"] or "",
        }
        for r in runs
    ],
    use_container_width=True,
)
