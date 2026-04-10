"""
dialogue_generator.py — Multi-stage dialogue pipeline (Agentic edition).

When AGENTIC_ENABLED=true (default), the pipeline runs through three agents:
  1. PlannerAgent  — decides section depths, episode length, paper type
  2. WriterAgent   — generates dialogue (this module) per section plan
  3. CriticAgent   — reviews each segment, optionally triggers a rewrite
  4. EditorAgent   — injects bridging HOST/EXPERT turns between sections

When AGENTIC_ENABLED=false, the original sequential path is used unchanged.
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
    build_brief_dialogue_messages,
    build_summary_messages,
    build_takeaway_messages,
)
from src.llm_interface import query_llm
from src.page_indexer import PageIndex

logger = logging.getLogger(__name__)


# ── Output data classes ───────────────────────────────────────────────

@dataclass
class DialogueSegment:
    """One section's worth of HOST/EXPERT dialogue."""
    section_title: str
    raw_dialogue: str
    is_bridge: bool = False     # True for EditorAgent bridge turns
    depth: str = "full"         # "full" | "brief" | "bridge"


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
            if not seg.is_bridge:
                parts.append(f"\n\n--- {seg.section_title.upper()} ---\n\n")
            parts.append(seg.raw_dialogue)
        parts.append(self.outro)
        return "\n".join(parts)


# ── Section order ─────────────────────────────────────────────────────

_DIALOGUE_SECTIONS = [
    ("Abstract", "abstract"),
    ("Introduction", "introduction"),
    ("Related Work", "related_work"),
    ("Methodology", "methodology"),
    ("Results", "results"),
    ("Discussion", "discussion"),
    ("Conclusion", "conclusion"),
]


# ── Internal writer helpers ───────────────────────────────────────────

def _retrieve_section_text(
    key: str,
    paper_sections: dict[str, str],
    page_index: Optional[PageIndex],
    progress_callback: Optional[Callable],
    frac: float,
) -> str:
    """Get the best available text for a section (RAG or fallback truncation)."""
    if page_index is not None and page_index.total_blocks() > 0:
        text = page_index.retrieve_for_section(key, top_k=config.RAG_TOP_K)
        if text.strip():
            return text
    return paper_sections.get(key, "")[:config.MAX_SECTION_CHARS]


def _write_segment(
    display_name: str,
    key: str,
    depth: str,
    focus_hint: str,
    turn_count: int,
    section_text: str,
    summary: str,
    backend: Optional[str],
    corrective_hint: str = "",
) -> str:
    """Call the LLM to write a single dialogue segment."""
    if depth == "brief":
        messages = build_brief_dialogue_messages(
            section_title=display_name,
            section_text=section_text,
            paper_summary=summary,
            focus_hint=focus_hint,
        )
    else:
        messages = build_dialogue_messages(
            section_title=display_name,
            section_text=section_text,
            paper_summary=summary,
        )
        # Inject focus_hint and corrective_hint into the last user message
        if focus_hint or corrective_hint:
            extra = []
            if focus_hint:
                extra.append(f"Focus on: {focus_hint}")
            if corrective_hint:
                extra.append(f"Correction needed: {corrective_hint}")
            messages[-1]["content"] += "\n\n" + " ".join(extra)

    return query_llm(messages, backend=backend)


# ── Agentic generate_script ───────────────────────────────────────────

def generate_script(
    paper_sections: dict[str, str],
    title: str,
    authors: str,
    backend: Optional[str] = None,
    progress_callback: Optional[Callable[[str, float], None]] = None,
    page_index: Optional[PageIndex] = None,
) -> tuple[FullScript, dict]:
    """
    Run the full dialogue generation pipeline.

    Returns
    -------
    (FullScript, agent_report)
        agent_report is a dict with keys:
          "podcast_plan"   → PodcastPlan.to_dict() or None
          "critic_reports" → {section_title: CritiqueResult.to_dict()}
    """
    if config.AGENTIC_ENABLED:
        return _agentic_generate(
            paper_sections, title, authors, backend, progress_callback, page_index
        )
    else:
        script = _sequential_generate(
            paper_sections, title, authors, backend, progress_callback, page_index
        )
        return script, {"podcast_plan": None, "critic_reports": {}}


def _agentic_generate(
    paper_sections: dict[str, str],
    title: str,
    authors: str,
    backend: Optional[str],
    progress_callback: Optional[Callable[[str, float], None]],
    page_index: Optional[PageIndex],
) -> tuple[FullScript, dict]:
    """Agentic path: Planner → Writer → Critic → Editor."""

    def _prog(msg: str, frac: float) -> None:
        logger.info("[%.0f%%] %s", frac * 100, msg)
        if progress_callback:
            progress_callback(msg, frac)

    critic_reports: dict[str, dict] = {}

    # ── Stage 0: Summary (always needed for intro/outro) ─────────────
    _prog("Generating paper summary…", 0.03)
    summary_input = "\n\n".join(
        paper_sections.get(k, "")
        for k in ("abstract", "introduction", "conclusion")
        if paper_sections.get(k)
    ) or paper_sections.get("abstract", "No abstract available.")
    summary = query_llm(
        build_summary_messages(summary_input[:config.MAX_SECTION_CHARS * 2]),
        backend=backend,
    )
    _prog("Summary generated.", 0.08)

    # ── Stage 1: Planner ─────────────────────────────────────────────
    _prog("🧠 Planner deciding episode structure…", 0.10)
    from src.agents.planner import PlannerAgent
    planner = PlannerAgent(backend=backend)

    def _planner_prog(msg: str, frac: float) -> None:
        _prog(msg, 0.10 + frac * 0.05)

    plan = planner.plan(paper_sections, title, progress_callback=_planner_prog)
    _prog(
        f"🧠 Plan: {plan.paper_type} · {plan.target_duration} "
        f"(~{plan.target_minutes} min)",
        0.15,
    )

    # ── Stage 2: Writer + Critic per section ─────────────────────────
    from src.agents.critic import CriticAgent
    critic = CriticAgent(backend=backend)

    active = plan.active_sections
    segments: list[DialogueSegment] = []
    section_dialogues: dict[str, str] = {}  # for EditorAgent

    total = len(active)
    for idx, sec_plan in enumerate(active):
        write_frac = 0.15 + 0.65 * (idx / max(total, 1))
        _prog(f"✍️ Writing {sec_plan.display} ({sec_plan.depth})…", write_frac)

        # Retrieve source text
        section_text = _retrieve_section_text(
            sec_plan.key, paper_sections, page_index, None, write_frac
        )

        # Write segment (with optional corrective hint on retry)
        corrective_hint = ""
        dialogue_text = _write_segment(
            display_name=sec_plan.display,
            key=sec_plan.key,
            depth=sec_plan.depth,
            focus_hint=sec_plan.focus_hint,
            turn_count=sec_plan.turn_count,
            section_text=section_text,
            summary=summary,
            backend=backend,
            corrective_hint=corrective_hint,
        )

        # Critic review
        critique_frac = write_frac + 0.65 / max(total * 2, 1)
        _prog(f"🔍 Critic reviewing {sec_plan.display}…", critique_frac)
        critique = critic.critique(
            section_title=sec_plan.display,
            source_text=section_text,
            dialogue=dialogue_text,
        )

        # Retry if critic failed (max once)
        for retry in range(config.CRITIC_MAX_RETRIES):
            if critique.passed:
                break
            _prog(
                f"🔄 Rewriting {sec_plan.display} (Critic flagged: "
                f"{'; '.join(critique.issues[:2])})…",
                critique_frac,
            )
            dialogue_text = _write_segment(
                display_name=sec_plan.display,
                key=sec_plan.key,
                depth=sec_plan.depth,
                focus_hint=sec_plan.focus_hint,
                turn_count=sec_plan.turn_count,
                section_text=section_text,
                summary=summary,
                backend=backend,
                corrective_hint=critique.suggestions,
            )
            critique = critic.critique(
                section_title=sec_plan.display,
                source_text=section_text,
                dialogue=dialogue_text,
            )
            critique.regenerated = True

        critique_dict = critique.to_dict()
        critic_reports[sec_plan.display] = critique_dict

        section_dialogues[sec_plan.key] = dialogue_text
        segments.append(DialogueSegment(
            section_title=sec_plan.display,
            raw_dialogue=dialogue_text,
            depth=sec_plan.depth,
        ))

    _prog("All sections written and reviewed.", 0.82)

    # ── Stage 3: Editor (bridging turns) ─────────────────────────────
    _prog("✏️ Editor generating narrative bridges…", 0.84)
    from src.agents.editor import EditorAgent
    editor = EditorAgent(backend=backend)
    bridges = editor.edit(
        sections_in_order=[(s.key, s.display) for s in active],
        section_dialogues=section_dialogues,
        paper_summary=summary,
    )

    # Insert bridge segments between section segments
    if bridges:
        new_segments: list[DialogueSegment] = []
        for i, seg in enumerate(segments):
            new_segments.append(seg)
            if i < len(segments) - 1:
                next_seg = segments[i + 1]
                bridge_key = (
                    f"{active[i].key}→{active[i + 1].key}"
                )
                bridge_text = bridges.get(bridge_key, "")
                if bridge_text:
                    new_segments.append(DialogueSegment(
                        section_title=f"Bridge: {seg.section_title} → {next_seg.section_title}",
                        raw_dialogue=bridge_text,
                        is_bridge=True,
                        depth="bridge",
                    ))
        segments = new_segments
        _prog(f"✏️ Inserted {len(bridges)} narrative bridges.", 0.88)

    # ── Stage 4: Outro takeaway ───────────────────────────────────────
    _prog("Generating closing takeaway…", 0.90)
    takeaway = query_llm(build_takeaway_messages(summary), backend=backend)

    # ── Stage 5: Assemble ─────────────────────────────────────────────
    _prog("Assembling final script…", 0.95)
    authors_short = authors
    if len(authors) > 120:
        authors_short = f"{authors.split(',')[0].strip()} and colleagues"

    intro = INTRO_TEMPLATE.format(
        title=title, authors=authors_short, summary=summary
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

    _prog("Script complete!", 1.0)

    agent_report = {
        "podcast_plan": plan.to_dict(),
        "critic_reports": critic_reports,
    }

    return script, agent_report


def _sequential_generate(
    paper_sections: dict[str, str],
    title: str,
    authors: str,
    backend: Optional[str],
    progress_callback: Optional[Callable[[str, float], None]],
    page_index: Optional[PageIndex],
) -> FullScript:
    """Original sequential path (used when AGENTIC_ENABLED=false)."""

    def _prog(msg: str, frac: float) -> None:
        logger.info("[%.0f%%] %s", frac * 100, msg)
        if progress_callback:
            progress_callback(msg, frac)

    _prog("Generating paper summary…", 0.05)
    summary_input = "\n\n".join(
        paper_sections.get(k, "")
        for k in ("abstract", "introduction", "conclusion")
        if paper_sections.get(k)
    ) or paper_sections.get("abstract", "No abstract available.")
    summary = query_llm(
        build_summary_messages(summary_input[:config.MAX_SECTION_CHARS * 2]),
        backend=backend,
    )
    _prog("Summary generated.", 0.15)

    segments: list[DialogueSegment] = []
    non_empty = [
        (d, k)
        for d, k in _DIALOGUE_SECTIONS
        if paper_sections.get(k, "").strip()
    ]
    total = len(non_empty)

    for idx, (display_name, key) in enumerate(non_empty):
        frac = 0.15 + 0.70 * (idx / max(total, 1))
        _prog(f"Generating dialogue for {display_name}…", frac)

        section_text = _retrieve_section_text(key, paper_sections, page_index, None, frac)
        messages = build_dialogue_messages(display_name, section_text, summary)
        dialogue_text = query_llm(messages, backend=backend)
        segments.append(DialogueSegment(section_title=display_name, raw_dialogue=dialogue_text))

    _prog("All section dialogues generated.", 0.85)

    _prog("Generating closing takeaway…", 0.90)
    takeaway = query_llm(build_takeaway_messages(summary), backend=backend)

    _prog("Assembling final script…", 0.95)
    authors_short = authors
    if len(authors) > 120:
        authors_short = f"{authors.split(',')[0].strip()} and colleagues"

    intro = INTRO_TEMPLATE.format(title=title, authors=authors_short, summary=summary)
    outro = OUTRO_TEMPLATE.format(takeaway=takeaway)

    script = FullScript(
        title=title,
        authors=authors,
        summary=summary,
        segments=segments,
        intro=intro,
        outro=outro,
    )
    _prog("Script complete!", 1.0)
    return script
