from __future__ import annotations

import asyncio
from typing import Dict, List

from features.ai.gemini_pool import GeminiPoolExhausted, generate_reply as gemini_generate_reply
from features.ai.groq_provider import GroqAPIError, generate_reply as groq_generate_reply


class ProviderManagerError(RuntimeError):
    pass


def _generate_sync(provider: str, messages: List[Dict[str, str]], system_prompt: str) -> str:
    provider = (provider or "").strip().lower()

    if provider == "groq":
        try:
            return groq_generate_reply(messages=messages)
        except GroqAPIError as e:
            if e.retryable:
                return groq_generate_reply(messages=messages)
            raise ProviderManagerError(str(e))

    if provider == "gemini":
        try:
            return gemini_generate_reply(messages=messages, system_prompt=system_prompt)
        except GeminiPoolExhausted as e:
            raise ProviderManagerError(str(e))
        except Exception as e:
            raise ProviderManagerError(str(e))

    raise ProviderManagerError("Provider AI tidak dikenal.")


async def generate_reply(provider: str, messages: List[Dict[str, str]], system_prompt: str) -> str:
    return await asyncio.to_thread(_generate_sync, provider, messages, system_prompt)
