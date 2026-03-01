"""
app.py — Streamlit Review UI & Orchestrator for the Faceless Video Pipeline.

Run with:  streamlit run app.py

Features
--------
* Enter video script text and a Pexels search keyword.
* Generate TTS audio → fetch background video → render final MP4.
* Preview the finished video in the browser.
* Approve & upload to YouTube / TikTok with one click.
* Regenerate background (keeps audio, re-fetches + re-renders).
* Discard and start over.
* Account setup panel to log into YouTube / TikTok once.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Force the project root into sys.path to ensure local imports always work
_ROOT = str(Path(__file__).resolve().parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import nest_asyncio
import streamlit as st

# Apply nest_asyncio so sync Playwright can run within Streamlit's event loop.
nest_asyncio.apply()

from config import FINAL_DIR, AUDIO_DIR, VIDEO_DIR, VIDEO_CATEGORIES
from tts_engine import generate_audio
from video_fetcher import get_clips_for_script, get_background_video
from video_engine import render_final_video
from uploader import upload_video, manual_login
from reddit_fetcher import get_reddit_story

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
#  Page configuration
# ═══════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Faceless Video Pipeline",
    page_icon="🎬",
    layout="centered",
)


# ═══════════════════════════════════════════════════════════════════════════
#  Session state defaults
# ═══════════════════════════════════════════════════════════════════════════

_DEFAULTS = {
    "final_video_path": None,
    "audio_path": None,
    "audio_duration": None,
    "subtitles_path": None,
    "video_path": None,
    "generating": False,
    "upload_youtube": True,
    "upload_tiktok": True,
    # BUG FIX: Persist the keyword and title/description so they survive
    # a st.rerun() after "Regenerate BG" — without this the form fields
    # reset to empty and the regen uses "nature" as a fallback.
    "last_keyword": "",
    "last_title": "",
    "last_description": "",
    "last_script": "",
    "seen_reddit_ids": set(),
}

for key, val in _DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = val


# ═══════════════════════════════════════════════════════════════════════════
#  Sidebar — Account Setup
# ═══════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.header("⚙️ Account Setup")
    st.caption(
        "Log into each platform **once** so the app can upload automatically. "
        "Cookies are saved locally — you won't need to log in again."
    )

    col_yt, col_tt = st.columns(2)
    with col_yt:
        if st.button("🔑 Login YouTube", use_container_width=True):
            with st.spinner("Opening browser — log in manually…"):
                try:
                    manual_login("youtube")
                    st.success("YouTube session saved ✓")
                except Exception as exc:
                    st.error(f"Error: {exc}")

    with col_tt:
        if st.button("🔑 Login TikTok", use_container_width=True):
            with st.spinner("Opening browser — log in manually…"):
                try:
                    manual_login("tiktok")
                    st.success("TikTok session saved ✓")
                except Exception as exc:
                    st.error(f"Error: {exc}")

    st.divider()
    st.subheader("Upload Targets")
    st.session_state.upload_youtube = st.checkbox(
        "YouTube Shorts", value=st.session_state.upload_youtube
    )
    st.session_state.upload_tiktok = st.checkbox(
        "TikTok", value=st.session_state.upload_tiktok
    )

    st.divider()
    st.subheader("🧹 Maintenance")
    if st.button("🗑️ Clear Cache", use_container_width=True, help="Delete all temporary audio and video files"):
        count = 0
        for directory in (AUDIO_DIR, VIDEO_DIR, FINAL_DIR):
            if directory.exists():
                for f in directory.iterdir():
                    if f.is_file():
                        try:
                            f.unlink()
                            count += 1
                        except Exception:
                            pass
        st.toast(f"Cleared {count} files.")
        st.rerun()

    st.divider()
    st.subheader("🔑 API Keys")
    st.caption(
        "Set your API keys in the `.env` file (see `.env.example`)."
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Main UI
# ═══════════════════════════════════════════════════════════════════════════

st.title("🎬 Faceless Video Pipeline")
st.write("Generate, review, and upload AI videos to YouTube Shorts & TikTok.")

# ── Reddit Content Sourcing ──────────────────────────────────────────────

with st.expander("🤖 Source Content from Reddit"):
    col_red1, col_red2 = st.columns([2, 1])
    with col_red1:
        reddit_category = st.selectbox(
            "Select Story Category",
            ["Interesting", "Funny", "Scary", "Drama", "Tales", "Entitled", "Revenge"],
            index=0
        )
    with col_red2:
        if st.button("🔍 Fetch Story", use_container_width=True):
            with st.spinner("Fetching from Reddit..."):
                story = get_reddit_story(
                    reddit_category,
                    seen_ids=st.session_state.seen_reddit_ids
                )
                if story:
                    st.session_state["reddit_story"] = story
                    st.session_state.seen_reddit_ids.add(story["id"])
                    st.success(f"Fetched: {story['title']}")
                else:
                    st.error("Could not fetch a suitable story. Check credentials or filters.")

    if "reddit_story" in st.session_state:
        story = st.session_state["reddit_story"]
        if st.button("📝 Use this Story", use_container_width=True):
            # Update the underlying session state values
            st.session_state.last_script = story["text"]
            st.session_state.last_title = story["title"]
            st.session_state.last_description = f"Story from r/{story['subreddit']}\n#shorts #reddit"
            st.session_state.last_keyword = reddit_category.lower()

            # CRITICAL: Also update the widget keys directly so the form
            # reflects the changes even if the user has already typed.
            st.session_state.f_script = st.session_state.last_script
            st.session_state.f_title = st.session_state.last_title
            st.session_state.f_desc = st.session_state.last_description
            st.session_state.f_keyword = st.session_state.last_keyword

            # We use st.rerun() to populate the form fields in the next run
            st.rerun()

# ── Input form ───────────────────────────────────────────────────────────

with st.form("video_form"):
    script_text = st.text_area(
        "📝 Video Script",
        height=180,
        placeholder="Paste your narration script here…",
        value=st.session_state.last_script,
        key="f_script"
    )
    col_k1, col_k2 = st.columns([1, 1])
    with col_k1:
        keyword = st.text_input(
            "🔍 Pexels Keyword",
            placeholder='e.g. "ocean waves", "city night"',
            value=st.session_state.last_keyword,
            key="f_keyword"
        )
    with col_k2:
        bg_style = st.selectbox(
            "🎥 Background Style",
            ["Dynamic Pexels"] + list(VIDEO_CATEGORIES.keys()),
            index=0,
            help="Choose between dynamic stock footage or high-engagement gameplay."
        )

    video_title = st.text_input(
        "🏷️ Video Title",
        placeholder="Title for YouTube / TikTok",
        value=st.session_state.last_title,
        key="f_title"
    )
    video_description = st.text_area(
        "📄 Video Description",
        height=80,
        placeholder="Short description / hashtags",
        value=st.session_state.last_description,
        key="f_desc"
    )
    generate_btn = st.form_submit_button(
        "🚀 Generate Video", use_container_width=True
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Generate pipeline
# ═══════════════════════════════════════════════════════════════════════════

def _run_generate(script: str, kw: str, bg_style: str = "Dynamic Pexels") -> None:
    """Run the full TTS → fetch segments → stitch → render pipeline."""
    progress = st.progress(0, text="Starting…")

    # Step 1 — TTS
    progress.progress(10, text="🎙️ Generating audio and timing…")
    st.toast("Generating AI narration...")
    audio_path, duration, subtitles_path = generate_audio(script)
    st.session_state.audio_path = audio_path
    st.session_state.audio_duration = duration
    st.session_state.subtitles_path = subtitles_path

    # Step 2 — Fetch relevant clips for script segments
    progress.progress(30, text="🎥 Analyzing script and fetching relevant clips…")
    st.toast("Fetching background visuals...")

    use_local = bg_style != "Dynamic Pexels"
    # If local, kw is actually the category key
    search_kw = kw if not use_local else VIDEO_CATEGORIES.get(bg_style, "nature")

    clips_metadata = get_clips_for_script(
        script, duration, base_keyword=search_kw, use_local_backgrounds=use_local
    )
    st.session_state.video_path = clips_metadata  # Store the list of clips

    # Step 3 — Render
    progress.progress(70, text="🔧 Stitching and rendering final video with subtitles…")
    st.toast("Merging audio and video...")
    final_path = render_final_video(
        audio_path, clips_metadata, subtitles_path=subtitles_path
    )
    st.session_state.final_video_path = final_path

    progress.progress(100, text="✅ Video connected to story!")
    st.balloons()


if generate_btn:
    # Read from keys to be extra sure they match current state
    script_text = st.session_state.get("f_script", "").strip()
    keyword = st.session_state.get("f_keyword", "").strip()
    video_title = st.session_state.get("f_title", "").strip()
    video_description = st.session_state.get("f_desc", "").strip()

    if not script_text:
        st.warning("Please enter a script.")
    elif not keyword and bg_style == "Dynamic Pexels":
        st.warning("Please enter a background keyword.")
    else:
        # BUG FIX: Persist form values before running pipeline so they
        # survive st.rerun(). Without this, clicking "Regenerate BG"
        # after a rerun loses the keyword/title/description.
        st.session_state.last_keyword = keyword
        st.session_state.last_title = video_title
        st.session_state.last_description = video_description
        st.session_state.last_script = script_text

        try:
            _run_generate(script_text.strip(), keyword.strip(), bg_style=bg_style)
        except Exception as exc:
            st.error(f"❌ Pipeline error: {exc}")


# ═══════════════════════════════════════════════════════════════════════════
#  Preview & Actions
# ═══════════════════════════════════════════════════════════════════════════

if st.session_state.final_video_path and Path(st.session_state.final_video_path).exists():
    st.divider()
    st.subheader("📺 Preview")
    st.video(st.session_state.final_video_path)

    st.write("")  # spacing

    col1, col2, col3 = st.columns(3)

    # ── Approve & Upload ─────────────────────────────────────────────
    with col1:
        if st.button("✅ Approve & Upload", use_container_width=True, type="primary"):
            platforms = []
            if st.session_state.upload_youtube:
                platforms.append("youtube")
            if st.session_state.upload_tiktok:
                platforms.append("tiktok")

            if not platforms:
                st.warning("Select at least one upload target in the sidebar.")
            else:
                # BUG FIX: Use persisted session values — the form variables
                # (video_title, video_description) are empty on a rerun
                # because Streamlit re-executes the form with no user input.
                title = st.session_state.last_title or "Untitled Video"
                desc = st.session_state.last_description or ""

                with st.spinner(f"Uploading to {', '.join(p.title() for p in platforms)}…"):
                    try:
                        results = upload_video(
                            st.session_state.final_video_path,
                            title,
                            desc,
                            platforms=platforms,
                        )
                        for platform, ok in results.items():
                            if ok:
                                st.success(f"✅ {platform.title()} upload succeeded!")
                                st.snow()
                            else:
                                st.error(
                                    f"❌ {platform.title()} upload failed. "
                                    "Check the terminal for details."
                                )
                    except FileNotFoundError as exc:
                        st.error(f"❌ {exc}")

    # ── Regenerate Background ────────────────────────────────────────
    with col2:
        if st.button("🔄 Regenerate BG", use_container_width=True):
            if st.session_state.audio_path and st.session_state.audio_duration:
                try:
                    with st.spinner("Analyzing script and fetching new clips…"):
                        # Use the persisted script for semantic regeneration
                        script = st.session_state.last_script or "nature"
                        keyword = st.session_state.last_keyword or "nature"
                        new_clips = get_clips_for_script(
                            script, st.session_state.audio_duration, base_keyword=keyword
                        )
                        st.session_state.video_path = new_clips

                        final_path = render_final_video(
                            st.session_state.audio_path,
                            new_clips,
                            subtitles_path=st.session_state.subtitles_path,
                        )
                        st.session_state.final_video_path = final_path
                    st.rerun()
                except Exception as exc:
                    st.error(f"Regeneration failed: {exc}")
            else:
                st.warning("No audio to regenerate with. Generate first.")

    # ── Discard ──────────────────────────────────────────────────────
    with col3:
        if st.button("❌ Discard", use_container_width=True):
            # Clean up generated files
            for directory in (AUDIO_DIR, VIDEO_DIR, FINAL_DIR):
                if directory.exists():
                    for f in directory.iterdir():
                        # BUG FIX: Only delete files, not subdirectories.
                        if f.is_file():
                            try:
                                f.unlink()
                            except Exception:
                                pass

            # Reset session
            for key in _DEFAULTS:
                st.session_state[key] = _DEFAULTS[key]
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
#  Footer
# ═══════════════════════════════════════════════════════════════════════════

st.divider()
st.caption(
    "Faceless Video Pipeline · Built with edge-tts, Pexels, moviepy, "
    "Playwright & Streamlit"
)

