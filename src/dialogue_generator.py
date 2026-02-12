"""
dialogue_generator.py — Multi-stage dialogue pipeline.

Orchestrates the conversion of structured paper sections into a
full podcast script by:
  1. Generating a plain-English summary of the paper.
  2. Generating a dialogue segment for each non-empty section.
  3. Wrapping everything with an intro and outro.

Each stage is a separate LLM call, keeping prompts focused and
improving output quality compared to a single monolithic prompt.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

import config
from prompts.templates import (
    INTRO_TEMPLATE,
    OUTRO_TEMPLATE,
    build_dialogue_messages,
    build_summary_messages,
    build_takeaway_messages,
)
from src.llm_interface import query_llm

logger = logging.getLogger(__name__)


@dataclass
class DialogueSegment:
    """One section's worth of HOST/EXPERT dialogue."""
    section_title: str
    raw_dialogue: str


@dataclass
class FullScript:
    """The complete podcast script assembled from all stages."""
    title: str
    authors: str
    summary: str
    segments: list[DialogueSegment] = field(default_factory=list)
    intro: str = ""
    outro: str = ""

    @property
    def full_text(self) -> str:
        """Concatenate intro + segments + outro into a single script."""
        parts = [self.intro]
        for seg in self.segments:
            parts.append(f"\n\n--- {seg.section_title.upper()} ---\n\n")
            parts.append(seg.raw_dialogue)
        parts.append(self.outro)
        return "\n".join(parts)


# ─────────────────────────────────────────────
# Section maps (title → text) we'll iterate
# ─────────────────────────────────────────────

_DIALOGUE_SECTIONS = [
    ("Abstract", "abstract"),
    ("Introduction", "introduction"),
    ("Methodology", "methodology"),
    ("Results", "results"),
    ("Discussion", "discussion"),
    ("Conclusion", "conclusion"),
]


def generate_script(
    paper_sections: dict[str, str],
    title: str,
    authors: str,
    backend: Optional[str] = None,
    progress_callback: Optional[Callable[[str, float], None]] = None,
) -> FullScript:
    """
    Run the full multi-stage dialogue generation pipeline.

    Parameters
    ----------
    paper_sections : dict[str, str]
        Mapping of section key → cleaned text (already LaTeX-free).
    title : str
        Paper title.
    authors : str
        Author string.
    backend : str, optional
        LLM backend override.
    progress_callback : callable, optional
        ``callback(stage_description, fraction_done)`` for UI updates.

    Returns
    -------
    FullScript
    """
    def _progress(msg: str, frac: float) -> None:
        logger.info("[%.0f%%] %s", frac * 100, msg)
        if progress_callback:
            progress_callback(msg, frac)

    # ── Stage 1: Generate paper summary ──────────────────────
    _progress("Generating paper summary…", 0.05)

    # Build a combined text block for the summary (abstract + intro + conclusion)
    summary_input = "\n\n".join(
        paper_sections.get(k, "")
        for k in ("abstract", "introduction", "conclusion")
        if paper_sections.get(k)
    )
    if not summary_input:
        summary_input = paper_sections.get("abstract", "No abstract available.")

    # Truncate if very long
    summary_input = summary_input[: config.MAX_SECTION_CHARS * 2]

    summary_messages = build_summary_messages(summary_input)
    summary = query_llm(summary_messages, backend=backend)

    _progress("Summary generated.", 0.15)

    # ── Stage 2: Generate per-section dialogue ───────────────
    segments: list[DialogueSegment] = []
    non_empty_sections = [
        (display, key)
        for display, key in _DIALOGUE_SECTIONS
        if paper_sections.get(key, "").strip()
    ]
    total = len(non_empty_sections)

    for idx, (display_name, key) in enumerate(non_empty_sections):
        frac = 0.15 + 0.70 * (idx / max(total, 1))
        _progress(f"Generating dialogue for {display_name}…", frac)

        section_text = paper_sections[key][: config.MAX_SECTION_CHARS]
        messages = build_dialogue_messages(display_name, section_text, summary)
        dialogue_text = query_llm(messages, backend=backend)

        segments.append(
            DialogueSegment(section_title=display_name, raw_dialogue=dialogue_text)
        )

    _progress("All section dialogues generated.", 0.85)

    # ── Stage 3: Generate outro takeaway ─────────────────────
    _progress("Generating closing takeaway…", 0.90)
    takeaway_messages = build_takeaway_messages(summary)
    takeaway = query_llm(takeaway_messages, backend=backend)

    # ── Stage 4: Assemble full script ────────────────────────
    _progress("Assembling final script…", 0.95)

    # Truncate author list for a friendlier intro
    authors_short = authors
    if len(authors) > 120:
        first_author = authors.split(",")[0].strip()
        authors_short = f"{first_author} and colleagues"

    intro = INTRO_TEMPLATE.format(
        title=title,
        authors=authors_short,
        summary=summary,
    )
    outro = OUTRO_TEMPLATE.format(takeaway=takeaway)

    script = FullScript(
        title=title,
        authors=authors,
        summary=summary,
        segments=segments,
        intro=intro,
        outro=outro,
    )

    _progress("Script complete!", 1.0)
    return script
