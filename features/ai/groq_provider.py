from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional


class GroqAPIError(RuntimeError):
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
        raise GroqAPIError(raw or str(e), status_code=e.code, retryable=retryable)
    except urllib.error.URLError as e:
        raise GroqAPIError(str(e), retryable=True)


def generate_reply(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> str:
    api_key = api_key or os.getenv("GROQ_API_KEY", "")
    if not api_key:
        raise GroqAPIError("GROQ_API_KEY belum diset.", retryable=False)

    model = model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    data = _post_json(
        url,
        {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        payload,
    )
    choices = data.get("choices") or []
    if not choices:
        raise GroqAPIError("Respons Groq kosong.", retryable=True)
    message = choices[0].get("message") or {}
    content = message.get("content") or ""
    if not content:
        raise GroqAPIError("Konten Groq kosong.", retryable=True)
    return str(content).strip()
