"""
page_indexer.py — Lightweight BM25 Page Index for PaperCast RAG.

Replaces the dumb `section_text[:MAX_SECTION_CHARS]` truncation with
keyword-based passage retrieval.  Uses PyMuPDF's block-level extraction
to preserve page/position metadata, then builds a BM25 index over the
blocks — no embedding models, no external databases, no API calls.

Usage
-----
    from src.page_indexer import build_page_index

    # During parsing (pdf_path still available)
    index = build_page_index(pdf_path)

    # During dialogue generation
    passage = index.retrieve_for_section("methodology", top_k=8)
    # → returns the most relevant passages for that section type
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ── Pre-built queries per section type ───────────────────────────────
# These are used when the caller asks for a section by name rather than
# providing an explicit query string.

_SECTION_QUERIES: dict[str, str] = {
    "abstract": (
        "problem statement motivation contribution overview summary"
    ),
    "introduction": (
        "background motivation problem statement related work contribution"
    ),
    "related_work": (
        "previous work prior methods baseline comparison state of the art"
    ),
    "methodology": (
        "method model architecture approach algorithm training loss function "
        "implementation framework design procedure formulation"
    ),
    "results": (
        "results evaluation experiments performance accuracy metrics "
        "comparison benchmark ablation improvement"
    ),
    "discussion": (
        "discussion analysis limitation future work implication insight"
    ),
    "conclusion": (
        "conclusion summary takeaway future direction impact contribution"
    ),
}


# ── Data structures ───────────────────────────────────────────────────

@dataclass
class PageBlock:
    """One text block extracted from a PDF page."""
    page_num: int
    block_num: int
    text: str
    x0: float = 0.0
    y0: float = 0.0


@dataclass
class PageIndex:
    """
    BM25 index built from the blocks of a parsed PDF.

    The index is lazy-built on first query and cached in memory.
    """
    blocks: list[PageBlock] = field(default_factory=list)
    _bm25: object = field(default=None, init=False, repr=False, compare=False)

    # ── Build / query ─────────────────────────────────────────────────

    def _ensure_index(self) -> None:
        """Build the BM25 index lazily the first time it's needed."""
        if self._bm25 is not None:
            return
        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            raise ImportError(
                "rank-bm25 is required for Page Index RAG. "
                "Install it with: pip install rank-bm25"
            )

        tokenized = [_tokenize(b.text) for b in self.blocks]
        # Filter out blocks that tokenize to nothing so BM25 doesn't crash
        non_empty = [(i, toks) for i, toks in enumerate(tokenized) if toks]
        if not non_empty:
            logger.warning("PageIndex: all blocks are empty after tokenization")
            self._bm25 = None
            return

        self._block_indices, tokenized_clean = zip(*non_empty)
        self._bm25 = BM25Okapi(list(tokenized_clean))

    def retrieve(self, query: str, top_k: int = 8, min_chars: int = 40) -> str:
        """
        Return the top-k most relevant text blocks for *query*,
        concatenated into a single string.

        Parameters
        ----------
        query : str
            Free-text query describing what you're looking for.
        top_k : int
            Maximum number of blocks to return.
        min_chars : int
            Minimum characters a block must have to be included
            (filters out headers, page numbers, single-word blocks).

        Returns
        -------
        str
            Concatenated passage text, one block per paragraph.
            Returns empty string if the index has no content.
        """
        self._ensure_index()
        if self._bm25 is None:
            return ""

        query_tokens = _tokenize(query)
        if not query_tokens:
            return ""

        scores = self._bm25.get_scores(query_tokens)

        # Map scores back to original block indices
        ranked = sorted(
            zip(self._block_indices, scores),
            key=lambda x: x[1],
            reverse=True,
        )

        selected: list[str] = []
        seen_texts: set[str] = set()

        for orig_idx, score in ranked:
            if len(selected) >= top_k:
                break
            block = self.blocks[orig_idx]
            text = block.text.strip()

            # Skip short blocks (headers, footers, page numbers)
            if len(text) < min_chars:
                continue

            # Deduplicate near-identical blocks (e.g. running headers)
            key = text[:80]
            if key in seen_texts:
                continue
            seen_texts.add(key)

            selected.append(text)

        return "\n\n".join(selected)

    def retrieve_for_section(self, section_name: str, top_k: int = 8) -> str:
        """
        Retrieve the most relevant passages for a known section type
        using a pre-built query for that section.

        Falls back to returning all blocks for unknown section names.

        Parameters
        ----------
        section_name : str
            One of: abstract, introduction, related_work, methodology,
            results, discussion, conclusion.
        top_k : int
            Number of passages to return.
        """
        query = _SECTION_QUERIES.get(section_name.lower(), section_name)
        return self.retrieve(query, top_k=top_k)

    def total_blocks(self) -> int:
        """Return the number of blocks in the index."""
        return len(self.blocks)

    # ── Serialisation ─────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Serialise the index to a JSON-compatible dict (blocks only)."""
        return {
            "blocks": [
                {
                    "page_num": b.page_num,
                    "block_num": b.block_num,
                    "text": b.text,
                    "x0": b.x0,
                    "y0": b.y0,
                }
                for b in self.blocks
            ]
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PageIndex":
        """Reconstruct a PageIndex from a serialised dict."""
        blocks = [
            PageBlock(
                page_num=b["page_num"],
                block_num=b["block_num"],
                text=b["text"],
                x0=b.get("x0", 0.0),
                y0=b.get("y0", 0.0),
            )
            for b in d.get("blocks", [])
        ]
        return cls(blocks=blocks)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, s: str) -> "PageIndex":
        return cls.from_dict(json.loads(s))


# ── Tokeniser ─────────────────────────────────────────────────────────

_WORD_RE = re.compile(r"[a-zA-Z0-9]+")


def _tokenize(text: str) -> list[str]:
    """
    Simple whitespace + lowercasing tokeniser for BM25.
    Filters out pure-numeric tokens and very short tokens.
    """
    tokens = _WORD_RE.findall(text.lower())
    return [t for t in tokens if len(t) > 1 and not t.isdigit()]


# ── PDF block extractor ───────────────────────────────────────────────

# Blocks shorter than this (chars) are treated as noise (headers, page nums)
_MIN_BLOCK_CHARS = 30

# Skip blocks that look like page headers / footers
_NOISE_RE = re.compile(
    r"^(arXiv:|Preprint|Under review|Published|Submitted|©|Page \d|^\d+$)",
    re.I,
)


def build_page_index(pdf_path: Path) -> PageIndex:
    """
    Extract text blocks from *pdf_path* using PyMuPDF and build a
    PageIndex for BM25 retrieval.

    Parameters
    ----------
    pdf_path : Path
        Path to a downloaded arXiv PDF.

    Returns
    -------
    PageIndex
        Ready-to-query index.  The BM25 index itself is built lazily
        on the first call to ``retrieve()``.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise ImportError(
            "PyMuPDF is required for page index building. "
            "Install with: pip install PyMuPDF"
        )

    blocks: list[PageBlock] = []

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as exc:
        logger.error("PageIndex: could not open PDF %s: %s", pdf_path, exc)
        return PageIndex(blocks=[])

    for page_num, page in enumerate(doc):
        # get_text("blocks") returns a list of:
        # (x0, y0, x1, y1, text, block_no, block_type)
        # block_type 0 = text, 1 = image
        raw_blocks = page.get_text("blocks", sort=True)

        for raw in raw_blocks:
            block_type = raw[6]
            if block_type != 0:          # skip image blocks
                continue

            text: str = raw[4].strip()
            if not text or len(text) < _MIN_BLOCK_CHARS:
                continue
            if _NOISE_RE.match(text):
                continue

            # Collapse internal newlines to spaces (common in two-column PDFs
            # where PyMuPDF splits a single paragraph across lines)
            text = " ".join(text.split())

            blocks.append(
                PageBlock(
                    page_num=page_num,
                    block_num=int(raw[5]),
                    text=text,
                    x0=float(raw[0]),
                    y0=float(raw[1]),
                )
            )

    doc.close()

    logger.info(
        "PageIndex: built %d blocks from %d pages of %s",
        len(blocks),
        page_num + 1 if blocks else 0,
        pdf_path.name,
    )
    return PageIndex(blocks=blocks)
