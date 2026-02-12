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
    def __init__(self, job_id: str, arxiv_url: str, llm: str, tts: str, gen_audio: bool):
        self.id = job_id
        self.arxiv_url = arxiv_url
        self.llm = llm
        self.tts = tts
        self.gen_audio = gen_audio
        self.status: str = "pending"       # pending | running | done | error
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


# ── Worker ───────────────────────────────────────────────────────────

def _run_job(job: Job):
    """Run the pipeline in a background thread."""
    job.status = "running"
    job.message = "Starting pipeline…"

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
    job = Job(job_id, req.arxiv_url, req.llm_backend, req.tts_engine, req.generate_audio)
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
