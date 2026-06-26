from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from groq import Groq

from ..core.config import PROJECT_ROOT


class LLMProviderError(RuntimeError):
    """Raised when an LLM provider call cannot be completed."""


def groq_chat_completion(
    messages: list[dict[str, str]],
    model: str,
    temperature: float = 0.1,
    response_format: dict[str, str] | None = None,
    max_tokens: int = 2048,
) -> str:
    """Call Groq's chat completions API through the official SDK."""
    api_key = _env_value("GROQ_API_KEY")
    if not api_key:
        raise LLMProviderError("GROQ_API_KEY is not set.")

    kwargs: dict[str, Any] = {
        "messages": messages,
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format:
        kwargs["response_format"] = response_format

    try:
        client = Groq(api_key=api_key, timeout=120.0)
        completion = client.chat.completions.create(**kwargs)
    except Exception as exc:
        raise LLMProviderError(f"Groq SDK request failed: {exc}") from exc

    try:
        choice = completion.choices[0]
        content = choice.message.content
    except (AttributeError, IndexError, TypeError) as exc:
        raise LLMProviderError(f"Unexpected Groq SDK response shape: {completion}") from exc
    if content is None:
        raise LLMProviderError(f"Groq SDK returned an empty message: {completion}")
    if not str(content).strip():
        finish_reason = getattr(choice, "finish_reason", None)
        raise LLMProviderError(f"Groq SDK returned blank content. finish_reason={finish_reason}")
    return content


def groq_transcribe_audio(
    filename: str,
    content: bytes,
    content_type: str | None = None,
    model: str = "whisper-large-v3-turbo",
    language: str | None = None,
) -> str:
    """Transcribe an uploaded audio file with Groq's speech-to-text API."""
    api_key = _env_value("GROQ_API_KEY")
    if not api_key:
        raise LLMProviderError("GROQ_API_KEY is not set.")
    if not content:
        raise LLMProviderError("Audio file is empty.")

    file_payload: tuple[str, bytes] | tuple[str, bytes, str]
    if content_type:
        file_payload = (filename, content, content_type)
    else:
        file_payload = (filename, content)

    kwargs: dict[str, Any] = {
        "file": file_payload,
        "model": model,
        "response_format": "json",
        "temperature": 0.0,
    }
    if language:
        kwargs["language"] = language

    try:
        client = Groq(api_key=api_key, timeout=120.0)
        transcription = client.audio.transcriptions.create(**kwargs)
    except Exception as exc:
        raise LLMProviderError(f"Groq transcription request failed: {exc}") from exc

    text = getattr(transcription, "text", None)
    if not text:
        raise LLMProviderError(f"Groq transcription returned empty text: {transcription}")
    return str(text).strip()


def has_groq_api_key() -> bool:
    """Return whether GROQ_API_KEY is available from the environment or .env files."""
    return bool(_env_value("GROQ_API_KEY"))


def parse_json_object(value: str) -> dict[str, Any]:
    """Parse an LLM JSON object, allowing simple fenced-code wrappers."""
    text = value.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("Expected a JSON object.")
    return parsed


def _env_value(name: str) -> str | None:
    value = os.getenv(name)
    if value:
        return value
    for env_path in (PROJECT_ROOT / ".env", PROJECT_ROOT / "src" / ".env"):
        value = _read_env_file(env_path).get(name)
        if value:
            os.environ.setdefault(name, value)
            return value
    return None


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values
