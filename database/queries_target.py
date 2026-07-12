# queries_target.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from database.supabase import get_supabase


def _db():
    return get_supabase()


def _one(resp):
    data = getattr(resp, "data", None)
    if isinstance(data, list):
        return data[0] if data else None
    return data


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_schema() -> None:
    # Supabase/PostgreSQL schema dibuat lewat SQL migration, bukan dari runtime query.
    return None


def _normalize_target_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    nominal_target = int(payload.get("nominal_target", 0) or 0)
    nominal_awal = int(payload.get("nominal_awal", 0) or 0)
    dana_terkumpul = int(payload.get("dana_terkumpul", 0) or 0)

    if nominal_target <= 0:
        raise ValueError("nominal_target_invalid")
    if nominal_awal < 0:
        nominal_awal = 0
    if dana_terkumpul < 0:
        dana_terkumpul = 0

    payload["nominal_target"] = nominal_target
    payload["nominal_awal"] = nominal_awal
    payload["dana_terkumpul"] = dana_terkumpul

    if dana_terkumpul >= nominal_target:
        payload["status"] = "SELESAI"
        payload["completed_at"] = payload.get("completed_at") or _now_iso()
    else:
        payload["status"] = payload.get("status") or "AKTIF"
        payload["completed_at"] = None

    payload["updated_at"] = _now_iso()
    return payload


def create_target(
    user_id: int,
    nama_target: str,
    nominal_target: int,
    nominal_awal: int = 0,
    catatan: str = "",
) -> Dict[str, Any]:
    db = _db()
    payload = _normalize_target_payload(
        {
            "user_id": user_id,
            "nama_target": (nama_target or "").strip(),
            "nominal_target": int(nominal_target),
            "nominal_awal": max(0, int(nominal_awal)),
            "dana_terkumpul": max(0, int(nominal_awal)),
            "catatan": (catatan or "").strip() or None,
            "status": "AKTIF",
            "completed_at": None,
            "created_at": _now_iso(),
        }
    )

    res = (
        db.table("targets")
        .insert(
            {
                "user_id": payload["user_id"],
                "nama_target": payload["nama_target"],
                "nominal_target": payload["nominal_target"],
                "nominal_awal": payload["nominal_awal"],
                "dana_terkumpul": payload["dana_terkumpul"],
                "catatan": payload["catatan"],
                "status": payload["status"],
                "created_at": payload["created_at"],
                "completed_at": payload["completed_at"],
                "updated_at": payload["updated_at"],
            }
        )
        .execute()
        .data
    )
    return _one(res) or {}


def get_target_by_id(user_id: int, target_id: int) -> Optional[Dict[str, Any]]:
    db = _db()
    res = (
        db.table("targets")
        .select("*")
        .eq("user_id", user_id)
        .eq("id", target_id)
        .limit(1)
        .execute()
        .data
    )
    return res[0] if res else None


def list_targets(user_id: int, status: Optional[str] = None) -> List[Dict[str, Any]]:
    db = _db()
    q = db.table("targets").select("*").eq("user_id", user_id)
    if status:
        q = q.eq("status", status)
    res = q.order("created_at", desc=True).order("id", desc=True).execute().data or []
    return res


def list_active_targets(user_id: int) -> List[Dict[str, Any]]:
    return list_targets(user_id, "AKTIF")


def list_done_targets(user_id: int) -> List[Dict[str, Any]]:
    return list_targets(user_id, "SELESAI")


def get_target_summary(user_id: int) -> Dict[str, Any]:
    rows = list_targets(user_id)

    jumlah_aktif = sum(1 for r in rows if (r.get("status") or "") == "AKTIF")
    jumlah_selesai = sum(1 for r in rows if (r.get("status") or "") == "SELESAI")
    total_nominal_target = sum(int(r.get("nominal_target") or 0) for r in rows)
    total_dana_terkumpul = sum(int(r.get("dana_terkumpul") or 0) for r in rows)
    total_sisa = sum(
        max(int(r.get("nominal_target") or 0) - int(r.get("dana_terkumpul") or 0), 0)
        for r in rows
    )

    progress = round((total_dana_terkumpul / total_nominal_target) * 100, 1) if total_nominal_target > 0 else 0.0
    progress = min(progress, 100.0)

    return {
        "total_target": len(rows),
        "jumlah_aktif": jumlah_aktif,
        "jumlah_selesai": jumlah_selesai,
        "total_nominal_target": total_nominal_target,
        "total_dana_terkumpul": total_dana_terkumpul,
        "total_sisa": total_sisa,
        "progress": progress,
    }


def update_target_full(
    user_id: int,
    target_id: int,
    *,
    nama_target: str,
    nominal_target: int,
    nominal_awal: int,
    dana_terkumpul: int,
    catatan: Optional[str],
) -> Optional[Dict[str, Any]]:
    db = _db()

    nama_target = (nama_target or "").strip()
    nominal_target = int(nominal_target or 0)
    nominal_awal = max(0, int(nominal_awal or 0))
    dana_terkumpul = max(0, int(dana_terkumpul or 0))
    catatan_value = (catatan or "").strip() or None

    if nominal_target <= 0:
        raise ValueError("nominal_target_invalid")

    status = "SELESAI" if dana_terkumpul >= nominal_target else "AKTIF"
    completed_at = _now_iso() if status == "SELESAI" else None

    res = (
        db.table("targets")
        .update(
            {
                "nama_target": nama_target,
                "nominal_target": nominal_target,
                "nominal_awal": nominal_awal,
                "dana_terkumpul": dana_terkumpul,
                "catatan": catatan_value,
                "status": status,
                "completed_at": completed_at,
                "updated_at": _now_iso(),
            }
        )
        .eq("user_id", user_id)
        .eq("id", target_id)
        .execute()
        .data
    )
    return _one(res)


def change_target_balance(
    user_id: int,
    target_id: int,
    delta: int,
) -> Optional[Dict[str, Any]]:
    target = get_target_by_id(user_id, target_id)
    if not target:
        return None

    current = int(target.get("dana_terkumpul") or 0)
    new_total = current + int(delta)
    if new_total < 0:
        raise ValueError("dana_terkumpul_negative")

    return update_target_full(
        user_id,
        target_id,
        nama_target=target.get("nama_target") or "",
        nominal_target=int(target.get("nominal_target") or 0),
        nominal_awal=int(target.get("nominal_awal") or 0),
        dana_terkumpul=new_total,
        catatan=target.get("catatan"),
    )


def delete_target(user_id: int, target_id: int) -> bool:
    db = _db()
    res = (
        db.table("targets")
        .delete()
        .eq("user_id", user_id)
        .eq("id", target_id)
        .execute()
    )
    data = getattr(res, "data", None)
    return bool(data)
