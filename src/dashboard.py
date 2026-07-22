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
    "extract_audio": "Extract audio from video file",
    "transcribe": "Transcribe speech via Gemini AI",
    "upload_and_generate_metadata": "Upload video & generate AI metadata concurrently",
    "update_metadata": "Update YouTube video title, description & tags",
    "wait_processing": "Wait for YouTube video processing",
    "publish": "Publish video to YouTube (make public)",
}

st.set_page_config(
    page_title="YouTube AI Upload Automation",
    page_icon=":material/smart_display:",
    layout="wide",
)

db.init_db()
skills_text = nim_client.load_skills()


def fetch_runs():
    with db.connect() as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("SELECT * FROM runs ORDER BY started_at DESC").fetchall()


def _thumbnail_for(video_path: Path) -> Path | None:
    thumb_path = config.WORK_DIR / f"{video_path.stem}_thumb.jpg"
    if thumb_path.exists() and thumb_path.stat().st_mtime >= video_path.stat().st_mtime:
        return thumb_path
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-ss", "1", "-i", str(video_path), "-frames:v", "1", str(thumb_path)],
            check=True,
            capture_output=True,
        )
        return thumb_path
    except Exception:
        return None


@st.cache_data(ttl=60)
def fetch_video_stats(video_ids: tuple[str, ...]):
    creds = auth.get_credentials()
    youtube = build("youtube", "v3", credentials=creds)
    resp = youtube.videos().list(part="statistics,snippet", id=",".join(video_ids)).execute()
    return {item["id"]: item for item in resp.get("items", [])}


# --- Header Section ---
st.title("YouTube AI upload automation", anchor=False)
st.caption("Automated video processing pipeline: audio extraction, Gemini transcription, NIM AI copywriting, and YouTube publishing.")

if url := st.session_state.get("last_uploaded_url"):
    st.toast("Video published successfully!", icon=":material/check_circle:")
    st.success(f"Video uploaded & published: [Watch on YouTube]({url})", icon=":material/open_in_new:")

# --- Overview Metrics Row ---
runs = fetch_runs()
total = len(runs)
successes = sum(1 for r in runs if r["status"] == "success")
failures = sum(1 for r in runs if r["status"] == "failed")
success_rate = f"{(successes / total * 100):.0f}%" if total else "N/A"

with st.container(horizontal=True):
    st.metric("Total runs", total, border=True)
    st.metric("Successful uploads", successes, border=True)
    st.metric("Failed runs", failures, border=True)
    st.metric("Success rate", success_rate, border=True)

st.space("medium")

# --- Tabbed Main Interface ---
tab_queue, tab_videos, tab_history, tab_skills = st.tabs([
    ":material/play_circle: Pipeline control & queue",
    ":material/video_library: Published videos & analytics",
    ":material/history: Run history",
    ":material/psychology: AI skills & status",
])

# --- TAB 1: Pipeline Control & Queue ---
with tab_queue:
    c_action, c_info = st.columns([1, 2])
    with c_action:
        run_clicked = st.button("Run pipeline now", type="primary", icon=":material/play_arrow:")

    if run_clicked:
        stage_keys = list(STAGE_LABELS)
        with st.status("Executing YouTube upload pipeline...", expanded=True) as status_box:
            step_rows = {key: st.empty() for key in stage_keys}
            for key in stage_keys:
                step_rows[key].markdown(f":material/pending: **{STAGE_LABELS[key]}**")

            def on_progress(stage, event):
                label = STAGE_LABELS.get(stage, stage)
                if event == "started":
                    step_rows[stage].markdown(f":material/sync: **{label}** *(in progress...)*")
                else:
                    step_rows[stage].markdown(f":material/check_circle: **{label}** *(completed)*")

            processed = pipeline.run_once(on_progress=on_progress)
            if processed:
                status_box.update(label="Pipeline execution completed successfully!", state="complete", expanded=False)
                latest = fetch_runs()[0]
                if latest["status"] == "success" and latest["video_id"]:
                    st.session_state["last_uploaded_url"] = f"https://youtu.be/{latest['video_id']}"
            else:
                status_box.update(label="No videos waiting in queue.", state="complete", expanded=False)
                st.info("No video files found in incoming directory.", icon=":material/info:")
            st.rerun()

    st.subheader("Pending video queue", anchor=False)
    pending_files = sorted(
        (p for p in config.SOURCE_DIR.iterdir() if p.suffix.lower() in pipeline.VIDEO_EXTENSIONS),
        key=lambda p: p.stat().st_mtime,
    )

    if not pending_files:
        st.caption(":material/inbox: No videos queued in source folder (`incoming/`). Drop video files (`.mp4`, `.mov`, `.mkv`) to process.")
    else:
        cols = st.columns(min(len(pending_files), 4))
        for i, p in enumerate(pending_files):
            with cols[i % 4]:
                with st.container(border=True):
                    thumb = _thumbnail_for(p)
                    if thumb:
                        st.image(str(thumb))
                    st.markdown(f"**{p.name}**")
                    size_mb = p.stat().st_size / (1024 * 1024)
                    st.badge("Ready to process", icon=":material/schedule:", color="orange")
                    st.caption(f"Size: {size_mb:.1f} MB")

# --- TAB 2: Published Videos & Analytics ---
with tab_videos:
    st.subheader("Published videos", anchor=False)
    published = [r for r in runs if r["status"] == "success" and r["video_id"]][:8]
    if not published:
        st.caption(":material/video_library: No published videos recorded yet.")
    else:
        recent_ids = tuple(r["video_id"] for r in published[:5])
        stats = {}
        try:
            stats = fetch_video_stats(recent_ids)
        except Exception as e:
            st.caption(f"Analytics feed unavailable: {e}")

        cols = st.columns(min(len(published), 4))
        for i, r in enumerate(published):
            vid = r["video_id"]
            item = stats.get(vid)
            with cols[i % 4]:
                with st.container(border=True):
                    st.image(f"https://img.youtube.com/vi/{vid}/hqdefault.jpg")
                    title_text = item["snippet"]["title"] if item else r["source_file"].split("/")[-1]
                    st.markdown(f"**{title_text[:45]}**")
                    st.link_button("Watch on YouTube", f"https://youtu.be/{vid}", icon=":material/open_in_new:")
                    if item:
                        s = item["statistics"]
                        st.caption(
                            f":material/visibility: {int(s.get('viewCount', 0)):,} views  ·  "
                            f":material/thumb_up: {int(s.get('likeCount', 0)):,}  ·  "
                            f":material/comment: {int(s.get('commentCount', 0)):,}"
                        )
                    else:
                        st.caption(f"Uploaded: {datetime.fromtimestamp(r['started_at']).strftime('%Y-%m-%d %H:%M')}")

# --- TAB 3: Run History ---
with tab_history:
    st.subheader("Execution history", anchor=False)
    if not runs:
        st.caption(":material/history: No execution history available.")
    else:
        filter_status = st.segmented_control(
            "Filter by status",
            options=["All", "Success", "Failed"],
            default="All",
        )

        filtered_runs = runs
        if filter_status == "Success":
            filtered_runs = [r for r in runs if r["status"] == "success"]
        elif filter_status == "Failed":
            filtered_runs = [r for r in runs if r["status"] == "failed"]

        st.dataframe(
            [
                {
                    "ID": r["id"],
                    "Source file": r["source_file"].split("/")[-1],
                    "Started at": datetime.fromtimestamp(r["started_at"]).strftime("%Y-%m-%d %H:%M:%S"),
                    "Status": "✅ Success" if r["status"] == "success" else "❌ Failed",
                    "YouTube Video ID": r["video_id"] or "-",
                    "Error details": r["error"] or "-",
                }
                for r in filtered_runs
            ],
            hide_index=True,
        )

# --- TAB 4: AI Skills & System Status ---
with tab_skills:
    st.subheader("Loaded AI skills", anchor=False)
    with st.container(border=True):
        st.markdown("**NIM Copywriting Skill (Humanizer)**")
        st.caption("Active rule guidelines loaded into DeepSeek / NIM client system prompts:")
        if skills_text:
            st.text_area("Skill instructions", value=skills_text[:3000] + ("\n..." if len(skills_text) > 3000 else ""), height=250, disabled=True)
        else:
            st.warning("No skill files found in `src/skills/` directory.", icon=":material/warning:")

    st.subheader("System directory layout", anchor=False)
    with st.container(border=True):
        st.markdown(f"- **Incoming folder:** `{config.SOURCE_DIR}`")
        st.markdown(f"- **Uploaded folder:** `{config.UPLOADED_DIR}`")
        st.markdown(f"- **Working directory:** `{config.WORK_DIR}`")
        st.markdown(f"- **Database path:** `{config.DB_PATH}`")
        st.markdown(f"- **Skills folder:** `{config.SKILLS_DIR}`")
