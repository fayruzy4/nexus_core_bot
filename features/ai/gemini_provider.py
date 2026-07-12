from __future__ import annotations

import os
from typing import Dict, List, Optional

from google import genai

from config import GEMINI_MODEL


class GeminiAPIError(RuntimeError):
    def __init__(self, message: str, status_code: Optional[int] = None, retryable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


def generate_reply_with_key(
    api_key: str,
    messages: List[Dict[str, str]],
    system_prompt: str,
    model: Optional[str] = None,
    temperature: float = 1.0,
    max_output_tokens: int = 1024,
) -> str:
    if not api_key:
        raise GeminiAPIError("API key Gemini kosong.", retryable=False)

    model = model or GEMINI_MODEL or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    client = genai.Client(api_key=api_key)

    contents = []
    for msg in messages:
        role = msg.get("role", "user")
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        if role == "assistant":
            contents.append({"role": "model", "parts": [{"text": content}]})
        else:
            contents.append({"role": "user", "parts": [{"text": content}]})

    try:
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config={
                "system_instruction": system_prompt,
                "temperature": temperature,
                "max_output_tokens": max_output_tokens,
            },
        )
    except Exception as e:
        raise GeminiAPIError(str(e), retryable=True)

    text = getattr(response, "text", None)
    if not text:
        raise GeminiAPIError("Konten Gemini kosong.", retryable=True)
    return str(text).strip()
