from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

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

    def _load_keys(self) -> List[str]:
        keys: List[str] = []
        raw = os.getenv("GEMINI_API_KEYS", "").strip()
        if raw:
            keys.extend([k.strip() for k in raw.split(",") if k.strip()])

        for idx in range(1, 9):
            val = os.getenv(f"GEMINI_API_KEY_{idx}", "").strip()
            if val:
                keys.append(val)

        fallback = os.getenv("GEMINI_API_KEY", "").strip()
        if fallback and fallback not in keys:
            keys.append(fallback)

        uniq: List[str] = []
        for key in keys:
            if key and key not in uniq:
                uniq.append(key)
        return uniq[:4]

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _pick_indices(self) -> List[int]:
        n = len(self.keys)
        if n == 0:
            return []
        order = list(range(self.cursor, n)) + list(range(0, self.cursor))
        return order

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
        for idx in self._pick_indices():
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
                    self._cooldown(idx, retry_after_seconds=300 if e.status_code in {429, 403} else 120)
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
