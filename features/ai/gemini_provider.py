from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from config import GEMINI_MODEL


class GeminiAPIError(RuntimeError):
    def __init__(self, message: str, status_code: Optional[int] = None, retryable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


def _post_json(url: str, headers: Dict[str, str], payload: Dict[str, Any], timeout: int = 60) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="ignore")
        retryable = e.code in {429, 500, 502, 503, 504}
        raise GeminiAPIError(raw or str(e), status_code=e.code, retryable=retryable)
    except urllib.error.URLError as e:
        raise GeminiAPIError(str(e), retryable=True)


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
    base_url = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
    url = f"{base_url}/models/{model}:generateContent?key={api_key}"

    system_parts: List[str] = [system_prompt.strip()] if system_prompt and system_prompt.strip() else []
    contents: List[Dict[str, Any]] = []

    for msg in messages:
        role = (msg.get("role") or "user").strip().lower()
        content = (msg.get("content") or "").strip()
        if not content:
            continue

        if role == "system":
            system_parts.append(content)
            continue

        contents.append(
            {
                "role": "model" if role == "assistant" else "user",
                "parts": [{"text": content}],
            }
        )

    system_instruction_text = "\n\n".join(part for part in system_parts if part).strip()

    payload = {
        "system_instruction": {"parts": [{"text": system_instruction_text}]},
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
        },
    }

    data = _post_json(
        url,
        {"Content-Type": "application/json"},
        payload,
    )

    candidates = data.get("candidates") or []
    if not candidates:
        raise GeminiAPIError("Respons Gemini kosong.", retryable=True)

    candidate = candidates[0]
    content = candidate.get("content") or {}
    parts = content.get("parts") or []
    texts = [part.get("text", "") for part in parts if isinstance(part, dict)]
    reply = "\n".join(t for t in texts if t).strip()

    if not reply:
        raise GeminiAPIError("Konten Gemini kosong.", retryable=True)

    return reply
