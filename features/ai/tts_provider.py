from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional

import edge_tts

from config import TTS_RATE, TTS_VOICE_DEFAULT, TTS_VOLUME


class TTSProviderError(RuntimeError):
    pass


async def synthesize_speech(
    text: str,
    voice: Optional[str] = None,
    rate: Optional[str] = None,
    volume: Optional[str] = None,
) -> Path:
    text = (text or "").strip()
    if not text:
        raise TTSProviderError("Teks TTS kosong.")

    voice = voice or TTS_VOICE_DEFAULT or os.getenv("TTS_VOICE_DEFAULT", "id-ID-ArdiNeural")
    rate = rate or TTS_RATE or os.getenv("TTS_RATE", "0%")
    volume = volume or TTS_VOLUME or os.getenv("TTS_VOLUME", "+0%")

    fd, path = tempfile.mkstemp(prefix="nexus_tts_", suffix=".mp3")
    os.close(fd)
    output = Path(path)

    try:
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate=rate,
            volume=volume,
        )
        await communicate.save(str(output))
    except Exception as e:
        cleanup_audio_file(output)
        raise TTSProviderError(str(e))

    return output


def cleanup_audio_file(path: Optional[Path | str]) -> None:
    if not path:
        return
    try:
        p = Path(path)
        if p.exists():
            p.unlink(missing_ok=True)
    except Exception:
        pass
