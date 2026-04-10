"""
editor.py — EditorAgent: injects bridging HOST/EXPERT turns between sections.

After all section dialogues are written and reviewed, the EditorAgent reads
the entire assembled script and generates short (2-turn) HOST/EXPERT bridges
that are inserted between consecutive "full" sections.

Why standalone turns (not text patches)?
  - Adds real podcast content — the Host pivots, the Expert teases what's next
  - Preserves TTS compatibility (HOST:/EXPERT: labels work with existing engine)
  - Results in a more natural, produced-feeling episode flow
  - A simple text patch would just be cosmetic; bridging turns are substantive

Example bridge between Methodology → Results:
  HOST: So now that we understand the model architecture, I'm curious — does
        it actually work in practice?
  EXPERT: That's exactly the right question, and the results here honestly
          surprised even us.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional, Callable

import config

logger = logging.getLogger(__name__)


class EditorAgent:
    """
    Generates narrative bridge turns between major podcast sections.

    Operates on the complete assembled FullScript, producing a dict of
    bridge dialogues keyed by ``(from_section, to_section)`` tuples.
    These are inserted by ``dialogue_generator`` as short DialogueSegments
    of type ``"bridge"``.
    """

    def __init__(self, backend: Optional[str] = None):
        self.backend = backend

    def edit(
        self,
        sections_in_order: list[tuple[str, str]],  # [(key, display), ...]
        section_dialogues: dict[str, str],          # key → raw dialogue text
        paper_summary: str,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> dict[str, str]:
        """
        Generate bridging HOST/EXPERT turns between sections.

        Parameters
        ----------
        sections_in_order : list of (key, display) for every ACTIVE section
            in the order they appear in the episode.
        section_dialogues : dict mapping section key → its raw dialogue text.
        paper_summary : str
            Paper summary (used as context so bridges are coherent).
        progress_callback : callable, optional

        Returns
        -------
        dict mapping ``"<from_key>→<to_key>"`` → bridge dialogue string.
        Caller inserts each bridge DialogueSegment between its two neighbours.
        """
        if not config.EDITOR_ENABLED or len(sections_in_order) < 2:
            return {}

        def _prog(msg: str, frac: float) -> None:
            logger.info("[Editor %.0f%%] %s", frac * 100, msg)
            if progress_callback:
                progress_callback(msg, frac)

        _prog("✏️ Editor generating narrative bridges…", 0.0)

        from prompts.templates import build_editor_messages
        from src.llm_interface import query_llm

        # Build a compact section summary list for the editor prompt
        section_summary_lines = []
        for key, display in sections_in_order:
            # Give the editor just the last 200 chars of each section dialogue
            # so it knows what was just said before bridging to the next
            tail = section_dialogues.get(key, "")[-200:].strip()
            section_summary_lines.append(f"{display}: ...{tail}")

        messages = build_editor_messages(
            paper_summary=paper_summary,
            section_sequence=[display for _, display in sections_in_order],
            section_tails=section_summary_lines,
        )

        try:
            raw = query_llm(
                messages,
                backend=self.backend,
                temperature=0.5,   # slight creativity for natural-sounding bridges
                max_tokens=1500,
            )
            bridges = self._parse_bridges(raw, sections_in_order)
            _prog(f"✏️ Editor: {len(bridges)} bridges generated.", 1.0)
            return bridges

        except Exception as exc:
            logger.warning("EditorAgent failed (%s) — skipping bridges.", exc)
            _prog("⚠️ Editor skipped (will not affect output quality).", 1.0)
            return {}

    # ── Parsing ───────────────────────────────────────────────────────

    def _parse_bridges(
        self,
        raw: str,
        sections_in_order: list[tuple[str, str]],
    ) -> dict[str, str]:
        """Parse the LLM's JSON bridge output into a keyed dict."""
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text.strip())

        data = json.loads(text)
        bridges_raw = data.get("bridges", [])

        result: dict[str, str] = {}

        for bridge in bridges_raw:
            from_sec = bridge.get("from_section", "").lower().replace(" ", "_")
            to_sec = bridge.get("to_section", "").lower().replace(" ", "_")
            dialogue = bridge.get("dialogue", "").strip()

            if not dialogue:
                continue

            # Validate that both sections are actually in our plan
            known_keys = {k for k, _ in sections_in_order}
            if from_sec not in known_keys or to_sec not in known_keys:
                logger.debug("Editor bridge skipped (unknown sections): %s → %s", from_sec, to_sec)
                continue

            bridge_key = f"{from_sec}→{to_sec}"
            result[bridge_key] = dialogue

        return result
