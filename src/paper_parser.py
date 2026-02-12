"""
paper_parser.py — Download and structurally parse arXiv PDFs.

Uses PyMuPDF (fitz) to extract text, then applies heuristic rules to
separate the paper into canonical academic sections.  Handles multi-column
layouts, strips citation markers, and preserves inline LaTeX for later
conversion.
"""

from __future__ import annotations

import json
import logging
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF
import requests

import config

logger = logging.getLogger(__name__)


# ── Canonical section keys in presentation order ──────────────────────
SECTION_ORDER = [
    "title",
    "authors",
    "abstract",
    "introduction",
    "methodology",
    "results",
    "discussion",
    "conclusion",
]

# Patterns used to detect section headings (case-insensitive)
_HEADING_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("abstract", re.compile(r"^\s*abstract\s*$", re.I)),
    ("introduction", re.compile(r"^\s*\d*\.?\s*introduction\s*$", re.I)),
    (
        "methodology",
        re.compile(
            r"^\s*\d*\.?\s*(method(ology|s)?|approach|model|framework|proposed\s+(method|approach|system))\s*$",
            re.I,
        ),
    ),
    (
        "results",
        re.compile(
            r"^\s*\d*\.?\s*(results?|experiments?|evaluation|findings)\s*$", re.I
        ),
    ),
    (
        "discussion",
        re.compile(
            r"^\s*\d*\.?\s*(discussion|analysis|limitations?)\s*$", re.I
        ),
    ),
    (
        "conclusion",
        re.compile(
            r"^\s*\d*\.?\s*(conclusion|conclusions|summary|concluding\s+remarks|future\s+work)\s*$",
            re.I,
        ),
    ),
    (
        "references",
        re.compile(
            r"^\s*\d*\.?\s*(references|bibliography)\s*$", re.I
        ),
    ),
    (
        "appendix",
        re.compile(r"^\s*\d*\.?\s*(appendix|appendices|supplementary)\s*$", re.I),
    ),
    (
        "related_work",
        re.compile(r"^\s*\d*\.?\s*(related\s+work|background|literature\s+review|prior\s+work)\s*$", re.I),
    ),
]


@dataclass
class PaperSections:
    """Container for the structured output of the parser."""
    title: str = ""
    authors: str = ""
    abstract: str = ""
    introduction: str = ""
    related_work: str = ""
    methodology: str = ""
    results: str = ""
    discussion: str = ""
    conclusion: str = ""
    raw_text: str = ""
    latex_expressions: list[str] = field(default_factory=list)


# ── Helpers ───────────────────────────────────────────────────────────

def _arxiv_url_to_pdf(url_or_id: str) -> str:
    """
    Normalise an arXiv URL or plain ID (e.g. '2301.07041') into
    a direct PDF download link.
    """
    # Strip trailing whitespace / slashes
    url_or_id = url_or_id.strip().rstrip("/")

    # Already a direct PDF link
    if url_or_id.endswith(".pdf"):
        return url_or_id

    # Extract the ID from various URL forms
    match = re.search(r"(\d{4}\.\d{4,5})(v\d+)?", url_or_id)
    if match:
        paper_id = match.group(0)
        return f"https://arxiv.org/pdf/{paper_id}.pdf"

    # Old-style IDs  (e.g. hep-ph/0301200)
    match = re.search(r"([a-z\-]+/\d{7})", url_or_id)
    if match:
        paper_id = match.group(1)
        return f"https://arxiv.org/pdf/{paper_id}.pdf"

    raise ValueError(f"Cannot parse arXiv identifier from: {url_or_id}")


def download_pdf(url_or_id: str, dest: Optional[Path] = None) -> Path:
    """Download the PDF and return the local file path."""
    pdf_url = _arxiv_url_to_pdf(url_or_id)
    resp = requests.get(pdf_url, timeout=60)
    resp.raise_for_status()

    if dest is None:
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        dest = Path(tmp.name)
        tmp.close()

    dest.write_bytes(resp.content)
    return dest


# ── Text extraction ──────────────────────────────────────────────────

def _extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Extract text via PyMuPDF using the 'text' extraction mode,
    which handles multi-column layouts better than raw char extraction.
    """
    doc = fitz.open(str(pdf_path))
    pages: list[str] = []
    for page in doc:
        # sort=True reorders blocks top-to-bottom, left-to-right
        # which helps with two-column papers
        text = page.get_text("text", sort=True)
        pages.append(text)
    doc.close()
    return "\n".join(pages)


# ── Cleaning helpers ─────────────────────────────────────────────────

_CITATION_RE = re.compile(r"\[[\d,;\s\–\-]+\]")          # [1], [1,2], [1-3]
_FIGURE_REF_RE = re.compile(
    r"(Fig(ure|\.)?|Table|Eq(uation|\.)?)\s*\.?\s*\d+(\.\d+)*[a-z]?",
    re.I,
)
_LATEX_INLINE_RE = re.compile(r"\$([^$]+)\$")              # $...$
_LATEX_DISPLAY_RE = re.compile(r"\$\$(.+?)\$\$", re.S)    # $$...$$
_HEADER_FOOTER_RE = re.compile(
    r"^(arXiv:\d{4}\.\d{4,5}|Preprint\.?\s*Under\s+review|Published\s+.+).*$",
    re.I | re.M,
)
_MULTIPLE_NEWLINES = re.compile(r"\n{3,}")
_MULTIPLE_SPACES = re.compile(r"[ \t]{2,}")


def _extract_latex(text: str) -> tuple[str, list[str]]:
    """
    Find inline & display LaTeX, replace with tagged placeholders,
    and collect the raw expressions for downstream spoken-math conversion.
    """
    expressions: list[str] = []

    def _replace(m: re.Match) -> str:
        expr = m.group(1).strip()
        idx = len(expressions)
        expressions.append(expr)
        return f" <<LATEX:{idx}>> "

    text = _LATEX_DISPLAY_RE.sub(_replace, text)
    text = _LATEX_INLINE_RE.sub(_replace, text)
    return text, expressions


def _clean_text(text: str) -> str:
    """Remove citations, figure refs, headers/footers, normalise whitespace."""
    text = _HEADER_FOOTER_RE.sub("", text)
    text = _CITATION_RE.sub("", text)
    text = _FIGURE_REF_RE.sub("", text)
    text = _MULTIPLE_SPACES.sub(" ", text)
    text = _MULTIPLE_NEWLINES.sub("\n\n", text)
    return text.strip()


# ── Section splitting ────────────────────────────────────────────────

def _identify_heading(line: str) -> Optional[str]:
    """Return the canonical section key if *line* looks like a heading."""
    stripped = line.strip()
    # Headings are usually short
    if len(stripped) > 80:
        return None
    for key, pat in _HEADING_PATTERNS:
        if pat.match(stripped):
            return key
    # Catch generic numbered section headings (e.g. "2. Data" → methodology)
    if re.match(r'^\s*\d+\.?\s+\S', stripped) and len(stripped) < 60:
        return _guess_section_key(stripped)
    return None


_SECTION_KEYWORDS: dict[str, list[str]] = {
    "introduction": ["introduction", "overview", "motivation", "background"],
    "methodology": [
        "method", "model", "framework", "approach", "formulation",
        "simulation", "setup", "implementation", "algorithm", "data",
        "observations", "numerical", "equations", "formalism",
        "architecture", "design", "procedure", "technique",
    ],
    "results": [
        "result", "experiment", "evaluation", "finding", "performance",
        "outcome", "comparison", "benchmark", "ablation", "analysis",
        "measurement",
    ],
    "discussion": [
        "discussion", "interpretation", "implication", "limitation",
        "caveat", "consideration",
    ],
    "conclusion": [
        "conclusion", "summary", "future", "outlook", "closing",
        "concluding",
    ],
    "related_work": [
        "related", "prior", "literature", "previous", "review",
        "context", "state of the art",
    ],
}


def _guess_section_key(heading_text: str) -> Optional[str]:
    """Map an unrecognised numbered heading to the best canonical key."""
    lower = heading_text.lower()
    best_key: Optional[str] = None
    best_score = 0
    for key, keywords in _SECTION_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in lower)
        if score > best_score:
            best_score = score
            best_key = key
    return best_key if best_score > 0 else "methodology"  # safe default for unknown sections


# ── LLM-based front-matter extraction ────────────────────────────────

_FRONT_MATTER_PROMPT = """You are an expert at parsing academic papers.
Given the raw text from the first pages of a research paper, extract
the **title**, **authors**, and **abstract**.

IMPORTANT RULES:
- The title is the actual research paper title, NOT things like
  "Draft version ...", "Typeset using LATEX ...", "Preprint", or journal names.
- Authors are the people who wrote the paper, with optional affiliations.
  Return only the names, separated by commas.
- The abstract is the text immediately after the word "Abstract" (or after
  the author list if no explicit Abstract heading exists).
- If you cannot confidently identify a field, return an empty string for it.

Return ONLY a valid JSON object with exactly these keys:
{"title": "...", "authors": "...", "abstract": "..."}

No extra text, no markdown fencing, just the JSON object."""


def _extract_front_matter_llm(raw_text: str) -> dict[str, str]:
    """
    Use the configured LLM to robustly extract title, authors, and
    abstract from the first ~3000 characters of the paper.
    """
    from src.llm_interface import query_llm

    # Send only the first chunk — enough to contain front matter
    snippet = raw_text[:4000]

    messages = [
        {"role": "system", "content": _FRONT_MATTER_PROMPT},
        {"role": "user", "content": snippet},
    ]

    try:
        reply = query_llm(
            messages,
            temperature=0.0,  # deterministic extraction
            max_tokens=1024,
        )
        # Strip markdown fencing if the model wraps it
        reply = reply.strip()
        if reply.startswith("```"):
            reply = re.sub(r"^```(?:json)?\s*", "", reply)
            reply = re.sub(r"\s*```$", "", reply)
        result = json.loads(reply)
        logger.info("LLM front-matter extraction succeeded")
        return {
            "title": result.get("title", "").strip(),
            "authors": result.get("authors", "").strip(),
            "abstract": result.get("abstract", "").strip(),
        }
    except Exception as exc:
        logger.warning("LLM front-matter extraction failed: %s", exc)
        return {}


def _extract_title_authors_heuristic(lines: list[str]) -> tuple[str, str, int]:
    """
    Fallback heuristic when LLM extraction is unavailable.
    Takes text before the abstract and splits on blank-line boundaries.
    """
    title_lines: list[str] = []
    author_lines: list[str] = []
    phase = "title"
    consumed = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        consumed = i

        if _identify_heading(stripped) is not None:
            break

        if phase == "title":
            if stripped == "":
                if title_lines:
                    phase = "authors"
                continue
            title_lines.append(stripped)
        elif phase == "authors":
            if stripped == "" and author_lines:
                break
            author_lines.append(stripped)

    title = " ".join(title_lines)
    authors = ", ".join(author_lines)
    return title, authors, consumed


def _find_abstract_line(lines: list[str]) -> int:
    """Return the line index where the abstract heading appears, or -1."""
    for i, line in enumerate(lines):
        if re.match(r'^\s*abstract\s*$', line.strip(), re.I):
            return i
    return -1


def _split_into_sections(
    text: str,
    raw_text: str = "",
) -> dict[str, str]:
    """
    Walk through lines, detect headings, and collect text under each
    heading into a dict keyed by canonical section name.

    Uses the LLM to robustly extract title / authors / abstract from
    the raw (uncleaned) front matter.  Falls back to a heuristic if
    the LLM call fails.
    """
    lines = text.split("\n")
    sections: dict[str, list[str]] = {}
    current_key: Optional[str] = None

    # ── Front-matter: title, authors, abstract via LLM ──
    front = _extract_front_matter_llm(raw_text or text)

    if front.get("title"):
        sections["title"] = [front["title"]]
        sections["authors"] = [front.get("authors", "")]
        if front.get("abstract"):
            sections["abstract"] = [front["abstract"]]
        # Figure out where to start scanning body sections.
        # Skip past the abstract heading + its content.
        abs_idx = _find_abstract_line(lines)
        if abs_idx >= 0:
            skip_to = abs_idx + 1  # heading detection loop will grab abstract content
            # If LLM already gave us abstract, skip past it entirely
            if front.get("abstract"):
                # Advance past blank lines + abstract body to next heading
                for j in range(abs_idx + 1, len(lines)):
                    if _identify_heading(lines[j]) and _identify_heading(lines[j]) != "abstract":
                        skip_to = j
                        break
                else:
                    skip_to = abs_idx + 1
        else:
            skip_to = 0
    else:
        # LLM failed → use heuristic
        logger.info("Falling back to heuristic title/author extraction")
        title, authors, skip_to = _extract_title_authors_heuristic(lines)
        sections["title"] = [title]
        sections["authors"] = [authors]

    for line in lines[skip_to:]:
        heading = _identify_heading(line)
        if heading:
            # Don't keep references or appendix content
            if heading in ("references", "appendix"):
                current_key = None
                continue
            current_key = heading
            # Don't overwrite LLM-extracted abstract
            if heading == "abstract" and "abstract" in sections:
                current_key = None
                continue
            sections.setdefault(current_key, [])
            continue

        if current_key is not None:
            sections.setdefault(current_key, []).append(line)

    return {k: "\n".join(v).strip() for k, v in sections.items()}


# ── Public API ───────────────────────────────────────────────────────

def parse_paper(url_or_id: str, keep_pdf: bool = False) -> PaperSections:
    """
    End-to-end: download → extract → clean → split → return structured
    PaperSections object.

    Parameters
    ----------
    url_or_id : str
        An arXiv URL (abs or pdf) or a plain paper ID like ``2301.07041``.
    keep_pdf : bool
        If True the downloaded PDF is not deleted after parsing.

    Returns
    -------
    PaperSections
    """
    pdf_path = download_pdf(url_or_id)

    try:
        raw_text = _extract_text_from_pdf(pdf_path)
    finally:
        if not keep_pdf:
            pdf_path.unlink(missing_ok=True)

    # Extract and tag LaTeX before any other cleaning
    text_with_tags, latex_exprs = _extract_latex(raw_text)
    cleaned = _clean_text(text_with_tags)

    section_map = _split_into_sections(cleaned, raw_text=raw_text)

    paper = PaperSections(
        title=section_map.get("title", ""),
        authors=section_map.get("authors", ""),
        abstract=section_map.get("abstract", ""),
        introduction=section_map.get("introduction", ""),
        related_work=section_map.get("related_work", ""),
        methodology=section_map.get("methodology", ""),
        results=section_map.get("results", ""),
        discussion=section_map.get("discussion", ""),
        conclusion=section_map.get("conclusion", ""),
        raw_text=raw_text,
        latex_expressions=latex_exprs,
    )
    return paper
