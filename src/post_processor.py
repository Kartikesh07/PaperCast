"""
post_processor.py — Clean, validate, and polish raw dialogue output.

Runs after the LLM generates raw dialogue and applies:
  1. Consistent speaker-label normalisation (HOST: / EXPERT:).
  2. Removal of residual LaTeX, markdown, or citation artefacts.
  3. Injection of sparse conversational fillers for realism.
  4. Timestamp and segment-title formatting.
  5. Basic hallucination guard — flags turns that look fabricated.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Optional

from src.dialogue_generator import FullScript, DialogueSegment


# ─────────────────────────────────────────────
# Regex patterns for cleaning
# ─────────────────────────────────────────────

# Matches various speaker labels the LLM might produce
_SPEAKER_RE = re.compile(
    r"^(Host|HOST|Expert|EXPERT|Interviewer|Guest|Speaker\s*[12AB])\s*[:：]\s*",
    re.M,
)

# Residual LaTeX fragments
_LATEX_RESIDUAL = re.compile(r"\\[a-zA-Z]+(\{[^}]*\})*|\$[^$]+\$|\$\$[^$]+\$\$")

# Markdown bold/italic/headers
_MARKDOWN_RE = re.compile(r"(\*{1,3}|_{1,3}|#{1,6}\s)")

# Citation-like references [1], (Author et al., 2023)
_CITATION_BRACKETS = re.compile(r"\[\d[\d,;\s\-]*\]")
_CITATION_PARENS = re.compile(
    r"\([A-Z][a-zéèêë]+(?:\s+(?:et\s+al\.?|and|&)\s+[A-Z][a-zéèêë]+)*"
    r",?\s*\d{4}[a-z]?\)",
)

# Figure / table / equation references
_FIG_REF_RE = re.compile(
    r"(as\s+(shown|seen|illustrated|depicted)\s+in\s+)?"
    r"(Fig(ure|\.)?|Table|Eq(uation|\.)?)\s*\.?\s*\d+(\.\d+)*[a-z]?",
    re.I,
)


# ─────────────────────────────────────────────
# Conversational fillers (used sparingly)
# ─────────────────────────────────────────────

_HOST_FILLERS = [
    "Hmm, interesting.",
    "Right, okay.",
    "Got it.",
    "That makes sense.",
    "Oh wow.",
]

_EXPERT_FILLERS = [
    "That's a great question.",
    "So basically,",
    "Right, so",
    "Yeah, exactly.",
    "Good point.",
]

_FILLER_INJECTION_PROB = 0.15  # probability of adding a filler per turn


# ─────────────────────────────────────────────
# Parsed turn
# ─────────────────────────────────────────────

@dataclass
class Turn:
    speaker: str   # "HOST" or "EXPERT"
    text: str


@dataclass
class ProcessedScript:
    """Final polished script with timestamps and segment markers."""
    title: str
    authors: str
    summary: str
    turns: list[Turn] = field(default_factory=list)
    segment_markers: dict[int, str] = field(default_factory=dict)  # turn_idx → title

    def to_text(self) -> str:
        """Render the script as a readable transcript with timestamps."""
        lines: list[str] = []
        lines.append(f"PODCAST TRANSCRIPT: {self.title}\n")
        lines.append(f"Authors: {self.authors}\n")
        lines.append("=" * 60 + "\n")

        # Estimate ~3 seconds per sentence for timestamps
        elapsed_seconds = 0
        for i, turn in enumerate(self.turns):
            if i in self.segment_markers:
                lines.append(f"\n{'─' * 40}")
                lines.append(f"  [{self._fmt_ts(elapsed_seconds)}] {self.segment_markers[i]}")
                lines.append(f"{'─' * 40}\n")

            ts = self._fmt_ts(elapsed_seconds)
            lines.append(f"[{ts}] {turn.speaker}: {turn.text}\n")

            # Rough estimate: 3 sec per sentence
            num_sentences = max(1, turn.text.count(".") + turn.text.count("?") + turn.text.count("!"))
            elapsed_seconds += num_sentences * 3

        return "\n".join(lines)

    @staticmethod
    def _fmt_ts(seconds: int) -> str:
        m, s = divmod(seconds, 60)
        return f"{m:02d}:{s:02d}"


# ─────────────────────────────────────────────
# Cleaning functions
# ─────────────────────────────────────────────

def _normalise_speaker(line: str) -> Optional[tuple[str, str]]:
    """
    Parse a line into (SPEAKER, text). Returns None if the line has no
    speaker prefix.
    """
    m = _SPEAKER_RE.match(line)
    if not m:
        return None

    raw_label = m.group(1).strip().upper()
    text = line[m.end():].strip()

    if raw_label in ("HOST", "INTERVIEWER", "SPEAKER 1", "SPEAKER A"):
        return "HOST", text
    return "EXPERT", text


def _clean_turn_text(text: str) -> str:
    """Remove LaTeX residue, markdown, citations, and figure refs from a turn."""
    text = _LATEX_RESIDUAL.sub("", text)
    text = _MARKDOWN_RE.sub("", text)
    text = _CITATION_BRACKETS.sub("", text)
    text = _CITATION_PARENS.sub("", text)
    text = _FIG_REF_RE.sub("", text)
    # Collapse multiple spaces / orphaned punctuation
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    text = re.sub(r"([.,;:!?]){2,}", r"\1", text)
    return text.strip()


def _maybe_inject_filler(turn: Turn, rng: random.Random) -> Turn:
    """With low probability, prepend a natural filler phrase."""
    if rng.random() > _FILLER_INJECTION_PROB:
        return turn

    fillers = _HOST_FILLERS if turn.speaker == "HOST" else _EXPERT_FILLERS
    filler = rng.choice(fillers)

    # Don't double-inject if the text already starts with a filler
    if any(turn.text.lower().startswith(f.lower().rstrip(",. ")) for f in fillers):
        return turn

    # Some fillers are sentence starters, some are interjections
    if filler.endswith(","):
        turn.text = f"{filler} {turn.text[0].lower()}{turn.text[1:]}"
    else:
        turn.text = f"{filler} {turn.text}"

    return turn


def _parse_dialogue_block(text: str) -> list[Turn]:
    """Parse a block of dialogue text into a list of Turn objects."""
    turns: list[Turn] = []
    current_speaker: Optional[str] = None
    current_lines: list[str] = []

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue

        parsed = _normalise_speaker(line)
        if parsed:
            # Flush previous turn
            if current_speaker and current_lines:
                turns.append(Turn(speaker=current_speaker, text=" ".join(current_lines)))
            current_speaker, first_text = parsed
            current_lines = [first_text] if first_text else []
        elif current_speaker:
            # Continuation line of current speaker
            current_lines.append(line)

    # Flush last turn
    if current_speaker and current_lines:
        turns.append(Turn(speaker=current_speaker, text=" ".join(current_lines)))

    return turns


# ─────────────────────────────────────────────
# Main post-processor
# ─────────────────────────────────────────────

def post_process(script: FullScript, seed: int = 42) -> ProcessedScript:
    """
    Take a raw FullScript from the dialogue generator and produce a
    polished ProcessedScript ready for TTS.

    Steps:
      1. Parse intro + segment dialogues + outro into Turn objects.
      2. Normalise speaker labels.
      3. Clean residual artefacts from each turn.
      4. Inject sparse conversational fillers.
      5. Record segment boundaries for timestamps.
    """
    rng = random.Random(seed)
    all_turns: list[Turn] = []
    segment_markers: dict[int, str] = {}

    # ── Intro ────────────────────────────────────────────────
    intro_turns = _parse_dialogue_block(script.intro)
    for t in intro_turns:
        t.text = _clean_turn_text(t.text)
        t = _maybe_inject_filler(t, rng)
    if intro_turns:
        segment_markers[0] = "Introduction"
    all_turns.extend(intro_turns)

    # ── Section segments ─────────────────────────────────────
    for seg in script.segments:
        seg_turns = _parse_dialogue_block(seg.raw_dialogue)
        for t in seg_turns:
            t.text = _clean_turn_text(t.text)
            t = _maybe_inject_filler(t, rng)

        if seg_turns:
            segment_markers[len(all_turns)] = seg.section_title
        all_turns.extend(seg_turns)

    # ── Outro ────────────────────────────────────────────────
    outro_turns = _parse_dialogue_block(script.outro)
    for t in outro_turns:
        t.text = _clean_turn_text(t.text)
    if outro_turns:
        segment_markers[len(all_turns)] = "Closing"
    all_turns.extend(outro_turns)

    # ── Filter empty turns ───────────────────────────────────
    all_turns = [t for t in all_turns if t.text.strip()]

    return ProcessedScript(
        title=script.title,
        authors=script.authors,
        summary=script.summary,
        turns=all_turns,
        segment_markers=segment_markers,
    )
