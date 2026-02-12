"""
app.py — Streamlit interface for the ArXiv-to-Podcast pipeline.

Single-page app with:
  • Text input for arXiv URL / paper ID
  • Sidebar for LLM backend and TTS engine selection
  • Progress bar showing pipeline stages
  • Split view: transcript (left) + audio player (right)
  • Download buttons for transcript and audio
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on the path so imports work
sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

import config
from src.pipeline import run_pipeline


# ─────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────

st.set_page_config(
    page_title="Paper → Podcast",
    page_icon="🎙️",
    layout="wide",
)

# ─────────────────────────────────────────────
# Custom CSS for a cleaner look
# ─────────────────────────────────────────────

st.markdown(
    """
    <style>
    .block-container { max-width: 1200px; padding-top: 2rem; }
    .stProgress > div > div > div > div {
        background-color: #4CAF50;
    }
    h1 { text-align: center; }
    .transcript-box {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 1.5rem;
        font-family: 'Courier New', monospace;
        font-size: 0.85rem;
        line-height: 1.6;
        max-height: 600px;
        overflow-y: auto;
        white-space: pre-wrap;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────
# Sidebar — settings
# ─────────────────────────────────────────────

with st.sidebar:
    st.header("Settings")

    llm_backend = st.selectbox(
        "LLM Backend",
        options=["groq", "ollama", "openai", "anthropic"],
        index=0,
        help=(
            "**Groq** — ultra-fast inference, free tier available. "
            "Set `GROQ_API_KEY` env var.\n\n"
            "**Ollama** — free, runs locally (install Ollama + pull a model first).\n\n"
            "**OpenAI** — requires API key in env var `OPENAI_API_KEY`.\n\n"
            "**Anthropic** — requires API key in env var `ANTHROPIC_API_KEY`."
        ),
    )

    tts_engine = st.selectbox(
        "TTS Engine",
        options=["groq", "edge", "coqui"],
        index=0,
        help=(
            "**Groq TTS** — PlayAI voices via Groq API (fast, high quality, "
            "uses same `GROQ_API_KEY`).\n\n"
            "**edge-tts** — free Microsoft Edge voices (requires internet).\n\n"
            "**Coqui TTS** — fully offline VITS model (slower on CPU)."
        ),
    )

    generate_audio_flag = st.checkbox("Generate audio", value=True)

    st.divider()
    st.caption(
        "All processing happens on your machine when using Ollama + Coqui. "
        "Groq sends text to their API for inference / TTS."
    )

# ─────────────────────────────────────────────
# Main area
# ─────────────────────────────────────────────

st.title("🎙️ Paper → Podcast")
st.markdown(
    "Transform any arXiv paper into an engaging two-host conversational podcast. "
    "Paste a URL or paper ID below and hit **Generate**."
)

arxiv_input = st.text_input(
    "arXiv URL or Paper ID",
    placeholder="e.g. https://arxiv.org/abs/2301.07041  or  2301.07041",
)

generate_btn = st.button("Generate Podcast", type="primary", use_container_width=True)

# ─────────────────────────────────────────────
# Pipeline execution
# ─────────────────────────────────────────────

if generate_btn:
    if not arxiv_input.strip():
        st.error("Please enter an arXiv URL or paper ID.")
        st.stop()

    # Progress UI
    progress_bar = st.progress(0)
    status_text = st.empty()

    def _progress(msg: str, frac: float) -> None:
        progress_bar.progress(min(frac, 1.0))
        status_text.text(msg)

    try:
        result = run_pipeline(
            arxiv_url=arxiv_input.strip(),
            llm_backend=llm_backend,
            tts_engine=tts_engine,
            generate_audio_flag=generate_audio_flag,
            progress_callback=_progress,
        )
    except Exception as exc:
        st.error(f"Pipeline failed: {exc}")
        st.exception(exc)
        st.stop()

    progress_bar.progress(1.0)
    status_text.text("Done!")

    st.success("Podcast generated successfully!")

    # ── Split view: transcript + audio ───────────────────
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.subheader("Transcript")
        transcript_text = result["transcript_path"].read_text(encoding="utf-8")
        st.markdown(
            f'<div class="transcript-box">{transcript_text}</div>',
            unsafe_allow_html=True,
        )
        st.download_button(
            label="Download Transcript",
            data=transcript_text,
            file_name="podcast_transcript.txt",
            mime="text/plain",
        )

    with col_right:
        st.subheader("Audio")
        audio_path = result.get("audio_path")
        if audio_path and audio_path.exists():
            audio_bytes = audio_path.read_bytes()
            st.audio(audio_bytes, format="audio/mp3")
            st.download_button(
                label="Download Audio",
                data=audio_bytes,
                file_name=f"podcast.{config.AUDIO_FORMAT}",
                mime="audio/mpeg",
            )
        else:
            st.info("Audio generation was skipped or not available.")

    # ── Paper metadata ───────────────────────────────────
    with st.expander("Paper details"):
        paper = result["paper"]
        st.markdown(f"**Title:** {paper.title}")
        st.markdown(f"**Authors:** {paper.authors}")
        st.markdown(f"**Summary:** {result['script'].summary}")
