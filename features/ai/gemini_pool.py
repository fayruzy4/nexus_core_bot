from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Dict, List, Optional

from config import GEMINI_API_KEYS
from features.ai.gemini_provider import GeminiAPIError, generate_reply_with_key


@dataclass
class _KeyState:
    cooldown_until: Optional[datetime] = None
    failure_count: int = 0


class GeminiPoolExhausted(RuntimeError):
    pass


class GeminiPool:
    def __init__(self) -> None:
        self.keys: List[str] = self._load_keys()
        self.states: Dict[int, _KeyState] = {i: _KeyState() for i in range(len(self.keys))}
        self.cursor: int = 0
        self._lock = Lock()

    def _load_keys(self) -> List[str]:
        keys = [k.strip() for k in GEMINI_API_KEYS if k and k.strip()]
        return keys[:4]

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _ordered_indices(self) -> List[int]:
        with self._lock:
            start = self.cursor
        n = len(self.keys)
        if n == 0:
            return []
        return list(range(start, n)) + list(range(0, start))

    def _is_available(self, idx: int) -> bool:
        state = self.states[idx]
        if state.cooldown_until is None:
            return True
        return self._now() >= state.cooldown_until

    def _cooldown(self, idx: int, retry_after_seconds: int = 300) -> None:
        state = self.states[idx]
        state.cooldown_until = self._now() + timedelta(seconds=retry_after_seconds)
        state.failure_count += 1

    def _mark_success(self, idx: int) -> None:
        state = self.states[idx]
        state.cooldown_until = None
        state.failure_count = 0
        with self._lock:
            self.cursor = (idx + 1) % len(self.keys) if self.keys else 0

    def generate_reply(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
        model: Optional[str] = None,
        temperature: float = 1.0,
        max_output_tokens: int = 1024,
    ) -> str:
        if not self.keys:
            raise GeminiPoolExhausted("Tidak ada API key Gemini yang tersedia.")

        last_error: Optional[Exception] = None

        for idx in self._ordered_indices():
            if not self._is_available(idx):
                continue
            try:
                reply = generate_reply_with_key(
                    api_key=self.keys[idx],
                    messages=messages,
                    system_prompt=system_prompt,
                    model=model,
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                )
                self._mark_success(idx)
                return reply
            except GeminiAPIError as e:
                last_error = e
                if e.retryable:
                    cooldown = 300 if e.status_code in {429, 403} else 120
                    self._cooldown(idx, retry_after_seconds=cooldown)
                    continue
                raise

        if last_error and isinstance(last_error, GeminiAPIError) and last_error.retryable:
            raise GeminiPoolExhausted(
                "Gemini sedang mencapai batas penggunaan.\nSilakan gunakan Groq atau coba lagi nanti."
            )

        raise GeminiPoolExhausted(
            "Gemini sedang mencapai batas penggunaan.\nSilakan gunakan Groq atau coba lagi nanti."
        )


_POOL = GeminiPool()


def generate_reply(messages: List[Dict[str, str]], system_prompt: str, model: Optional[str] = None) -> str:
    return _POOL.generate_reply(messages=messages, system_prompt=system_prompt, model=model)
