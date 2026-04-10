"""
critic.py — CriticAgent: reviews each dialogue segment for faithfulness and quality.

After the WriterAgent produces a segment, the CriticAgent scores it on:
  1. Faithfulness — are all claims grounded in the source text?
  2. Pacing      — is the turn balance reasonable (not a lecture monologue)?
  3. Relevance   — does the dialogue actually cover the section content?

If the verdict is FAIL, the agent returns a list of specific issues that are
injected as a corrective hint into the Writer's next attempt.  Max 1 retry
per segment (controlled by config.CRITIC_MAX_RETRIES) to avoid infinite loops.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional, Callable

import config

logger = logging.getLogger(__name__)


# ── Data classes ──────────────────────────────────────────────────────

@dataclass
class CritiqueResult:
    """Verdict returned by CriticAgent for one dialogue segment."""
    passed: bool
    severity: str           # "none" | "minor" | "major"
    issues: list[str] = field(default_factory=list)
    suggestions: str = ""
    regenerated: bool = False   # set True by the caller if a rewrite was triggered

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "severity": self.severity,
            "issues": self.issues,
            "suggestions": self.suggestions,
            "regenerated": self.regenerated,
        }


# ── CriticAgent ───────────────────────────────────────────────────────

class CriticAgent:
    """
    Reviews a generated dialogue segment against its source text.

    Uses a single, focused LLM call with temperature=0 for reproducibility.
    Returns a CritiqueResult that the caller can act on.
    """

    def __init__(self, backend: Optional[str] = None):
        self.backend = backend

    def critique(
        self,
        section_title: str,
        source_text: str,
        dialogue: str,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> CritiqueResult:
        """
        Evaluate a dialogue segment.

        Parameters
        ----------
        section_title : str
            Name of the section (e.g. "Methodology").
        source_text : str
            The retrieved passages used to generate the dialogue.
        dialogue : str
            The raw HOST/EXPERT dialogue to evaluate.
        progress_callback : callable, optional

        Returns
        -------
        CritiqueResult
        """
        if not config.CRITIC_ENABLED:
            return CritiqueResult(passed=True, severity="none")

        def _prog(msg: str, frac: float) -> None:
            logger.info("[Critic %.0f%%] %s", frac * 100, msg)
            if progress_callback:
                progress_callback(msg, frac)

        _prog(f"🔍 Critic reviewing {section_title}…", 0.0)

        from prompts.templates import build_critic_messages
        from src.llm_interface import query_llm

        messages = build_critic_messages(
            section_title=section_title,
            source_text=source_text[:3000],   # cap to avoid huge prompts
            dialogue=dialogue[:3000],
        )

        try:
            raw = query_llm(messages, backend=self.backend, temperature=0.0, max_tokens=512)
            result = self._parse_result(raw)

            if result.passed:
                _prog(f"✅ Critic: {section_title} passed ({result.severity} issues)", 1.0)
            else:
                _prog(
                    f"⚠️ Critic: {section_title} FAILED — {len(result.issues)} issue(s): "
                    f"{'; '.join(result.issues[:2])}",
                    1.0,
                )

            return result

        except Exception as exc:
            logger.warning("CriticAgent failed for '%s': %s — passing by default", section_title, exc)
            return CritiqueResult(passed=True, severity="none")

    # ── Parsing ───────────────────────────────────────────────────────

    def _parse_result(self, raw: str) -> CritiqueResult:
        """Parse the LLM's JSON critique output."""
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text.strip())

        data = json.loads(text)

        passed = bool(data.get("passed", True))
        severity = data.get("severity", "none").lower()
        if severity not in ("none", "minor", "major"):
            severity = "minor"

        # A "minor" severity still passes — only major failures trigger rewrite
        if severity == "minor":
            passed = True
        elif severity == "major":
            passed = False

        return CritiqueResult(
            passed=passed,
            severity=severity,
            issues=list(data.get("issues", [])),
            suggestions=str(data.get("suggestions", "")),
        )
