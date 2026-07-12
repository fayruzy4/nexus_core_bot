from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

DB_PATH_CANDIDATES = [
    os.environ.get("NEXUS_CORE_DB_PATH"),
    os.environ.get("NEXUS_DB_PATH"),
    os.environ.get("DATABASE_PATH"),
    os.environ.get("DB_PATH"),
    "nexus_core.db",
    "nexus.db",
]

TABLE_SQL = """
CREATE TABLE IF NOT EXISTS targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    nama_target TEXT NOT NULL,
    nominal_target INTEGER NOT NULL,
    nominal_awal INTEGER NOT NULL DEFAULT 0,
    dana_terkumpul INTEGER NOT NULL DEFAULT 0,
    catatan TEXT,
    status TEXT NOT NULL CHECK (status IN ('AKTIF', 'SELESAI')),
    created_at TEXT NOT NULL,
    completed_at TEXT,
    updated_at TEXT NOT NULL
);
"""

INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_targets_user_status_created ON targets(user_id, status, created_at);",
    "CREATE INDEX IF NOT EXISTS idx_targets_user_id ON targets(user_id);",
]


def _resolve_db_path() -> str:
    for path in DB_PATH_CANDIDATES:
        if path:
            return path
    return "nexus_core.db"


@contextmanager
def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_resolve_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _row_to_dict(row: sqlite3.Row | None) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    return dict(row)


def ensure_schema() -> None:
    with _connect() as conn:
        conn.execute(TABLE_SQL)
        for sql in INDEX_SQL:
            conn.execute(sql)


def _normalize_target_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    dana = int(payload.get("dana_terkumpul", 0) or 0)
    target = int(payload.get("nominal_target", 0) or 0)
    if dana < 0:
        dana = 0
    if target < 0:
        target = 0
    if target > 0 and dana >= target:
        payload["status"] = "SELESAI"
        payload["completed_at"] = payload.get("completed_at") or _now()
        payload["dana_terkumpul"] = dana
    else:
        payload["status"] = payload.get("status") or "AKTIF"
        payload["completed_at"] = None
        payload["dana_terkumpul"] = dana
    payload["updated_at"] = _now()
    return payload


def create_target(
    user_id: int,
    nama_target: str,
    nominal_target: int,
    nominal_awal: int = 0,
    catatan: str = "",
) -> Dict[str, Any]:
    ensure_schema()
    payload = _normalize_target_payload(
        {
            "nama_target": nama_target.strip(),
            "nominal_target": int(nominal_target),
            "nominal_awal": max(0, int(nominal_awal)),
            "dana_terkumpul": max(0, int(nominal_awal)),
            "catatan": catatan.strip() or None,
            "status": "AKTIF",
            "completed_at": None,
            "created_at": _now(),
        }
    )

    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO targets (
                user_id, nama_target, nominal_target, nominal_awal, dana_terkumpul,
                catatan, status, created_at, completed_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                payload["nama_target"],
                payload["nominal_target"],
                payload["nominal_awal"],
                payload["dana_terkumpul"],
                payload["catatan"],
                payload["status"],
                payload["created_at"],
                payload["completed_at"],
                payload["updated_at"],
            ),
        )
        row = conn.execute(
            "SELECT * FROM targets WHERE id = ? AND user_id = ?",
            (cur.lastrowid, user_id),
        ).fetchone()
    return dict(row)


def get_target_by_id(user_id: int, target_id: int) -> Optional[Dict[str, Any]]:
    ensure_schema()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM targets WHERE id = ? AND user_id = ?",
            (target_id, user_id),
        ).fetchone()
    return _row_to_dict(row)


def list_targets(user_id: int, status: Optional[str] = None) -> List[Dict[str, Any]]:
    ensure_schema()
    query = "SELECT * FROM targets WHERE user_id = ?"
    params: List[Any] = [user_id]
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY datetime(created_at) DESC, id DESC"
    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def list_active_targets(user_id: int) -> List[Dict[str, Any]]:
    return list_targets(user_id, "AKTIF")


def list_done_targets(user_id: int) -> List[Dict[str, Any]]:
    return list_targets(user_id, "SELESAI")


def get_target_summary(user_id: int) -> Dict[str, Any]:
    ensure_schema()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS total_target,
                COALESCE(SUM(CASE WHEN status = 'AKTIF' THEN 1 ELSE 0 END), 0) AS jumlah_aktif,
                COALESCE(SUM(CASE WHEN status = 'SELESAI' THEN 1 ELSE 0 END), 0) AS jumlah_selesai,
                COALESCE(SUM(nominal_target), 0) AS total_nominal_target,
                COALESCE(SUM(dana_terkumpul), 0) AS total_dana_terkumpul,
                COALESCE(SUM(CASE WHEN nominal_target - dana_terkumpul > 0 THEN nominal_target - dana_terkumpul ELSE 0 END), 0) AS total_sisa
            FROM targets
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
    result = dict(row or {})
    if not result:
        result = {
            "total_target": 0,
            "jumlah_aktif": 0,
            "jumlah_selesai": 0,
            "total_nominal_target": 0,
            "total_dana_terkumpul": 0,
            "total_sisa": 0,
        }
    total_target = int(result.get("total_nominal_target", 0) or 0)
    total_gathered = int(result.get("total_dana_terkumpul", 0) or 0)
    progress = round((total_gathered / total_target) * 100, 1) if total_target > 0 else 0.0
    result["progress"] = min(progress, 100.0)
    return result


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
    ensure_schema()
    nama_target = (nama_target or "").strip()
    nominal_target = max(0, int(nominal_target))
    nominal_awal = max(0, int(nominal_awal))
    dana_terkumpul = max(0, int(dana_terkumpul))
    catatan_value = (catatan or "").strip() or None

    status = "SELESAI" if nominal_target > 0 and dana_terkumpul >= nominal_target else "AKTIF"
    completed_at = _now() if status == "SELESAI" else None
    updated_at = _now()

    with _connect() as conn:
        conn.execute(
            """
            UPDATE targets
            SET nama_target = ?,
                nominal_target = ?,
                nominal_awal = ?,
                dana_terkumpul = ?,
                catatan = ?,
                status = ?,
                completed_at = ?,
                updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                nama_target,
                nominal_target,
                nominal_awal,
                dana_terkumpul,
                catatan_value,
                status,
                completed_at,
                updated_at,
                target_id,
                user_id,
            ),
        )
        row = conn.execute(
            "SELECT * FROM targets WHERE id = ? AND user_id = ?",
            (target_id, user_id),
        ).fetchone()
    return _row_to_dict(row)


def change_target_balance(
    user_id: int,
    target_id: int,
    delta: int,
) -> Optional[Dict[str, Any]]:
    ensure_schema()
    target = get_target_by_id(user_id, target_id)
    if not target:
        return None

    current = int(target.get("dana_terkumpul", 0) or 0)
    new_total = current + int(delta)
    if new_total < 0:
        raise ValueError("dana_terkumpul_negative")

    return update_target_full(
        user_id,
        target_id,
        nama_target=target["nama_target"],
        nominal_target=int(target["nominal_target"]),
        nominal_awal=int(target["nominal_awal"]),
        dana_terkumpul=new_total,
        catatan=target.get("catatan"),
    )


def delete_target(user_id: int, target_id: int) -> bool:
    ensure_schema()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM targets WHERE id = ? AND user_id = ?",
            (target_id, user_id),
        )
    return cur.rowcount > 0


ensure_schema()
