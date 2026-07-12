from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from database.supabase import get_supabase
from config import INCOME_CATEGORIES, EXPENSE_CATEGORIES

def _db():
    return get_supabase()

def _one(resp):
    data = getattr(resp, "data", None)
    if isinstance(data, list):
        return data[0] if data else None
    return data

def seed_default_categories() -> None:
    db = _db()
    existing = (
    db.table("categories")
    .select("id")
    .is_("user_id", None)
    .limit(1)
    .execute()
    .data
    )
    if existing:
        return

    rows = []
    for urutan, (emoji, nama) in enumerate(INCOME_CATEGORIES):
        rows.append({
            "user_id": None,
            "nama": nama,
            "emoji": emoji,
            "jenis_transaksi": "pemasukan",
            "urutan": urutan,
        })
    for urutan, (emoji, nama) in enumerate(EXPENSE_CATEGORIES):
        rows.append({
            "user_id": None,
            "nama": nama,
            "emoji": emoji,
            "jenis_transaksi": "pengeluaran",
            "urutan": urutan,
        })
    if rows:
        db.table("categories").insert(rows).execute()

def get_or_create_user(telegram_id: int, username: str | None, nama: str | None) -> Dict[str, Any]:
    db = _db()
    existing = db.table("users").select("*").eq("telegram_id", telegram_id).limit(1).execute().data
    if existing:
        user = existing[0]
        db.table("users").update({
            "username": username,
            "nama": nama,
            "updated_at": datetime.utcnow().isoformat(),
        }).eq("id", user["id"]).execute()
        user.update({"username": username, "nama": nama})
        return user

    inserted = db.table("users").insert({
        "telegram_id": telegram_id,
        "username": username,
        "nama": nama,
        "saldo_awal": 0,
    }).execute().data
    return inserted[0]

def get_user_by_telegram_id(telegram_id: int) -> Optional[Dict[str, Any]]:
    db = _db()
    res = db.table("users").select("*").eq("telegram_id", telegram_id).limit(1).execute().data
    return res[0] if res else None

def set_initial_balance(user_id: int, balance: int) -> None:
    db = _db()
    db.table("users").update({
        "saldo_awal": balance,
        "updated_at": datetime.utcnow().isoformat(),
    }).eq("id", user_id).execute()

def get_categories(user_id: int, jenis_transaksi: str | None = None) -> List[Dict[str, Any]]:
    db = _db()
    q = db.table("categories").select("*").order("urutan", desc=False)
    res = q.or_(f"user_id.eq.{user_id},user_id.is.null").execute().data
    rows = res or []
    if jenis_transaksi:
        rows = [r for r in rows if r["jenis_transaksi"] == jenis_transaksi]
    if rows:
        return rows
    return [
        {"nama": nama, "emoji": emoji, "jenis_transaksi": jenis_transaksi or "pengeluaran"}
        for emoji, nama in (EXPENSE_CATEGORIES if jenis_transaksi == "pengeluaran" else INCOME_CATEGORIES)
    ]

def create_transaction(user_id: int, jenis: str, nominal: int, kategori: str, catatan: str | None, tanggal_transaksi: str) -> Dict[str, Any]:
    db = _db()
    res = db.table("transactions").insert({
        "user_id": user_id,
        "jenis": jenis,
        "nominal": nominal,
        "kategori": kategori,
        "catatan": catatan,
        "tanggal_transaksi": tanggal_transaksi,
    }).execute().data
    return res[0]

def update_transaction(tx_id: int, fields: Dict[str, Any]) -> Dict[str, Any]:
    db = _db()
    res = db.table("transactions").update({
        **fields,
        "updated_at": datetime.utcnow().isoformat(),
    }).eq("id", tx_id).execute().data
    return res[0]

def delete_transaction(tx_id: int) -> None:
    db = _db()
    db.table("transactions").delete().eq("id", tx_id).execute()

def get_transaction_by_id(user_id: int, tx_id: int) -> Optional[Dict[str, Any]]:
    db = _db()
    res = db.table("transactions").select("*").eq("user_id", user_id).eq("id", tx_id).limit(1).execute().data
    return res[0] if res else None

def list_transactions(user_id: int, start_date: str | None = None, end_date: str | None = None, search: str | None = None) -> List[Dict[str, Any]]:
    db = _db()
    q = db.table("transactions").select("*").eq("user_id", user_id).order("tanggal_transaksi", desc=True).order("id", desc=True)
    if start_date:
        q = q.gte("tanggal_transaksi", start_date)
    if end_date:
        q = q.lte("tanggal_transaksi", end_date)
    rows = q.execute().data or []
    if search:
        s = search.lower()
        rows = [
            r for r in rows
            if s in (r.get("kategori") or "").lower()
            or s in (r.get("catatan") or "").lower()
            or s in (r.get("jenis") or "").lower()
        ]
    return rows

def get_user_summary(user_id: int) -> Dict[str, Any]:
    db = _db()
    user = db.table("users").select("*").eq("id", user_id).limit(1).execute().data[0]
    rows = list_transactions(user_id)
    income = sum(int(r["nominal"]) for r in rows if r["jenis"] == "pemasukan")
    expense = sum(int(r["nominal"]) for r in rows if r["jenis"] == "pengeluaran")
    return {
        "saldo_awal": int(user["saldo_awal"] or 0),
        "pemasukan": income,
        "pengeluaran": expense,
        "saldo": int(user["saldo_awal"] or 0) + income - expense,
        "jumlah_transaksi": len(rows),
    }

def get_report_rows(user_id: int, start_date: str, end_date: str) -> List[Dict[str, Any]]:
    return list_transactions(user_id, start_date=start_date, end_date=end_date)

def reset_user_data(user_id: int) -> None:
    db = _db()
    db.table("transactions").delete().eq("user_id", user_id).execute()
    db.table("categories").delete().eq("user_id", user_id).execute()
    db.table("settings").delete().eq("user_id", user_id).execute()
    db.table("users").update({
        "saldo_awal": 0,
        "updated_at": datetime.utcnow().isoformat(),
    }).eq("id", user_id).execute()

def export_user_bundle(user_id: int) -> Dict[str, Any]:
    db = _db()
    user = db.table("users").select("*").eq("id", user_id).limit(1).execute().data[0]
    transactions = list_transactions(user_id)
    categories = db.table("categories").select("*").or_(f"user_id.eq.{user_id},user_id.is.null").order("urutan").execute().data or []
    settings = db.table("settings").select("*").eq("user_id", user_id).execute().data or []
    return {
        "user": user,
        "transactions": transactions,
        "categories": categories,
        "settings": settings,
    }

def import_user_bundle(user_id: int, payload: Dict[str, Any]) -> None:
    db = _db()
    db.table("transactions").delete().eq("user_id", user_id).execute()
    db.table("categories").delete().eq("user_id", user_id).execute()
    db.table("settings").delete().eq("user_id", user_id).execute()

    user_data = payload.get("user") or {}
    if "saldo_awal" in user_data:
        db.table("users").update({
            "saldo_awal": int(user_data.get("saldo_awal") or 0),
            "updated_at": datetime.utcnow().isoformat(),
        }).eq("id", user_id).execute()

    categories = payload.get("categories") or []
    cat_rows = []
    for c in categories:
        if c.get("user_id") is None:
            continue
        cat_rows.append({
            "user_id": user_id,
            "nama": c.get("nama"),
            "emoji": c.get("emoji", ""),
            "jenis_transaksi": c.get("jenis_transaksi"),
            "urutan": int(c.get("urutan") or 0),
        })
    if cat_rows:
        db.table("categories").insert(cat_rows).execute()

    settings = payload.get("settings") or []
    set_rows = []
    for s in settings:
        set_rows.append({
            "user_id": user_id,
            "key": s.get("key"),
            "value": s.get("value"),
        })
    if set_rows:
        db.table("settings").insert(set_rows).execute()

    tx_rows = []
    for t in payload.get("transactions") or []:
        tx_rows.append({
            "user_id": user_id,
            "jenis": t.get("jenis"),
            "nominal": int(t.get("nominal") or 0),
            "kategori": t.get("kategori"),
            "catatan": t.get("catatan"),
            "tanggal_transaksi": t.get("tanggal_transaksi"),
        })
    if tx_rows:
        db.table("transactions").insert(tx_rows).execute()
