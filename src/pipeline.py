"""
pipeline.py — End-to-end orchestrator.

Ties together every stage of the paper-to-podcast pipeline:
  1. Download & parse the arXiv paper.
  2. Convert LaTeX to spoken English.
  3. Generate dialogue via multi-stage LLM calls.
  4. Post-process the raw dialogue.
  5. (Optional) Generate multi-voice audio.

This module is the single entry point used by the Streamlit UI and
can also be run standalone for CLI usage.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Optional

import config
from src.paper_parser import PaperSections, parse_paper
from src.latex_to_speech import replace_latex_placeholders
from src.dialogue_generator import generate_script, FullScript
from src.post_processor import post_process, ProcessedScript
from src.tts_engine import generate_audio

logger = logging.getLogger(__name__)


def _sections_to_dict(paper: PaperSections) -> dict[str, str]:
    """Convert a PaperSections dataclass into a plain dict for the generator."""
    return {
        "abstract": paper.abstract,
        "introduction": paper.introduction,
        "related_work": paper.related_work,
        "methodology": paper.methodology,
        "results": paper.results,
        "discussion": paper.discussion,
        "conclusion": paper.conclusion,
    }


def run_pipeline(
    arxiv_url: str,
    llm_backend: Optional[str] = None,
    tts_engine: Optional[str] = None,
    generate_audio_flag: bool = True,
    output_dir: Optional[Path] = None,
    progress_callback: Optional[Callable[[str, float], None]] = None,
) -> dict:
    """
    Execute the full paper → podcast pipeline.

    Parameters
    ----------
    arxiv_url : str
        arXiv paper URL or ID.
    llm_backend : str
        ``"openai"`` | ``"anthropic"`` | ``"ollama"``.
    tts_engine : str
        ``"edge"`` | ``"coqui"``.
    generate_audio_flag : bool
        Whether to run TTS after generating the script.
    output_dir : Path
        Directory for output files (defaults to ``config.OUTPUT_DIR``).
    progress_callback : callable
        ``callback(stage, fraction)`` for UI progress updates.

    Returns
    -------
    dict with keys:
        "paper"    → PaperSections
        "script"   → ProcessedScript
        "transcript_path" → Path
        "audio_path" → Path | None
    """
    out = output_dir or config.OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)

    def _progress(msg: str, frac: float) -> None:
        logger.info("[%.0f%%] %s", frac * 100, msg)
        if progress_callback:
            progress_callback(msg, frac)

    # ── 1. Parse paper ───────────────────────────────────────
    _progress("Downloading and parsing paper…", 0.0)
    paper = parse_paper(arxiv_url)
    _progress("Paper parsed successfully.", 0.10)

    # ── 2. Convert LaTeX → spoken English ────────────────────
    _progress("Converting maths to spoken English…", 0.12)
    sections = _sections_to_dict(paper)
    for key in sections:
        sections[key] = replace_latex_placeholders(
            sections[key], paper.latex_expressions
        )
    paper.abstract = sections["abstract"]
    _progress("LaTeX conversion complete.", 0.15)

    # ── 3. Generate dialogue ─────────────────────────────────
    def _llm_progress(msg: str, frac: float) -> None:
        # Map the 0-1 range from the generator into the 0.15-0.75 band
        _progress(msg, 0.15 + frac * 0.60)

    raw_script: FullScript = generate_script(
        paper_sections=sections,
        title=paper.title,
        authors=paper.authors,
        backend=llm_backend,
        progress_callback=_llm_progress,
    )

    # ── 4. Post-process ──────────────────────────────────────
    _progress("Post-processing script…", 0.78)
    processed: ProcessedScript = post_process(raw_script)
    _progress("Script polished.", 0.80)

    # Save transcript
    transcript_path = out / "transcript.txt"
    transcript_path.write_text(processed.to_text(), encoding="utf-8")
    _progress("Transcript saved.", 0.82)

    # ── 5. TTS (optional) ────────────────────────────────────
    audio_path: Optional[Path] = None
    if generate_audio_flag:
        def _tts_progress(msg: str, frac: float) -> None:
            _progress(msg, 0.82 + frac * 0.17)

        audio_path = generate_audio(
            script=processed,
            output_path=out / f"podcast.{config.AUDIO_FORMAT}",
            engine=tts_engine,
            progress_callback=_tts_progress,
        )
        _progress("Audio generation complete.", 0.99)

    _progress("Pipeline finished!", 1.0)

    return {
        "paper": paper,
        "script": processed,
        "transcript_path": transcript_path,
        "audio_path": audio_path,
    }
