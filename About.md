# About PaperCast

## Abstract

PaperCast is an end-to-end AI pipeline that converts academic papers (primarily arXiv preprints) into listener-friendly, two-host conversational podcast episodes. The system ingests PDFs, preserves LaTeX math tokens for later verbalization, generates multi-stage LLM scripts that produce a Host–Expert dialogue, runs light editorial passes to improve clarity and factual alignment, and (optionally) synthesizes multi-voice audio using pluggable TTS engines. Outputs are reproducible artifacts (page index, transcript, agent report, audio) intended for distribution, accessibility, and archival use. Design priorities include robustness to noisy PDFs, portability of audio artifacts (wav‑first outputs and bundled ffmpeg), configurable engine fallbacks, and a responsive web UI for job control and real‑time progress.

## Technical Architecture

Overview
- Input: an arXiv URL/ID or PDF → parsing and front‑matter extraction → LaTeX token capture → page indexing (for retrieval) → multi‑stage LLM generation → post‑processing → optional TTS → output artifacts (transcript, audio, metadata).
- The pipeline is cache‑aware: cached processed papers (page index, transcript, script, audio) are reused to avoid repeated LLM/TTS calls and to provide deterministic reproduction.

Core Components
- **API & Job Model:** `api.py` runs a FastAPI server that accepts generation requests, starts background workers (threaded jobs), provides polling and SSE streaming (`/api/stream/{job_id}`), serves audio files, and exposes cache management and a RAG Q&A endpoint. Jobs are tracked in a lightweight in‑memory store and communicate progress through callbacks.
- **Pipeline Orchestrator:** `src/pipeline.py` is the single entry point (`run_pipeline`) that sequences stages and maps fine‑grained progress into UI‑friendly updates. It handles backend selection, output paths, and saving cache metadata.
- **Parsing & Page Indexing:** `src/paper_parser.py` extracts text using PyMuPDF with block/column ordering, detects sections and front‑matter (title/authors/abstract) using heuristics + deterministic LLM prompts, and emits a page/paragraph index (used by RAG and Q&A).
- **LaTeX Preservation & Verbalization:** `src/latex_to_speech.py` tags inline and display LaTeX expressions as placeholders, collects originals for deterministic verbalization, and replaces placeholders with readable spoken forms (configurable verbalizer rules).
- **LLM & Agent Layer:** `src/llm_interface.py` abstracts multiple backends; `src/dialogue_generator.py` runs a staged generation pipeline (short summaries → per‑section dialogue → takeaways). Agent modules in `src/agents/` (planner, editor, critic) apply structural planning, in‑context editing, and lightweight factual checks to reduce hallucinations and enforce turn constraints.
- **Post‑processing:** `src/post_processor.py` normalizes speaker labels, removes disfluencies/fillers, formats dialog turns for TTS, and produces the canonical transcript (`transcript.txt`) and script JSON.
- **TTS & Audio Assembly:** `src/tts_engine.py` exposes a TTS adapter interface with multiple engines (cloud and local). The implementation prefers wav outputs, adds per‑turn padding and leveling, concatenates segments into a single episode, and relies on bundled ffmpeg (imageio‑ffmpeg) for safe mp3↔wav transcode when required.
- **Cache & Artifacts:** Processed papers are stored under `cache/` with structured JSON (metadata, `page_index.json`, `paper.json`, `script.json`) and the generated assets are placed in `output/`. Metadata includes the chosen LLM/TTS backends and seed parameters for reproducibility.
- **Frontend & UX:** A React + Vite + Tailwind app (`frontend/src/`) provides an input panel, progress view powered by SSE, transcript viewer and an audio player with download links.

Operational Properties
- **Resilience:** retry/backoff policies and deterministic fallback ordering allow the system to continue when cloud providers hit rate limits; local Coqui TTS supports offline runs.
- **Observability:** SSE streaming and rich job metadata (agent reports, errors, progress) provide live feedback and troubleshooting hooks.
- **Extensibility:** adapter patterns for LLMs and TTS engines plus modular agents make it straightforward to add new providers, persona templates, or post‑processing rules.

## Use Cases

- **Automated Episode Production:** Turn newly published arXiv papers into a ready‑to‑publish podcast episode (script + audio + show notes), enabling fast dissemination of research.
- **Science Communication & Journalism:** Produce conversational summaries and short audio segments for news desks, newsletters, or social audio clips.
- **Teaching & Study Aids:** Generate lecture‑style dialogues and concise takeaways for classroom materials, study groups, or flipped‑classroom content.
- **Accessibility & Inclusion:** Convert mathematical content into intelligible spoken math and publish synchronized transcripts/captions for visually impaired or non‑technical audiences.
- **Interactive Research Q&A:** Use the RAG Q&A endpoint to answer focused questions grounded on the paper’s indexed passages, useful for research tooling and exploration.
- **Private / Air‑Gapped Workflows:** Run with local TTS and cached artifacts to produce audio in environments where cloud APIs are restricted.

## Innovation

- **Conversationalization at Scale:** Automates multi‑turn, persona‑conditioned Host–Expert dialogues rather than single‑voice summaries, improving listener engagement and clarity.
- **Tight LaTeX Integration:** Preserves original LaTeX tokens and applies deterministic verbalization, enabling faithful spoken representations of equations and notation.
- **Agent‑Augmented Generation:** Combines multi‑stage LLM prompts with modular agent passes (planning, editing, critique) to reduce hallucinations, enforce constraints (turn count, role duties), and produce cleaner scripts.
- **Multi‑Engine, Wav‑First Audio Strategy:** Adapter pattern with wav‑first outputs and a bundled ffmpeg conversion pipeline ensures portable, high‑quality audio regardless of provider idiosyncrasies.
- **Reproducibility & Audit Trails:** Cache entries store page indexes, scripts, transcripts, seeds and agent reports to reproduce runs and to audit the pipeline’s outputs.
- **Developer‑Friendly UX for Long Jobs:** SSE streaming and job metadata make long‑running ML tasks observable and integrable into UIs or automation pipelines.

## Key Files (quick pointers)

- `api.py` — FastAPI server and job endpoints.  
- `src/pipeline.py` — Orchestrator and progress mapping.  
- `src/paper_parser.py` — PDF parsing and page indexing.  
- `src/latex_to_speech.py` — LaTeX placeholder tagging and verbalizer.  
- `src/dialogue_generator.py` — Multi‑stage script generator and agent calls.  
- `src/post_processor.py` — Transcript and script polishing.  
- `src/tts_engine.py` — TTS adapters and audio assembly.  
- `src/cache.py` — Cache read/write and artifact helpers.  
- `frontend/src/` — React + Vite + Tailwind UI and SSE client.

---

This expanded overview is intended to help developers and reviewers understand the system at a component and operational level. For implementation details, see the referenced files in the repository root and `src/` directory.
