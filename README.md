# 🎙️ Paper → Podcast

Transform dense academic arXiv papers into engaging two-host conversational podcasts — complete with a readable transcript and optional multi-voice audio.

## Features

- **Structured PDF parsing** — extracts title, authors, abstract, methodology, results, discussion, and conclusion from any arXiv paper using PyMuPDF.
- **LaTeX → spoken English** — converts math notation into natural language before dialogue generation (e.g., `x^2` → "x squared").
- **Multi-stage dialogue generation** — not a single monolithic prompt; generates a summary first, then section-by-section dialogue with distinct Host/Expert personas.
- **Three interchangeable LLM backends** — Groq (default, ultra-fast), OpenAI, Anthropic, or fully offline via Ollama (Mistral-7B). Swap with one config variable.
- **Script post-processing** — normalises speaker labels, strips residual artefacts, injects sparse conversational fillers, and adds timestamps.
- **Multi-voice TTS** — Groq TTS with PlayAI voices (default), edge-tts (free Microsoft voices), or Coqui TTS (fully offline). Generates per-turn audio and concatenates with natural pacing.
- **Clean Streamlit UI** — progress bar, split transcript/audio view, download buttons.

## Project Structure

```
fysem2/
├── app.py                  # Streamlit interface
├── config.py               # Central configuration
├── requirements.txt
├── README.md
├── src/
│   ├── paper_parser.py     # PDF download & structured extraction
│   ├── latex_to_speech.py  # LaTeX → spoken English converter
│   ├── llm_interface.py    # Unified LLM abstraction layer
│   ├── dialogue_generator.py  # Multi-stage dialogue pipeline
│   ├── post_processor.py   # Script cleaning & polishing
│   ├── tts_engine.py       # Multi-voice audio generation
│   └── pipeline.py         # End-to-end orchestrator
├── prompts/
│   └── templates.py        # System prompts, personas, few-shot examples
└── output/                 # Generated transcripts & audio files
```

## Quick Start

### 1. Clone & set up the virtual environment

```bash
cd fysem2
python -m venv venv

# Windows
.\venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

> **Note:** You also need **ffmpeg** installed on your system for pydub audio processing.
> - Windows: `choco install ffmpeg` or download from https://ffmpeg.org
> - macOS: `brew install ffmpeg`
> - Linux: `sudo apt install ffmpeg`

### 3. Choose your LLM backend

#### Option A — Groq (fast, free tier, recommended)

1. Get a free API key at https://console.groq.com
2. Set it:
   ```bash
   set GROQ_API_KEY=gsk_...        # Windows
   export GROQ_API_KEY=gsk_...     # macOS/Linux
   ```
3. No extra config needed — Groq is the default backend for both LLM **and** TTS.

#### Option B — Ollama (free, fully offline)

1. Install Ollama: https://ollama.com/download
2. Pull a model:
   ```bash
   ollama pull mistral
   ```
3. Start the server:
   ```bash
   ollama serve
   ```
4. Set backend:
   ```bash
   set LLM_BACKEND=ollama
   ```

#### Option C — OpenAI

```bash
set OPENAI_API_KEY=sk-...       # Windows
export OPENAI_API_KEY=sk-...    # macOS/Linux
set LLM_BACKEND=openai
```

#### Option D — Anthropic

```bash
set ANTHROPIC_API_KEY=sk-ant-...
set LLM_BACKEND=anthropic
```

### 4. Run the app

```bash
streamlit run app.py
```

Open http://localhost:8501 in your browser, paste an arXiv URL, and click **Generate Podcast**.

## Configuration

All settings are in `config.py`:

| Variable | Default | Description |
|---|---|---|
| `LLM_BACKEND` | `"groq"` | `"groq"`, `"openai"`, `"anthropic"`, or `"ollama"` |
| `GROQ_API_KEY` | `""` | Your Groq API key (used for both LLM and TTS) |
| `GROQ_MODEL` | `"llama-3.3-70b-versatile"` | Groq LLM model |
| `TTS_ENGINE` | `"groq"` | `"groq"`, `"edge"`, or `"coqui"` |
| `GROQ_VOICE_HOST` | `"tara"` | Host voice for Groq TTS |
| `GROQ_VOICE_EXPERT` | `"dan"` | Expert voice for Groq TTS |
| `OLLAMA_MODEL` | `"mistral"` | Any model pulled into Ollama |
| `EDGE_VOICE_HOST` | `"en-US-JennyNeural"` | Host voice for edge-tts |
| `EDGE_VOICE_EXPERT` | `"en-US-GuyNeural"` | Expert voice for edge-tts |
| `SILENCE_BETWEEN_TURNS_MS` | `600` | Pause between speaker turns |
| `LLM_TEMPERATURE` | `0.7` | Creativity of dialogue generation |

## System Requirements

- Python 3.10+
- 8–16 GB RAM (Ollama models need ~4–8 GB)
- ffmpeg on PATH
- Internet connection for arXiv downloads and edge-tts (not needed for Ollama + Coqui)

## Module Overview

| Module | Responsibility |
|---|---|
| `paper_parser.py` | Downloads the PDF, extracts text with PyMuPDF, splits into structured sections, strips citations and figure references |
| `latex_to_speech.py` | Regex + lookup-table converter that transforms LaTeX into spoken English (handles fractions, superscripts, Greek letters, nested expressions) |
| `llm_interface.py` | Unified `query_llm()` function that dispatches to OpenAI / Anthropic / Ollama behind a common interface |
| `dialogue_generator.py` | Multi-stage pipeline: summary → per-section dialogue → takeaway, with persona prompts and few-shot examples |
| `post_processor.py` | Normalises speaker labels, removes artefacts, injects fillers, adds timestamps and segment markers |
| `tts_engine.py` | Generates per-turn audio clips (edge-tts or Coqui VITS), concatenates with silence gaps via pydub |
| `pipeline.py` | Orchestrates all stages with progress reporting |
| `templates.py` | Contains all prompt templates, persona definitions, and few-shot examples |

## License

MIT
