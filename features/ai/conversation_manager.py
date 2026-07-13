from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from database.queries_ai import (
    add_message,
    add_summary,
    clear_user_ai_data,
    get_latest_summary,
    get_or_create_session,
    get_session_by_user_id,
    list_messages,
    reset_provider_state,
    set_session_provider,
)
from features.ai.gemini_pool import reset_pool_state as reset_gemini_pool_state


def ensure_session(user_id: int) -> Dict[str, Any]:
    return get_or_create_session(user_id)


def get_session(user_id: int) -> Optional[Dict[str, Any]]:
    return get_session_by_user_id(user_id)


def activate_provider(user_id: int, provider: str) -> Dict[str, Any]:
    ensure_session(user_id)
    return set_session_provider(user_id, provider, True)


def deactivate_provider(user_id: int) -> Dict[str, Any]:
    return set_session_provider(user_id, None, False)


def append_user_message(user_id: int, content: str) -> Optional[Dict[str, Any]]:
    session = ensure_session(user_id)
    return add_message(session["id"], user_id, "user", content, session.get("active_provider"))


def append_assistant_message(user_id: int, content: str, provider: str) -> Optional[Dict[str, Any]]:
    session = ensure_session(user_id)
    return add_message(session["id"], user_id, "assistant", content, provider)


def append_system_message(user_id: int, content: str) -> Optional[Dict[str, Any]]:
    session = ensure_session(user_id)
    return add_message(session["id"], user_id, "system", content, None)


def get_history(user_id: int, limit: int = 40) -> Tuple[Dict[str, Any], List[Dict[str, Any]], str]:
    session = ensure_session(user_id)
    history = list_messages(session["id"], limit=limit)
    summary = get_latest_summary(session["id"])
    return session, history, summary


def store_summary(user_id: int, summary_text: str) -> Optional[Dict[str, Any]]:
    session = ensure_session(user_id)
    return add_summary(session["id"], summary_text)


def reset_runtime_state() -> None:
    reset_provider_state("groq")
    reset_gemini_pool_state()


def reset_user_ai(user_id: int) -> None:
    clear_user_ai_data(user_id)


def session_is_active(user_id: int) -> bool:
    session = get_session(user_id)
    return bool(session and session.get("is_active") and session.get("active_provider"))


def current_provider(user_id: int) -> Optional[str]:
    session = get_session(user_id)
    if not session:
        return None
    return session.get("active_provider")
