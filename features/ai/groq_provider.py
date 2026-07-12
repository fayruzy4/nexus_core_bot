from __future__ import annotations

import os
from typing import Dict, List, Optional

from groq import Groq

from config import GROQ_API_KEY, GROQ_MODEL


class GroqAPIError(RuntimeError):
    def __init__(self, message: str, status_code: Optional[int] = None, retryable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


def generate_reply(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> str:
    api_key = api_key or GROQ_API_KEY or os.getenv("GROQ_API_KEY", "")
    if not api_key:
        raise GroqAPIError("GROQ_API_KEY belum diisi.", retryable=False)

    model = model or GROQ_MODEL or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    client = Groq(api_key=api_key)

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception as e:
        raise GroqAPIError(str(e), retryable=True)

    try:
        content = completion.choices[0].message.content or ""
    except Exception as e:
        raise GroqAPIError(str(e), retryable=True)

    content = str(content).strip()
    if not content:
        raise GroqAPIError("Konten Groq kosong.", retryable=True)
    return content
