"""
cache.py — Disk-based caching for PaperCast pipeline results.

Stores parsed paper sections + processed scripts keyed by arXiv paper ID.
On a cache hit the entire pipeline (PDF download, all LLM calls, TTS) is
skipped, returning results instantly.

Cache layout
------------
cache/
  <arxiv_id>/
    meta.json        ← title, authors, cached_at, llm_backend, tts_engine
    paper.json       ← serialised PaperSections (no page_index, no raw_text)
    script.json      ← serialised ProcessedScript (all turns + markers)
    page_index.json  ← serialised PageIndex for Q&A RAG (BM25 blocks)
    transcript.txt   ← plain-text transcript (copy from output/)
    audio.path       ← single line: relative path to audio file in output/
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import config
from src.page_indexer import PageIndex

logger = logging.getLogger(__name__)

# ── Regex to extract a clean arXiv ID from any URL form ───────────────

_ARXIV_ID_RE = re.compile(r"(\d{4}\.\d{4,5}(?:v\d+)?|[a-z\-]+/\d{7})")


def extract_arxiv_id(url_or_id: str) -> str:
    """
    Return a normalised arXiv ID (e.g. '2301.07041') from a URL or bare ID.
    Strips the version suffix so '2301.07041v2' and '2301.07041' share a cache.
    Returns the full input string if no ID pattern is found (safe fallback).
    """
    m = _ARXIV_ID_RE.search(url_or_id.strip())
    if m:
        # Strip version suffix for stable cache key
        raw = m.group(1)
        base = re.sub(r"v\d+$", "", raw)
        return base.replace("/", "_")   # 'hep-ph/0301200' → 'hep-ph_0301200'
    # Fallback: sanitise the whole string as a filename-safe key
    safe = re.sub(r"[^a-zA-Z0-9_\-]", "_", url_or_id.strip())
    return safe[:80]


# ── Cache directory helper ────────────────────────────────────────────

def get_cache_dir(arxiv_id: str) -> Path:
    """Return (and create if needed) the per-paper cache directory."""
    d = config.CACHE_DIR / arxiv_id
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── Serialisation helpers for PaperSections ──────────────────────────

def _paper_to_dict(paper) -> dict:
    """Convert a PaperSections instance to a JSON-serialisable dict."""
    return {
        "title": paper.title,
        "authors": paper.authors,
        "abstract": paper.abstract,
        "introduction": paper.introduction,
        "related_work": paper.related_work,
        "methodology": paper.methodology,
        "results": paper.results,
        "discussion": paper.discussion,
        "conclusion": paper.conclusion,
        # raw_text and latex_expressions are large and not needed for replay
        # page_index is stored separately
    }


def _paper_from_dict(d: dict):
    """Reconstruct a lightweight PaperSections from a cached dict."""
    from src.paper_parser import PaperSections
    return PaperSections(
        title=d.get("title", ""),
        authors=d.get("authors", ""),
        abstract=d.get("abstract", ""),
        introduction=d.get("introduction", ""),
        related_work=d.get("related_work", ""),
        methodology=d.get("methodology", ""),
        results=d.get("results", ""),
        discussion=d.get("discussion", ""),
        conclusion=d.get("conclusion", ""),
    )


# ── Serialisation helpers for ProcessedScript ─────────────────────────

def _script_to_dict(script) -> dict:
    """Convert a ProcessedScript (with Turn list) to a JSON-serialisable dict."""
    return {
        "title": script.title,
        "authors": script.authors,
        "summary": script.summary,
        "turns": [
            {"speaker": t.speaker, "text": t.text}
            for t in script.turns
        ],
        # segment_markers keys are int but JSON requires str keys
        "segment_markers": {
            str(k): v for k, v in script.segment_markers.items()
        },
    }


def _script_from_dict(d: dict):
    """Reconstruct a ProcessedScript from a cached dict."""
    from src.post_processor import ProcessedScript, Turn
    return ProcessedScript(
        title=d.get("title", ""),
        authors=d.get("authors", ""),
        summary=d.get("summary", ""),
        turns=[
            Turn(speaker=t["speaker"], text=t["text"])
            for t in d.get("turns", [])
        ],
        segment_markers={
            int(k): v for k, v in d.get("segment_markers", {}).items()
        },
    )


# ── Public API ────────────────────────────────────────────────────────

@dataclass
class CacheEntry:
    """Everything the pipeline returns, reconstructed from disk."""
    arxiv_id: str
    paper: object                      # PaperSections
    script: object                     # ProcessedScript
    transcript_path: Path
    audio_path: Optional[Path]
    cached_at: str
    llm_backend: str
    tts_engine: str
    page_index: Optional[PageIndex] = None   # BM25 index for Q&A RAG


def load_cached_entry(arxiv_id: str) -> Optional[CacheEntry]:
    """
    Try to load a previously cached result for *arxiv_id*.

    Returns a ``CacheEntry`` on hit, or ``None`` on miss/corrupt cache.
    """
    if not config.CACHE_ENABLED:
        return None

    cache_dir = config.CACHE_DIR / arxiv_id
    meta_path = cache_dir / "meta.json"
    paper_path = cache_dir / "paper.json"
    script_path = cache_dir / "script.json"
    transcript_path = cache_dir / "transcript.txt"

    if not all(p.exists() for p in [meta_path, paper_path, script_path, transcript_path]):
        return None

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        paper = _paper_from_dict(json.loads(paper_path.read_text(encoding="utf-8")))
        script = _script_from_dict(json.loads(script_path.read_text(encoding="utf-8")))

        audio_path: Optional[Path] = None
        audio_ptr = cache_dir / "audio.path"
        if audio_ptr.exists():
            rel = audio_ptr.read_text(encoding="utf-8").strip()
            candidate = config.OUTPUT_DIR / rel
            if candidate.exists():
                audio_path = candidate

        # Load page index for Q&A RAG
        page_index: Optional[PageIndex] = None
        page_index_path = cache_dir / "page_index.json"
        if page_index_path.exists():
            try:
                page_index = PageIndex.from_json(page_index_path.read_text(encoding="utf-8"))
                # Attach to paper so pipeline/generators can also use it
                paper.page_index = page_index
                logger.info("Loaded page index (%d blocks) for '%s'", page_index.total_blocks(), arxiv_id)
            except Exception as idx_exc:
                logger.warning("Page index load failed for '%s': %s", arxiv_id, idx_exc)

        logger.info("Cache HIT for arXiv ID '%s'", arxiv_id)
        return CacheEntry(
            arxiv_id=arxiv_id,
            paper=paper,
            script=script,
            transcript_path=transcript_path,
            audio_path=audio_path,
            cached_at=meta.get("cached_at", ""),
            llm_backend=meta.get("llm_backend", ""),
            tts_engine=meta.get("tts_engine", ""),
            page_index=page_index,
        )

    except Exception as exc:
        logger.warning("Cache read failed for '%s': %s — treating as miss", arxiv_id, exc)
        return None


def save_cache_entry(
    arxiv_id: str,
    paper,
    script,
    transcript_path: Path,
    audio_path: Optional[Path],
    llm_backend: str,
    tts_engine: str,
) -> None:
    """
    Persist a completed pipeline run to disk.

    Parameters mirror the pipeline's return dict.  All writes are atomic
    (write to tmp then rename) so a crash mid-write won't corrupt the cache.
    """
    if not config.CACHE_ENABLED:
        return

    try:
        cache_dir = get_cache_dir(arxiv_id)
        now = datetime.now(timezone.utc).isoformat()

        # meta.json
        meta = {
            "arxiv_id": arxiv_id,
            "title": paper.title,
            "authors": paper.authors,
            "cached_at": now,
            "llm_backend": llm_backend,
            "tts_engine": tts_engine,
        }
        (cache_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

        # paper.json
        (cache_dir / "paper.json").write_text(
            json.dumps(_paper_to_dict(paper), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # script.json
        (cache_dir / "script.json").write_text(
            json.dumps(_script_to_dict(script), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # page_index.json — serialise BM25 blocks for Q&A RAG
        if paper.page_index is not None:
            (cache_dir / "page_index.json").write_text(
                paper.page_index.to_json(), encoding="utf-8"
            )

        # transcript.txt — copy from output/transcript.txt into cache dir
        # so the cache is self-contained
        if transcript_path.exists():
            cached_transcript = cache_dir / "transcript.txt"
            cached_transcript.write_bytes(transcript_path.read_bytes())

        # audio.path — store relative filename only (audio lives in output/)
        if audio_path and audio_path.exists():
            rel = audio_path.name   # e.g. "podcast.wav"
            (cache_dir / "audio.path").write_text(rel, encoding="utf-8")

        logger.info("Cache SAVED for arXiv ID '%s' → %s", arxiv_id, cache_dir)

    except Exception as exc:
        # Cache write failure is non-fatal — pipeline result is still valid
        logger.warning("Cache save failed for '%s': %s", arxiv_id, exc)


def list_cached_papers() -> list[dict]:
    """
    Return a list of metadata dicts for every cached paper, newest first.
    Each dict has: arxiv_id, title, authors, cached_at, llm_backend, tts_engine.
    """
    if not config.CACHE_DIR.exists():
        return []

    results = []
    for meta_path in config.CACHE_DIR.glob("*/meta.json"):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            results.append(meta)
        except Exception:
            pass

    results.sort(key=lambda x: x.get("cached_at", ""), reverse=True)
    return results


def delete_cached_paper(arxiv_id: str) -> bool:
    """
    Delete the cache entry for *arxiv_id*.

    Returns True if the entry existed and was deleted, False if not found.
    """
    import shutil
    cache_dir = config.CACHE_DIR / arxiv_id
    if not cache_dir.exists():
        return False
    shutil.rmtree(cache_dir)
    logger.info("Cache DELETED for arXiv ID '%s'", arxiv_id)
    return True
