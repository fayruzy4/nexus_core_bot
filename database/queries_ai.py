from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from database.supabase import get_supabase


def _db():
    return get_supabase()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rows(resp) -> List[Dict[str, Any]]:
    data = getattr(resp, "data", None)
    if not data:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    return []


def _one(resp) -> Optional[Dict[str, Any]]:
    rows = _rows(resp)
    return rows[0] if rows else None


def ensure_schema() -> None:
    return None


def get_session_by_user_id(user_id: int) -> Optional[Dict[str, Any]]:
    db = _db()
    resp = (
        db.table("ai_sessions")
        .select("*")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    return _one(resp)


def create_session(user_id: int) -> Dict[str, Any]:
    db = _db()
    resp = (
        db.table("ai_sessions")
        .insert(
            {
                "user_id": user_id,
                "active_provider": None,
                "is_active": False,
                "created_at": _now(),
                "updated_at": _now(),
            }
        )
        .execute()
    )
    row = _one(resp)
    return row or get_session_by_user_id(user_id) or {}


def get_or_create_session(user_id: int) -> Dict[str, Any]:
    session = get_session_by_user_id(user_id)
    if session:
        return session
    return create_session(user_id)


def set_session_provider(user_id: int, provider: Optional[str], is_active: bool) -> Dict[str, Any]:
    db = _db()
    payload = {
        "user_id": user_id,
        "active_provider": provider,
        "is_active": bool(is_active),
        "updated_at": _now(),
    }
    resp = db.table("ai_sessions").upsert(payload).execute()
    row = _one(resp)
    if row:
        return row
    return get_or_create_session(user_id)


def deactivate_session(user_id: int) -> Dict[str, Any]:
    return set_session_provider(user_id, None, False)


def delete_session(user_id: int) -> None:
    db = _db()
    db.table("ai_sessions").delete().eq("user_id", user_id).execute()


def add_message(
    session_id: int,
    user_id: int,
    role: str,
    content: str,
    provider: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    db = _db()
    resp = (
        db.table("ai_messages")
        .insert(
            {
                "session_id": session_id,
                "user_id": user_id,
                "role": role,
                "provider": provider,
                "content": content,
                "created_at": _now(),
            }
        )
        .execute()
    )
    return _one(resp)


def list_messages(session_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    db = _db()
    resp = (
        db.table("ai_messages")
        .select("*")
        .eq("session_id", session_id)
        .order("created_at", desc=False)
        .limit(limit)
        .execute()
    )
    return _rows(resp)


def add_summary(session_id: int, summary_text: str) -> Optional[Dict[str, Any]]:
    db = _db()
    resp = (
        db.table("ai_memory_summaries")
        .insert(
            {
                "session_id": session_id,
                "summary_text": summary_text,
                "created_at": _now(),
            }
        )
        .execute()
    )
    return _one(resp)


def get_latest_summary(session_id: int) -> str:
    db = _db()
    resp = (
        db.table("ai_memory_summaries")
        .select("*")
        .eq("session_id", session_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    row = _one(resp)
    return (row or {}).get("summary_text", "") or ""


def clear_user_ai_data(user_id: int) -> None:
    session = get_session_by_user_id(user_id)
    if not session:
        return
    session_id = session["id"]
    db = _db()
    db.table("ai_messages").delete().eq("session_id", session_id).execute()
    db.table("ai_memory_summaries").delete().eq("session_id", session_id).execute()
    delete_session(user_id)


def get_provider_state(provider_name: str) -> Optional[Dict[str, Any]]:
    db = _db()
    resp = (
        db.table("ai_provider_state")
        .select("*")
        .eq("provider_name", provider_name)
        .limit(1)
        .execute()
    )
    return _one(resp)


def upsert_provider_state(
    provider_name: str,
    api_index: int,
    cooldown_until: Optional[str] = None,
    failure_count: int = 0,
    last_error_message: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    db = _db()
    payload = {
        "provider_name": provider_name,
        "api_index": api_index,
        "cooldown_until": cooldown_until,
        "failure_count": failure_count,
        "last_used_at": _now(),
        "last_error_at": _now() if last_error_message else None,
        "last_error_message": last_error_message,
        "updated_at": _now(),
    }
    resp = db.table("ai_provider_state").upsert(payload).execute()
    return _one(resp)


def reset_provider_state(provider_name: str) -> Optional[Dict[str, Any]]:
    return upsert_provider_state(provider_name=provider_name, api_index=0, cooldown_until=None, failure_count=0)
