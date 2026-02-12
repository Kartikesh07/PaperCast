"""
tts_engine.py — Multi-voice Text-to-Speech generation.

Supports three engines:
  • Groq TTS    (PlayAI voices via Groq API, fast, high quality)
  • edge-tts    (Microsoft Edge TTS, free, high-quality, async)
  • Coqui TTS   (local VITS model, fully offline, CPU-friendly)

Generates one audio clip per dialogue turn, then concatenates them
with configurable silence gaps using pydub. Exports a single MP3.
"""

from __future__ import annotations

import asyncio
import gc
import logging
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Callable, Optional

from pydub import AudioSegment

# Point pydub at the ffmpeg binary bundled by imageio-ffmpeg
# so mp3 decoding works without a system-wide ffmpeg install.
try:
    import imageio_ffmpeg
    AudioSegment.converter = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError:
    pass  # Fall back to system ffmpeg if imageio-ffmpeg not installed

import config
from src.post_processor import ProcessedScript, Turn

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Groq TTS backend with auto-fallback to edge-tts
# ─────────────────────────────────────────────

# Retry config for transient (per-minute) rate limits
_GROQ_TTS_MAX_RETRIES = 3
_GROQ_TTS_RETRY_BASE_DELAY = 5  # seconds


def _is_daily_limit(exc: Exception) -> bool:
    """Return True if the error is a daily (TPD) rate limit — not worth retrying."""
    msg = str(exc).lower()
    return "tokens per day" in msg or "tpd" in msg


def _get_groq_voice(speaker: str) -> str:
    """Map speaker label to a Groq / PlayAI voice name."""
    if speaker == "HOST":
        return config.GROQ_VOICE_HOST
    return config.GROQ_VOICE_EXPERT


def _edge_fallback_single(turn: Turn, out_path: Path) -> Path:
    """Synthesize a single turn via edge-tts (sync wrapper)."""
    import edge_tts

    voice = _get_edge_voice(turn.speaker)
    communicate = edge_tts.Communicate(turn.text, voice)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import nest_asyncio
        nest_asyncio.apply()
        asyncio.get_event_loop().run_until_complete(communicate.save(str(out_path)))
    else:
        asyncio.run(communicate.save(str(out_path)))

    return out_path


def _generate_groq_clips(
    turns: list[Turn],
    tmp_dir: Path,
    progress_cb: Optional[Callable[[str, float], None]] = None,
) -> list[Path]:
    """
    Generate one WAV per turn using Groq's TTS API.

    If a per-minute (RPM/TPM) rate limit is hit, retries with exponential
    backoff.  If the daily token limit (TPD) is exhausted, automatically
    falls back to edge-tts for the remaining turns.
    """
    try:
        from groq import Groq
    except ImportError:
        raise ImportError(
            "Install the groq package:  pip install groq"
        )

    client = Groq(api_key=config.GROQ_API_KEY)
    clips: list[Path] = []
    total = len(turns)
    use_edge_fallback = False  # flip once on daily-limit hit

    for idx, turn in enumerate(turns):
        out_path = tmp_dir / f"turn_{idx:04d}.wav"

        # ── If daily limit already hit, go straight to edge-tts ──
        if use_edge_fallback:
            try:
                # edge-tts produces mp3
                edge_path = tmp_dir / f"turn_{idx:04d}.mp3"
                _edge_fallback_single(turn, edge_path)
                clips.append(edge_path)
            except Exception as edge_exc:
                logger.warning("Edge-tts fallback failed on turn %d: %s", idx, edge_exc)
                silence = AudioSegment.silent(duration=500)
                silence.export(str(out_path), format="wav")
                clips.append(out_path)

            if progress_cb:
                progress_cb(f"TTS (edge fallback): turn {idx + 1}/{total}", idx / total)
            continue

        # ── Try Groq with retries for transient rate limits ──
        success = False
        for attempt in range(_GROQ_TTS_MAX_RETRIES):
            try:
                voice = _get_groq_voice(turn.speaker)
                response = client.audio.speech.create(
                    model=config.GROQ_TTS_MODEL,
                    input=turn.text,
                    voice=voice,
                    response_format="wav",
                )
                response.write_to_file(str(out_path))
                clips.append(out_path)
                success = True
                break
            except Exception as exc:
                if "429" in str(exc) or "rate_limit" in str(exc).lower():
                    if _is_daily_limit(exc):
                        # Daily quota exhausted → switch all remaining to edge-tts
                        logger.warning(
                            "Groq TTS daily limit reached at turn %d. "
                            "Falling back to edge-tts for remaining turns.",
                            idx,
                        )
                        use_edge_fallback = True
                        break
                    else:
                        # Per-minute limit → wait and retry
                        delay = _GROQ_TTS_RETRY_BASE_DELAY * (2 ** attempt)
                        logger.info(
                            "Groq TTS rate-limited (RPM/TPM) on turn %d, "
                            "retrying in %ds (attempt %d/%d)…",
                            idx, delay, attempt + 1, _GROQ_TTS_MAX_RETRIES,
                        )
                        if progress_cb:
                            progress_cb(
                                f"Rate limited — waiting {delay}s before retry…",
                                idx / total,
                            )
                        time.sleep(delay)
                else:
                    # Non-rate-limit error → fall back immediately
                    logger.warning("Groq TTS failed on turn %d: %s", idx, exc)
                    break

        # If Groq didn't succeed (retries exhausted or daily limit), use edge-tts
        if not success:
            if use_edge_fallback:
                # Daily limit just triggered on this turn — handle it via edge
                try:
                    edge_path = tmp_dir / f"turn_{idx:04d}.mp3"
                    _edge_fallback_single(turn, edge_path)
                    clips.append(edge_path)
                except Exception as edge_exc:
                    logger.warning("Edge-tts fallback failed on turn %d: %s", idx, edge_exc)
                    silence = AudioSegment.silent(duration=500)
                    silence.export(str(out_path), format="wav")
                    clips.append(out_path)
            else:
                # Transient failure — try edge as one-off fallback
                try:
                    edge_path = tmp_dir / f"turn_{idx:04d}.mp3"
                    _edge_fallback_single(turn, edge_path)
                    clips.append(edge_path)
                    logger.info("Used edge-tts fallback for turn %d", idx)
                except Exception:
                    silence = AudioSegment.silent(duration=500)
                    silence.export(str(out_path), format="wav")
                    clips.append(out_path)

        if progress_cb:
            label = "TTS (edge fallback)" if use_edge_fallback else "TTS"
            progress_cb(f"{label}: turn {idx + 1}/{total}", idx / total)

    return clips


# ─────────────────────────────────────────────
# Edge-TTS backend (async, free, high quality)
# ─────────────────────────────────────────────

async def _edge_tts_synthesize(text: str, voice: str, out_path: Path) -> None:
    """Synthesize a single utterance with edge-tts."""
    import edge_tts

    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(out_path))


def _get_edge_voice(speaker: str) -> str:
    """Map speaker label to an edge-tts voice name."""
    if speaker == "HOST":
        return config.EDGE_VOICE_HOST
    return config.EDGE_VOICE_EXPERT


async def _generate_edge_clips(
    turns: list[Turn],
    tmp_dir: Path,
    progress_cb: Optional[Callable[[str, float], None]] = None,
) -> list[Path]:
    """Generate one MP3 per turn using edge-tts."""
    clips: list[Path] = []
    total = len(turns)

    for idx, turn in enumerate(turns):
        out_path = tmp_dir / f"turn_{idx:04d}.mp3"
        voice = _get_edge_voice(turn.speaker)

        try:
            await _edge_tts_synthesize(turn.text, voice, out_path)
            clips.append(out_path)
        except Exception as exc:
            logger.warning("edge-tts failed on turn %d: %s", idx, exc)
            # Create a short silence as placeholder (wav needs no ffmpeg)
            out_path = tmp_dir / f"turn_{idx:04d}.wav"
            silence = AudioSegment.silent(duration=500)
            silence.export(str(out_path), format="wav")
            clips.append(out_path)

        if progress_cb:
            progress_cb(f"TTS: turn {idx + 1}/{total}", idx / total)

    return clips


# ─────────────────────────────────────────────
# Coqui TTS backend (offline, CPU)
# ─────────────────────────────────────────────

def _generate_coqui_clips(
    turns: list[Turn],
    tmp_dir: Path,
    progress_cb: Optional[Callable[[str, float], None]] = None,
) -> list[Path]:
    """Generate one WAV per turn using Coqui TTS (VITS model)."""
    try:
        from TTS.api import TTS as CoquiTTS
    except ImportError:
        raise ImportError(
            "Coqui TTS is not installed. Install it with: pip install TTS"
        )

    tts = CoquiTTS(model_name=config.COQUI_MODEL_NAME, progress_bar=False)
    clips: list[Path] = []
    total = len(turns)

    for idx, turn in enumerate(turns):
        out_path = tmp_dir / f"turn_{idx:04d}.wav"

        try:
            tts.tts_to_file(text=turn.text, file_path=str(out_path))
            clips.append(out_path)
        except Exception as exc:
            logger.warning("Coqui TTS failed on turn %d: %s", idx, exc)
            silence = AudioSegment.silent(duration=500)
            silence.export(str(out_path), format="wav")
            clips.append(out_path)

        if progress_cb:
            progress_cb(f"TTS: turn {idx + 1}/{total}", idx / total)

    return clips


# ─────────────────────────────────────────────
# Concatenation
# ─────────────────────────────────────────────

def _load_clip(path: Path) -> AudioSegment:
    """
    Load an audio clip without relying on ffprobe.

    * .wav  → read directly via Python's wave module (no external tools).
    * .mp3  → convert to .wav with the bundled ffmpeg, then read the wav.
    """
    if path.suffix == ".wav":
        return AudioSegment.from_wav(str(path))

    # mp3 or other format → transcode to wav via ffmpeg subprocess
    ffmpeg_bin = getattr(AudioSegment, "converter", "ffmpeg")
    wav_path = path.with_suffix(".wav")
    subprocess.run(
        [ffmpeg_bin, "-y", "-i", str(path), str(wav_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    segment = AudioSegment.from_wav(str(wav_path))
    wav_path.unlink(missing_ok=True)
    return segment


def _concatenate_clips(
    clip_paths: list[Path],
    output_path: Path,
    silence_ms: int = config.SILENCE_BETWEEN_TURNS_MS,
) -> Path:
    """
    Concatenate audio clips with silence gaps between them.
    Returns the path to the final audio file.
    """
    silence = AudioSegment.silent(duration=silence_ms)
    combined = AudioSegment.empty()

    for path in clip_paths:
        try:
            segment = _load_clip(path)
            if len(combined) > 0:
                combined += silence
            combined += segment
        except Exception as exc:
            logger.warning("Skipping clip %s: %s", path.name, exc)

    combined.export(str(output_path), format=config.AUDIO_FORMAT)
    logger.info("Exported audio: %s (%.1f sec)", output_path, len(combined) / 1000)
    return output_path


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def generate_audio(
    script: ProcessedScript,
    output_path: Optional[Path] = None,
    engine: Optional[str] = None,
    progress_callback: Optional[Callable[[str, float], None]] = None,
) -> Path:
    """
    Generate a multi-voice podcast audio file from a ProcessedScript.

    Parameters
    ----------
    script : ProcessedScript
        The polished dialogue with speaker labels.
    output_path : Path, optional
        Where to save the final MP3. Defaults to ``output/podcast.mp3``.
    engine : str, optional
        ``"groq"``, ``"edge"``, or ``"coqui"``. Defaults to ``config.TTS_ENGINE``.
    progress_callback : callable, optional
        ``callback(stage_description, fraction_done)`` for UI updates.

    Returns
    -------
    Path
        Path to the generated audio file.
    """
    engine = (engine or config.TTS_ENGINE).lower()
    if output_path is None:
        output_path = config.OUTPUT_DIR / f"podcast.{config.AUDIO_FORMAT}"

    # Use a manual temp dir instead of a context manager to avoid
    # Windows file-locking issues (pydub keeps handles open).
    tmp_dir = Path(tempfile.mkdtemp())

    try:
        if engine == "groq":
            clips = _generate_groq_clips(script.turns, tmp_dir, progress_callback)

        elif engine == "edge":
            # edge-tts is async — run in event loop
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                # Already inside an async context (e.g. Streamlit)
                import nest_asyncio
                nest_asyncio.apply()
                clips = asyncio.get_event_loop().run_until_complete(
                    _generate_edge_clips(script.turns, tmp_dir, progress_callback)
                )
            else:
                clips = asyncio.run(
                    _generate_edge_clips(script.turns, tmp_dir, progress_callback)
                )

        elif engine == "coqui":
            clips = _generate_coqui_clips(script.turns, tmp_dir, progress_callback)
        else:
            raise ValueError(f"Unknown TTS engine: {engine}. Use 'groq', 'edge', or 'coqui'.")

        # Concatenate all clips into one file
        result = _concatenate_clips(clips, output_path)
        return result
    finally:
        # Force-close any lingering file handles before cleanup
        gc.collect()
        shutil.rmtree(tmp_dir, ignore_errors=True)
