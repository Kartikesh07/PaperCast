"""
api.py — FastAPI backend for the PaperCast React frontend.

Provides REST endpoints for:
  • POST /api/generate   → start pipeline (SSE stream for progress)
  • GET  /api/audio/{filename} → serve generated audio
  • GET  /api/transcript  → return the latest transcript
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

import config
from src.pipeline import run_pipeline
from src.cache import list_cached_papers, delete_cached_paper, extract_arxiv_id

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="PaperCast API", version="1.0.0")

# Allow the Vite dev server to talk to us
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── In-memory job store ──────────────────────────────────────────────

class Job:
    def __init__(self, job_id: str, arxiv_url: str, llm: str, tts: str, gen_audio: bool, force_refresh: bool = False):
        self.id = job_id
        self.arxiv_url = arxiv_url
        self.llm = llm
        self.tts = tts
        self.gen_audio = gen_audio
        self.force_refresh = force_refresh
        self.arxiv_id: Optional[str] = None   # set after pipeline resolves the ID
        self.status: str = "pending"
        self.progress: float = 0.0
        self.message: str = ""
        self.error: Optional[str] = None
        self.result: Optional[dict] = None

_jobs: dict[str, Job] = {}


# ── Request / Response models ────────────────────────────────────────

class GenerateRequest(BaseModel):
    arxiv_url: str
    llm_backend: str = "groq"
    tts_engine: str = "edge"
    generate_audio: bool = True
    force_refresh: bool = False


class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: float
    message: str
    error: Optional[str] = None
    title: Optional[str] = None
    authors: Optional[str] = None
    abstract: Optional[str] = None
    transcript: Optional[str] = None
    audio_url: Optional[str] = None
    arxiv_id: Optional[str] = None
    agent_report: Optional[dict] = None


# ── Worker ───────────────────────────────────────────────────────────

def _run_job(job: Job):
    """Run the pipeline in a background thread."""
    job.status = "running"
    job.message = "Starting pipeline…"

    # Pre-resolve the arXiv ID so it's available even before pipeline finishes
    from src.cache import extract_arxiv_id as _extract_id
    try:
        job.arxiv_id = _extract_id(job.arxiv_url)
    except Exception:
        pass

    def _progress(msg: str, frac: float):
        job.message = msg
        job.progress = frac

    try:
        result = run_pipeline(
            arxiv_url=job.arxiv_url,
            llm_backend=job.llm,
            tts_engine=job.tts,
            generate_audio_flag=job.gen_audio,
            progress_callback=_progress,
            force_refresh=job.force_refresh,
        )
        job.result = result
        job.status = "done"
        job.progress = 1.0
        job.message = "Pipeline finished!"
    except Exception as exc:
        logger.exception("Pipeline failed for job %s", job.id)
        job.status = "error"
        job.error = str(exc)
        job.message = f"Error: {exc}"


# ── Endpoints ────────────────────────────────────────────────────────

@app.post("/api/generate")
def start_generation(req: GenerateRequest):
    """Kick off a pipeline run and return a job ID."""
    job_id = uuid.uuid4().hex[:12]
    job = Job(
        job_id,
        req.arxiv_url,
        req.llm_backend,
        req.tts_engine,
        req.generate_audio,
        force_refresh=req.force_refresh,
    )
    _jobs[job_id] = job
    thread = threading.Thread(target=_run_job, args=(job,), daemon=True)
    thread.start()
    return {"job_id": job_id}


@app.get("/api/status/{job_id}")
def get_status(job_id: str):
    """Poll the status of a running job."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    resp = JobStatus(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        message=job.message,
        error=job.error,
        arxiv_id=job.arxiv_id,
    )

    if job.result:
        paper = job.result["paper"]
        resp.title = paper.title
        resp.authors = paper.authors
        resp.abstract = paper.abstract
        transcript_path: Path = job.result["transcript_path"]
        if transcript_path.exists():
            resp.transcript = transcript_path.read_text(encoding="utf-8")
        audio_path = job.result.get("audio_path")
        if audio_path and Path(audio_path).exists():
            resp.audio_url = f"/api/audio/{Path(audio_path).name}"
        agent_report = job.result.get("agent_report")
        if agent_report:
            resp.agent_report = agent_report

    return resp


@app.get("/api/stream/{job_id}")
def stream_status(job_id: str):
    """SSE stream of job progress for real-time UI updates."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    def event_generator():
        last_msg = ""
        last_progress = -1.0
        while True:
            if job.message != last_msg or job.progress != last_progress:
                last_msg = job.message
                last_progress = job.progress
                data = json.dumps({
                    "status": job.status,
                    "progress": job.progress,
                    "message": job.message,
                    "error": job.error,
                })
                yield f"data: {data}\n\n"

            if job.status in ("done", "error"):
                # Final payload with full results
                final = {"status": job.status, "progress": job.progress, "message": job.message}
                if job.result:
                    paper = job.result["paper"]
                    final["title"] = paper.title
                    final["authors"] = paper.authors
                    final["abstract"] = paper.abstract
                    final["arxiv_id"] = job.arxiv_id
                    agent_report = job.result.get("agent_report")
                    if agent_report:
                        final["agent_report"] = agent_report
                    tp = job.result["transcript_path"]
                    if Path(tp).exists():
                        final["transcript"] = Path(tp).read_text(encoding="utf-8")
                    ap = job.result.get("audio_path")
                    if ap and Path(ap).exists():
                        final["audio_url"] = f"/api/audio/{Path(ap).name}"
                if job.error:
                    final["error"] = job.error
                yield f"data: {json.dumps(final)}\n\n"
                break
            time.sleep(0.3)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/audio/{filename}")
def serve_audio(filename: str):
    """Serve a generated audio file."""
    path = config.OUTPUT_DIR / filename
    if not path.exists():
        raise HTTPException(404, "Audio file not found")
    media = "audio/wav" if filename.endswith(".wav") else "audio/mpeg"
    return FileResponse(path, media_type=media, filename=filename)


# ── Q&A endpoint ─────────────────────────────────────────────────────

class AskRequest(BaseModel):
    arxiv_id: str
    question: str
    conversation_history: list[dict] = []   # [{role, content}, ...]


_QA_SYSTEM_PROMPT = """You are a knowledgeable research assistant helping a user understand an academic paper.
You are given:
1. Relevant passages retrieved from the paper (your context window).
2. The user's question.

Rules:
- Answer ONLY based on the retrieved passages. Do not hallucinate facts not present in the text.
- If the passages don't contain enough information, say so clearly.
- Be concise but thorough. Use plain English — avoid unnecessary jargon.
- When citing a specific finding or claim, indicate where it came from (e.g. "According to the methodology section...").
- Format your answer in clear prose, not bullet points, unless the question explicitly asks for a list.
"""


@app.post("/api/ask")
def ask_paper(req: AskRequest):
    """
    Answer a question about a paper using Page Index RAG + Groq LLM.

    Requires the paper to have been processed at least once (cache entry
    with a page_index.json must exist).  Uses BM25 retrieval to find the
    most relevant passages, then calls Groq to answer with those passages
    as grounded context.
    """
    from src.cache import load_cached_entry
    from src.llm_interface import query_llm

    arxiv_id = req.arxiv_id.strip()
    question = req.question.strip()

    if not question:
        raise HTTPException(400, "question cannot be empty")

    # Load cached entry (which now includes the page index)
    cached = load_cached_entry(arxiv_id)
    if cached is None:
        raise HTTPException(
            404,
            f"No cached paper found for '{arxiv_id}'. "
            "Process the paper first via POST /api/generate."
        )

    if cached.page_index is None or cached.page_index.total_blocks() == 0:
        raise HTTPException(
            422,
            f"Page index not available for '{arxiv_id}'. "
            "Re-process the paper with force_refresh=true to rebuild the index."
        )

    # BM25 retrieval — get the most relevant passages for the question
    context_passages = cached.page_index.retrieve(question, top_k=config.RAG_TOP_K)

    if not context_passages.strip():
        return {
            "answer": (
                "I couldn't find relevant passages in this paper to answer your question. "
                "Try rephrasing or asking about a different aspect of the paper."
            ),
            "context_used": "",
            "arxiv_id": arxiv_id,
        }

    # Build message list with optional conversation history
    paper_meta = f'Paper: "{cached.paper.title}" by {cached.paper.authors}' if cached.paper.title else ""

    context_block = (
        f"{paper_meta}\n\n"
        f"--- Retrieved passages from the paper ---\n\n"
        f"{context_passages}\n\n"
        f"--- End of retrieved passages ---"
    )

    messages = [{"role": "system", "content": _QA_SYSTEM_PROMPT}]

    # Inject prior turns (trim to last 6 to avoid blowing the context window)
    for turn in req.conversation_history[-6:]:
        if turn.get("role") in ("user", "assistant") and turn.get("content"):
            messages.append({"role": turn["role"], "content": turn["content"]})

    # Current question with context
    messages.append({
        "role": "user",
        "content": f"{context_block}\n\nQuestion: {question}"
    })

    try:
        answer = query_llm(
            messages,
            backend="groq",          # always use Groq for Q&A
            temperature=0.3,         # more deterministic for factual Q&A
            max_tokens=1024,
        )
    except Exception as exc:
        logger.exception("Q&A LLM call failed for '%s'", arxiv_id)
        raise HTTPException(500, f"LLM call failed: {exc}")

    return {
        "answer": answer,
        "context_used": context_passages,
        "arxiv_id": arxiv_id,
    }


# ── Cache management endpoints ────────────────────────────────────────

@app.get("/api/cache")
def list_cache():
    """
    List all cached papers with their metadata.

    Returns a list of objects sorted newest-first, each with:
      arxiv_id, title, authors, cached_at, llm_backend, tts_engine
    """
    return {"papers": list_cached_papers()}


@app.delete("/api/cache/{arxiv_id}")
def clear_cache_entry(arxiv_id: str):
    """
    Delete the cached result for a specific arXiv paper.

    Pass the normalised arXiv ID (e.g. '2301.07041').  The ID is visible
    in the GET /api/cache response.
    """
    deleted = delete_cached_paper(arxiv_id)
    if not deleted:
        raise HTTPException(404, f"No cache entry found for '{arxiv_id}'")
    return {"deleted": arxiv_id}


@app.delete("/api/cache")
def clear_all_cache():
    """Delete ALL cached papers (use with caution)."""
    import shutil
    deleted = []
    if config.CACHE_DIR.exists():
        for entry in config.CACHE_DIR.iterdir():
            if entry.is_dir():
                shutil.rmtree(entry)
                deleted.append(entry.name)
    return {"deleted": deleted, "count": len(deleted)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
