# queries_target.py
from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor

DB_DSN_ENV_VARS = [
    "DATABASE_URL",
    "POSTGRES_URL",
    "SUPABASE_DATABASE_URL",
    "SUPABASE_DB_URL",
    "NEXUS_DATABASE_URL",
    "NEXUS_CORE_DATABASE_URL",
]

TABLE_SQL = """
CREATE TABLE IF NOT EXISTS targets (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    nama_target TEXT NOT NULL,
    nominal_target BIGINT NOT NULL CHECK (nominal_target > 0),
    nominal_awal BIGINT NOT NULL DEFAULT 0 CHECK (nominal_awal >= 0),
    dana_terkumpul BIGINT NOT NULL DEFAULT 0 CHECK (dana_terkumpul >= 0),
    catatan TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'AKTIF'
        CHECK (status IN ('AKTIF', 'SELESAI')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT targets_completed_at_check
        CHECK (
            (status = 'AKTIF' AND completed_at IS NULL)
            OR (status = 'SELESAI' AND completed_at IS NOT NULL)
        )
);
"""

INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_targets_user_status_created ON targets(user_id, status, created_at);",
    "CREATE INDEX IF NOT EXISTS idx_targets_user_id ON targets(user_id);",
]


def _resolve_dsn() -> str:
    for name in DB_DSN_ENV_VARS:
        value = os.environ.get(name)
        if value:
            return value

    host = os.environ.get("PGHOST")
    dbname = os.environ.get("PGDATABASE")
    user = os.environ.get("PGUSER")
    password = os.environ.get("PGPASSWORD")
    port = os.environ.get("PGPORT")

    if host and dbname and user:
        parts = [
            f"host={host}",
            f"dbname={dbname}",
            f"user={user}",
        ]
        if password:
            parts.append(f"password={password}")
        if port:
            parts.append(f"port={port}")
        return " ".join(parts)

    raise RuntimeError(
        "DSN PostgreSQL belum ditemukan. Set DATABASE_URL / POSTGRES_URL / SUPABASE_DATABASE_URL "
        "atau PGHOST, PGDATABASE, PGUSER, PGPASSWORD."
    )


@contextmanager
def _connect():
    conn = psycopg2.connect(_resolve_dsn())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _row_to_dict(row: Any) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    return dict(row)


def ensure_schema() -> None:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(TABLE_SQL)
            for sql in INDEX_SQL:
                cur.execute(sql)


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
            "nama_target": (nama_target or "").strip(),
            "nominal_target": int(nominal_target),
            "nominal_awal": max(0, int(nominal_awal)),
            "dana_terkumpul": max(0, int(nominal_awal)),
            "catatan": (catatan or "").strip() or None,
            "status": "AKTIF",
            "completed_at": None,
            "created_at": _now(),
        }
    )

    with _connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO targets (
                    user_id, nama_target, nominal_target, nominal_awal, dana_terkumpul,
                    catatan, status, created_at, completed_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
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
            row = cur.fetchone()
    return dict(row)


def get_target_by_id(user_id: int, target_id: int) -> Optional[Dict[str, Any]]:
    ensure_schema()
    with _connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM targets WHERE id = %s AND user_id = %s",
                (target_id, user_id),
            )
            row = cur.fetchone()
    return _row_to_dict(row)


def list_targets(user_id: int, status: Optional[str] = None) -> List[Dict[str, Any]]:
    ensure_schema()
    query = "SELECT * FROM targets WHERE user_id = %s"
    params: List[Any] = [user_id]

    if status:
        query += " AND status = %s"
        params.append(status)

    query += " ORDER BY created_at DESC, id DESC"

    with _connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
    return [dict(row) for row in rows]


def list_active_targets(user_id: int) -> List[Dict[str, Any]]:
    return list_targets(user_id, "AKTIF")


def list_done_targets(user_id: int) -> List[Dict[str, Any]]:
    return list_targets(user_id, "SELESAI")


def get_target_summary(user_id: int) -> Dict[str, Any]:
    ensure_schema()
    with _connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) AS total_target,
                    COALESCE(SUM(CASE WHEN status = 'AKTIF' THEN 1 ELSE 0 END), 0) AS jumlah_aktif,
                    COALESCE(SUM(CASE WHEN status = 'SELESAI' THEN 1 ELSE 0 END), 0) AS jumlah_selesai,
                    COALESCE(SUM(nominal_target), 0) AS total_nominal_target,
                    COALESCE(SUM(dana_terkumpul), 0) AS total_dana_terkumpul,
                    COALESCE(
                        SUM(
                            CASE
                                WHEN nominal_target - dana_terkumpul > 0
                                THEN nominal_target - dana_terkumpul
                                ELSE 0
                            END
                        ),
                        0
                    ) AS total_sisa
                FROM targets
                WHERE user_id = %s
                """,
                (user_id,),
            )
            row = cur.fetchone() or {}

    result = dict(row)
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
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                UPDATE targets
                SET nama_target = %s,
                    nominal_target = %s,
                    nominal_awal = %s,
                    dana_terkumpul = %s,
                    catatan = %s,
                    status = %s,
                    completed_at = %s,
                    updated_at = %s
                WHERE id = %s AND user_id = %s
                RETURNING *
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
            row = cur.fetchone()
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
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM targets WHERE id = %s AND user_id = %s",
                (target_id, user_id),
            )
            return cur.rowcount > 0


ensure_schema()
