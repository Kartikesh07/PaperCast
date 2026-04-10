"""
planner.py — PlannerAgent: decides podcast structure before any writing.

Reads only the lightest sections (abstract + intro + conclusion) with a single,
deterministic LLM call, then returns a PodcastPlan that controls:
  - Which sections get full / brief / skip treatment
  - How many HOST↔EXPERT turns each section should have
  - The classified paper type (empirical / survey / theoretical / application)
  - The target episode duration and a one-line narrative angle

This single planning step replaces the hard-coded "always write all 6 sections"
logic and adapts the episode structure to the actual paper.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional, Callable

logger = logging.getLogger(__name__)

# ── Duration targets (minutes) keyed by paper_type + preferred length ─
_DURATION_MAP: dict[str, dict[str, int]] = {
    "empirical":    {"short": 8,  "medium": 14, "long": 22},
    "survey":       {"short": 10, "medium": 18, "long": 28},
    "theoretical":  {"short": 9,  "medium": 15, "long": 24},
    "application":  {"short": 7,  "medium": 12, "long": 20},
}

# Approx seconds per dialogue turn (used to estimate episode duration)
_SECS_PER_TURN = 28


# ── Data classes ──────────────────────────────────────────────────────

@dataclass
class SectionPlan:
    """Plan for one paper section."""
    key: str            # e.g. "methodology"
    display: str        # e.g. "Methodology"
    depth: str          # "full" | "brief" | "skip"
    focus_hint: str     # what the writer should emphasise
    turn_count: int     # target HOST/EXPERT exchange count


@dataclass
class PodcastPlan:
    """Complete episode plan returned by PlannerAgent."""
    paper_type: str          # "empirical" | "survey" | "theoretical" | "application"
    episode_angle: str       # one-sentence narrative hook for the intro
    target_duration: str     # "short" | "medium" | "long"
    target_minutes: int      # estimated episode length in minutes
    sections: list[SectionPlan] = field(default_factory=list)

    @property
    def full_sections(self) -> list[SectionPlan]:
        return [s for s in self.sections if s.depth == "full"]

    @property
    def brief_sections(self) -> list[SectionPlan]:
        return [s for s in self.sections if s.depth == "brief"]

    @property
    def active_sections(self) -> list[SectionPlan]:
        """All sections that will produce dialogue (full + brief)."""
        return [s for s in self.sections if s.depth != "skip"]

    def estimated_turns(self) -> int:
        return sum(s.turn_count for s in self.active_sections)

    def to_dict(self) -> dict:
        return {
            "paper_type": self.paper_type,
            "episode_angle": self.episode_angle,
            "target_duration": self.target_duration,
            "target_minutes": self.target_minutes,
            "sections": [
                {
                    "key": s.key,
                    "display": s.display,
                    "depth": s.depth,
                    "focus_hint": s.focus_hint,
                    "turn_count": s.turn_count,
                }
                for s in self.sections
            ],
        }


# ── Fallback plan (used when LLM call fails) ─────────────────────────

_ALL_SECTIONS = [
    ("abstract", "Abstract"),
    ("introduction", "Introduction"),
    ("related_work", "Related Work"),
    ("methodology", "Methodology"),
    ("results", "Results"),
    ("discussion", "Discussion"),
    ("conclusion", "Conclusion"),
]


def _make_fallback_plan(available_keys: list[str]) -> PodcastPlan:
    """Return a safe default plan when the LLM call fails."""
    sections = [
        SectionPlan(key=k, display=d, depth="full", focus_hint="", turn_count=5)
        for k, d in _ALL_SECTIONS
        if k in available_keys
    ]
    return PodcastPlan(
        paper_type="empirical",
        episode_angle="An in-depth look at a research paper.",
        target_duration="medium",
        target_minutes=14,
        sections=sections,
    )


# ── PlannerAgent ──────────────────────────────────────────────────────

class PlannerAgent:
    """
    Decides podcast structure with a single, cheap LLM call.

    Only reads the lightest sections (abstract, intro, conclusion) — typically
    ~1500 tokens — so the cost is minimal.
    """

    def __init__(self, backend: Optional[str] = None):
        self.backend = backend

    def plan(
        self,
        paper_sections: dict[str, str],
        title: str,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> PodcastPlan:
        """
        Produce a PodcastPlan for the given paper.

        Parameters
        ----------
        paper_sections : dict[str, str]
            Mapping of section key → text (LaTeX already converted).
        title : str
            Paper title (used in the prompt for context).
        progress_callback : callable, optional
            ``(message, fraction)`` status reporter.

        Returns
        -------
        PodcastPlan
        """
        def _prog(msg: str, frac: float) -> None:
            logger.info("[Planner %.0f%%] %s", frac * 100, msg)
            if progress_callback:
                progress_callback(msg, frac)

        available_keys = [k for k, v in paper_sections.items() if v and v.strip()]

        _prog("🧠 Planner reading paper…", 0.0)

        from prompts.templates import build_planner_messages
        from src.llm_interface import query_llm

        messages = build_planner_messages(
            title=title,
            abstract=paper_sections.get("abstract", ""),
            introduction=paper_sections.get("introduction", ""),
            conclusion=paper_sections.get("conclusion", ""),
            available_sections=available_keys,
        )

        try:
            raw = query_llm(messages, backend=self.backend, temperature=0.0, max_tokens=1024)
            plan = self._parse_plan(raw, available_keys)
            _prog(
                f"🧠 Plan: {plan.paper_type} · {plan.target_duration} "
                f"(~{plan.target_minutes} min) · "
                f"{len(plan.full_sections)} full + {len(plan.brief_sections)} brief sections",
                1.0,
            )
            return plan

        except Exception as exc:
            logger.warning("PlannerAgent failed (%s), using fallback plan.", exc)
            _prog("⚠️ Planner failed — using default plan.", 1.0)
            return _make_fallback_plan(available_keys)

    # ── Parsing ───────────────────────────────────────────────────────

    def _parse_plan(self, raw: str, available_keys: list[str]) -> PodcastPlan:
        """Parse and validate the LLM's JSON plan output."""
        # Strip markdown fencing
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text.strip())

        data = json.loads(text)

        paper_type = data.get("paper_type", "empirical").lower()
        if paper_type not in _DURATION_MAP:
            paper_type = "empirical"

        target_duration = data.get("target_duration", "medium").lower()
        if target_duration not in ("short", "medium", "long"):
            target_duration = "medium"

        target_minutes = _DURATION_MAP[paper_type].get(target_duration, 14)

        sections: list[SectionPlan] = []
        seen_keys: set[str] = set()

        for s in data.get("sections", []):
            key = s.get("key", "").lower()
            depth = s.get("depth", "skip").lower()
            if depth not in ("full", "brief", "skip"):
                depth = "skip"

            # Only include sections that exist in this paper
            if key not in available_keys:
                continue
            if key in seen_keys:
                continue
            seen_keys.add(key)

            # Clamp turn_count to sensible range
            raw_turns = int(s.get("turn_count", 5))
            if depth == "full":
                turn_count = max(4, min(raw_turns, 10))
            elif depth == "brief":
                turn_count = max(2, min(raw_turns, 3))
            else:
                turn_count = 0

            sections.append(SectionPlan(
                key=key,
                display=s.get("display", key.replace("_", " ").title()),
                depth=depth,
                focus_hint=s.get("focus_hint", ""),
                turn_count=turn_count,
            ))

        # Safety: if planner returned no active sections, promote all available to full
        if not any(s.depth != "skip" for s in sections):
            logger.warning("Planner returned no active sections — promoting all to full")
            return _make_fallback_plan(available_keys)

        return PodcastPlan(
            paper_type=paper_type,
            episode_angle=data.get("episode_angle", ""),
            target_duration=target_duration,
            target_minutes=target_minutes,
            sections=sections,
        )
