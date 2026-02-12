"""
Central configuration for the ArXiv-to-Podcast pipeline.

All tuneable knobs live here so that swapping backends or tweaking
behaviour requires editing exactly one file.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (before any os.getenv calls)
load_dotenv(Path(__file__).resolve().parent / ".env")

# ──────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# ──────────────────────────────────────────────
# LLM Backend  ("groq" | "openai" | "anthropic" | "ollama")
# ──────────────────────────────────────────────
LLM_BACKEND = os.getenv("LLM_BACKEND", "groq")

# Groq (fast inference, free tier available)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Anthropic
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")

# Ollama (fully offline, free)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")

# Common LLM parameters
LLM_TEMPERATURE = 0.7
LLM_MAX_TOKENS = 4096

# ──────────────────────────────────────────────
# TTS Engine  ("groq" | "edge" | "coqui")
# ──────────────────────────────────────────────
TTS_ENGINE = os.getenv("TTS_ENGINE", "groq")

# Groq TTS (Orpheus model via Groq API — uses GROQ_API_KEY above)
GROQ_TTS_MODEL = "canopylabs/orpheus-v1-english"
GROQ_VOICE_HOST = "diana"               # warm, clear female voice
GROQ_VOICE_EXPERT = "austin"              # deep, confident male voice

# edge-tts voice assignments
EDGE_VOICE_HOST = "en-US-JennyNeural"
EDGE_VOICE_EXPERT = "en-US-GuyNeural"

# Coqui TTS model (VITS, runs on CPU)
COQUI_MODEL_NAME = "tts_models/en/ljspeech/vits"

# Audio settings
SILENCE_BETWEEN_TURNS_MS = 600  # milliseconds of silence between speakers
AUDIO_FORMAT = "wav"             # wav works without ffmpeg; change to mp3 if ffmpeg is installed

# ──────────────────────────────────────────────
# Pipeline
# ──────────────────────────────────────────────
MAX_SECTION_CHARS = 6000  # truncate very long sections before sending to LLM
MIN_DIALOGUE_TURNS = 4    # minimum host/expert exchanges per section
