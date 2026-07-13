from __future__ import annotations

import asyncio
import os
from typing import Optional

from groq import Groq

from config import GROQ_API_KEY, GROQ_STT_MODEL


class SpeechProviderError(RuntimeError):
    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


def _guess_mime_type(filename: str, mime_type: Optional[str]) -> str:
    if mime_type:
        return mime_type
    lower = (filename or "").lower()
    if lower.endswith(".ogg") or lower.endswith(".oga"):
        return "audio/ogg"
    if lower.endswith(".mp3"):
        return "audio/mpeg"
    if lower.endswith(".wav"):
        return "audio/wav"
    if lower.endswith(".m4a"):
        return "audio/mp4"
    return "application/octet-stream"


def _transcribe_sync(
    audio_bytes: bytes,
    filename: str,
    mime_type: Optional[str],
    model: Optional[str],
) -> str:
    api_key = GROQ_API_KEY or os.getenv("GROQ_API_KEY", "")
    if not api_key:
        raise SpeechProviderError("GROQ_API_KEY belum diisi.", retryable=False)

    client = Groq(api_key=api_key)
    model_name = model or GROQ_STT_MODEL or os.getenv("GROQ_STT_MODEL", "whisper-large-v3-turbo")
    guessed_mime = _guess_mime_type(filename, mime_type)
    file_payload = (filename, bytes(audio_bytes), guessed_mime)

    try:
        transcription = client.audio.transcriptions.create(
            file=file_payload,
            model=model_name,
        )
    except Exception as e:
        raise SpeechProviderError(str(e), retryable=True)

    text = getattr(transcription, "text", None)
    if not text and isinstance(transcription, dict):
        text = transcription.get("text", "")

    text = (text or "").strip()
    if not text:
        raise SpeechProviderError("Transkrip suara kosong.", retryable=True)

    return text


async def transcribe_audio_bytes(
    audio_bytes: bytes,
    filename: str,
    mime_type: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    return await asyncio.to_thread(
        _transcribe_sync,
        audio_bytes,
        filename,
        mime_type,
        model,
    )
