from __future__ import annotations

from typing import Dict, List, Optional

from features.ai.gemini_pool import GeminiPoolExhausted, generate_reply as gemini_generate_reply
from features.ai.groq_provider import GroqAPIError, generate_reply as groq_generate_reply


class ProviderManagerError(RuntimeError):
    pass


async def generate_reply(
    provider: str,
    messages: List[Dict[str, str]],
    system_prompt: str,
) -> str:
    provider = (provider or "").strip().lower()

    if provider == "groq":
        try:
            return groq_generate_reply(messages=messages, model=None)
        except GroqAPIError as e:
            if e.retryable:
                try:
                    return groq_generate_reply(messages=messages, model=None)
                except Exception as e2:
                    raise ProviderManagerError(str(e2))
            raise ProviderManagerError(str(e))

    if provider == "gemini":
        try:
            return gemini_generate_reply(messages=messages, system_prompt=system_prompt, model=None)
        except GeminiPoolExhausted as e:
            raise ProviderManagerError(str(e))
        except Exception as e:
            raise ProviderManagerError(str(e))

    raise ProviderManagerError("Provider AI tidak dikenal.")
