"""
llm_interface.py — Unified LLM abstraction layer.

Provides a single ``query_llm(messages, backend=...)`` function that
dispatches to OpenAI, Anthropic, or Ollama.  Swapping backends requires
changing one config variable — no other code changes needed.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import requests

import config

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Message type aliases
# ─────────────────────────────────────────────

Message = dict[str, str]  # {"role": "system"|"user"|"assistant", "content": "..."}


# ─────────────────────────────────────────────
# Backend implementations
# ─────────────────────────────────────────────

def _query_groq(
    messages: list[Message],
    model: str,
    temperature: float,
    max_tokens: int,
) -> str:
    """Call Groq's ultra-fast inference API (OpenAI-compatible SDK)."""
    try:
        from groq import Groq
    except ImportError:
        raise ImportError(
            "Install the groq package:  pip install groq"
        )

    client = Groq(api_key=config.GROQ_API_KEY)
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content.strip()


def _query_openai(
    messages: list[Message],
    model: str,
    temperature: float,
    max_tokens: int,
) -> str:
    """Call the OpenAI-compatible chat completions endpoint."""
    try:
        import openai
    except ImportError:
        raise ImportError(
            "Install the openai package:  pip install openai"
        )

    client = openai.OpenAI(api_key=config.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content.strip()


def _query_anthropic(
    messages: list[Message],
    model: str,
    temperature: float,
    max_tokens: int,
) -> str:
    """Call the Anthropic Messages API."""
    try:
        import anthropic
    except ImportError:
        raise ImportError(
            "Install the anthropic package:  pip install anthropic"
        )

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    # Anthropic separates system prompt from the message list
    system_text = ""
    chat_messages: list[dict[str, str]] = []
    for m in messages:
        if m["role"] == "system":
            system_text += m["content"] + "\n"
        else:
            chat_messages.append({"role": m["role"], "content": m["content"]})

    response = client.messages.create(
        model=model,
        system=system_text.strip(),
        messages=chat_messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.content[0].text.strip()


def _query_ollama(
    messages: list[Message],
    model: str,
    temperature: float,
    max_tokens: int,
) -> str:
    """
    Call a local Ollama instance via its REST API.
    No API key needed — runs entirely offline.
    """
    url = f"{config.OLLAMA_BASE_URL}/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }

    try:
        resp = requests.post(url, json=payload, timeout=300)
        resp.raise_for_status()
    except requests.ConnectionError:
        raise ConnectionError(
            f"Cannot reach Ollama at {config.OLLAMA_BASE_URL}. "
            "Make sure Ollama is running (`ollama serve`)."
        )

    data = resp.json()
    return data["message"]["content"].strip()


# ─────────────────────────────────────────────
# Unified public interface
# ─────────────────────────────────────────────

_BACKENDS = {
    "groq": (_query_groq, lambda: config.GROQ_MODEL),
    "openai": (_query_openai, lambda: config.OPENAI_MODEL),
    "anthropic": (_query_anthropic, lambda: config.ANTHROPIC_MODEL),
    "ollama": (_query_ollama, lambda: config.OLLAMA_MODEL),
}


def query_llm(
    messages: list[Message],
    backend: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> str:
    """
    Send a list of chat messages to the configured LLM and return the
    assistant's reply as a string.

    Parameters
    ----------
    messages : list[Message]
        OpenAI-style message dicts with ``role`` and ``content`` keys.
    backend : str, optional
        Override ``config.LLM_BACKEND`` for this call.
    temperature : float, optional
        Sampling temperature (default from config).
    max_tokens : int, optional
        Max response tokens (default from config).

    Returns
    -------
    str
        The model's reply text.
    """
    backend = (backend or config.LLM_BACKEND).lower()
    temperature = temperature if temperature is not None else config.LLM_TEMPERATURE
    max_tokens = max_tokens if max_tokens is not None else config.LLM_MAX_TOKENS

    if backend not in _BACKENDS:
        raise ValueError(
            f"Unknown LLM backend '{backend}'. "
            f"Choose from: {', '.join(_BACKENDS)}"
        )

    fn, model_getter = _BACKENDS[backend]
    model = model_getter()

    logger.info("LLM [%s/%s] ← %d messages", backend, model, len(messages))

    reply = fn(messages, model, temperature, max_tokens)

    logger.info("LLM [%s/%s] → %d chars", backend, model, len(reply))
    return reply
