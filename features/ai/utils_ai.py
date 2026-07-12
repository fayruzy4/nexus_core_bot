from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional


def normalize_text(text: str) -> str:
    return (text or "").strip()


def is_button(text: str, label: str) -> bool:
    return normalize_text(text) == label


def chunk_text(text: str, max_chars: int = 3500) -> List[str]:
    text = normalize_text(text)
    if not text:
        return [""]
    return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]


def role_to_openai(role: str) -> str:
    return role if role in {"system", "assistant", "user"} else "user"


def provider_label(provider: Optional[str]) -> str:
    if provider == "groq":
        return "Groq"
    if provider == "gemini":
        return "Gemini"
    return "-"


def render_ai_dashboard(active_provider: Optional[str], is_active: bool) -> str:
    status = "AKTIF" if is_active and active_provider else "NONAKTIF"
    provider = provider_label(active_provider)
    return (
        "━━━━━━━━━━━━━━\n"
        "🤖 NEXUS AI\n"
        "━━━━━━━━━━━━━━\n\n"
        f"Status: {status}\n"
        f"Provider: {provider}\n\n"
        "Pilih engine atau lanjutkan percakapan."
    )


def render_active_notice(provider: str) -> str:
    return (
        "Mode AI aktif.\n"
        f"Engine: {provider_label(provider)}\n\n"
        "Semua pesan berikutnya akan diproses sebagai percakapan AI."
    )


def render_reset_warning() -> str:
    return (
        "Reset Mode akan menghapus seluruh percakapan, memory, dan session AI.\n"
        "Lanjutkan?"
    )


def summarize_old_messages(messages: List[Dict[str, Any]], max_turns: int = 8) -> str:
    if not messages:
        return ""
    parts: List[str] = []
    for msg in messages[-max_turns:]:
        role = msg.get("role", "")
        content = normalize_text(msg.get("content", ""))
        if not content:
            continue
        snippet = content[:180].replace("\n", " ")
        parts.append(f"{role}: {snippet}")
    return "\n".join(parts)
