from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from database.supabase import get_supabase

STATUS_BELUM = "BELUM"
STATUS_LUNAS = "LUNAS"


def _db():
    return get_supabase()


def _rows(resp) -> List[Dict[str, Any]]:
    data = getattr(resp, "data", None)
    return data if isinstance(data, list) else ([] if data is None else [data])


def _first(resp) -> Optional[Dict[str, Any]]:
    rows = _rows(resp)
    return rows[0] if rows else None


def now_iso() -> str:
    return datetime.utcnow().isoformat()


def split_total_into_installments(total: int, count: int) -> List[int]:
    if count <= 0:
        raise ValueError("count must be > 0")
    base, remainder = divmod(int(total), int(count))
    return [base + (1 if i < remainder else 0) for i in range(count)]


def calc_company_total(nominal_awal: int, bunga_percent: float) -> int:
    return int(round(float(nominal_awal) + (float(nominal_awal) * float(bunga_percent) / 100.0)))


# ---------------------------------------------------------------------------
# PERSON DEBT
# ---------------------------------------------------------------------------

def create_person_loan(telegram_id: int, nama: str, nominal: int, catatan: str | None = None) -> Dict[str, Any]:
    payload = {
        "telegram_id": telegram_id,
        "nama": nama.strip(),
        "nominal": int(nominal),
        "catatan": (catatan or "").strip() or None,
        "status": STATUS_BELUM,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    return _first(_db().table("loan_person").insert(payload).execute()) or payload


def list_person_loans(telegram_id: int, status: str | None = None) -> List[Dict[str, Any]]:
    q = (
        _db()
        .table("loan_person")
        .select("*")
        .eq("telegram_id", telegram_id)
        .order("created_at", desc=True)
        .order("id", desc=True)
    )
    if status:
        q = q.eq("status", status)
    return q.execute().data or []


def get_person_loan(telegram_id: int, loan_id: int) -> Optional[Dict[str, Any]]:
    resp = (
        _db()
        .table("loan_person")
        .select("*")
        .eq("telegram_id", telegram_id)
        .eq("id", loan_id)
        .limit(1)
        .execute()
    )
    return _first(resp)


def update_person_loan(telegram_id: int, loan_id: int, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    payload = {**fields, "updated_at": now_iso()}
    resp = (
        _db()
        .table("loan_person")
        .update(payload)
        .eq("telegram_id", telegram_id)
        .eq("id", loan_id)
        .execute()
    )
    return _first(resp)


def mark_person_loan_paid(telegram_id: int, loan_id: int) -> Optional[Dict[str, Any]]:
    return update_person_loan(telegram_id, loan_id, {"status": STATUS_LUNAS})


def delete_person_loan(telegram_id: int, loan_id: int) -> None:
    _db().table("loan_person").delete().eq("telegram_id", telegram_id).eq("id", loan_id).execute()


def get_person_summary(telegram_id: int) -> Dict[str, int]:
    loans = list_person_loans(telegram_id)
    total = sum(int(r["nominal"]) for r in loans)
    open_total = sum(int(r["nominal"]) for r in loans if r.get("status") != STATUS_LUNAS)
    paid_total = total - open_total
    return {
        "count": len(loans),
        "total": total,
        "open_total": open_total,
        "paid_total": paid_total,
    }


# ---------------------------------------------------------------------------
# COMPANY / PINJOL
# ---------------------------------------------------------------------------

def create_company_loan(
    telegram_id: int,
    nama_lembaga: str,
    nominal_awal: int,
    bunga_percent: float,
    jumlah_cicilan: int,
) -> Dict[str, Any]:
    total = calc_company_total(nominal_awal, bunga_percent)
    installment_values = split_total_into_installments(total, jumlah_cicilan)

    loan_payload = {
        "telegram_id": telegram_id,
        "nama_lembaga": nama_lembaga.strip(),
        "nominal_awal": int(nominal_awal),
        "bunga": float(bunga_percent),
        "total": int(total),
        "jumlah_cicilan": int(jumlah_cicilan),
        "status": STATUS_BELUM,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    loan = _first(_db().table("loan_company").insert(loan_payload).execute())
    if not loan:
        loan = loan_payload
        loan["id"] = None

    loan_id = loan.get("id")
    if loan_id is None:
        raise RuntimeError("Gagal membuat data loan_company.")

    installment_rows = []
    for nomor, nominal in enumerate(installment_values, start=1):
        installment_rows.append({
            "loan_id": loan_id,
            "nomor": nomor,
            "nominal": int(nominal),
            "status": STATUS_BELUM,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        })

    if installment_rows:
        _db().table("loan_company_installments").insert(installment_rows).execute()

    return loan


def list_company_loans(telegram_id: int, status: str | None = None) -> List[Dict[str, Any]]:
    q = (
        _db()
        .table("loan_company")
        .select("*")
        .eq("telegram_id", telegram_id)
        .order("created_at", desc=True)
        .order("id", desc=True)
    )
    if status:
        q = q.eq("status", status)
    return q.execute().data or []


def get_company_loan(telegram_id: int, loan_id: int) -> Optional[Dict[str, Any]]:
    resp = (
        _db()
        .table("loan_company")
        .select("*")
        .eq("telegram_id", telegram_id)
        .eq("id", loan_id)
        .limit(1)
        .execute()
    )
    return _first(resp)


def list_company_installments(loan_id: int) -> List[Dict[str, Any]]:
    return (
        _db()
        .table("loan_company_installments")
        .select("*")
        .eq("loan_id", loan_id)
        .order("nomor", desc=False)
        .order("id", desc=False)
        .execute()
        .data
        or []
    )


def get_company_installment(installment_id: int) -> Optional[Dict[str, Any]]:
    resp = (
        _db()
        .table("loan_company_installments")
        .select("*")
        .eq("id", installment_id)
        .limit(1)
        .execute()
    )
    return _first(resp)


def mark_company_installment_paid(installment_id: int) -> Optional[Dict[str, Any]]:
    installment = get_company_installment(installment_id)
    if not installment:
        return None

    if installment.get("status") == STATUS_LUNAS:
        return installment

    payload = {
        "status": STATUS_LUNAS,
        "updated_at": now_iso(),
    }
    _db().table("loan_company_installments").update(payload).eq("id", installment_id).execute()

    loan_id = installment["loan_id"]
    remaining = (
        _db()
        .table("loan_company_installments")
        .select("id")
        .eq("loan_id", loan_id)
        .neq("status", STATUS_LUNAS)
        .execute()
        .data
        or []
    )
    if not remaining:
        _db().table("loan_company").update({
            "status": STATUS_LUNAS,
            "updated_at": now_iso(),
        }).eq("id", loan_id).execute()

    return get_company_installment(installment_id)


def delete_company_loan(telegram_id: int, loan_id: int) -> None:
    _db().table("loan_company_installments").delete().eq("loan_id", loan_id).execute()
    _db().table("loan_company").delete().eq("telegram_id", telegram_id).eq("id", loan_id).execute()


def get_company_summary(telegram_id: int) -> Dict[str, int]:
    loans = list_company_loans(telegram_id)
    total = sum(int(r["total"]) for r in loans)
    open_total = 0
    paid_total = 0
    for loan in loans:
        installments = list_company_installments(int(loan["id"]))
        paid = sum(int(i["nominal"]) for i in installments if i.get("status") == STATUS_LUNAS)
        paid_total += paid
        open_total += max(0, int(loan["total"]) - paid)
    return {
        "count": len(loans),
        "total": total,
        "open_total": open_total,
        "paid_total": paid_total,
    }


def get_company_loan_detail(telegram_id: int, loan_id: int) -> Optional[Dict[str, Any]]:
    loan = get_company_loan(telegram_id, loan_id)
    if not loan:
        return None
    installments = list_company_installments(loan_id)
    paid_total = sum(int(i["nominal"]) for i in installments if i.get("status") == STATUS_LUNAS)
    remaining_total = max(0, int(loan["total"]) - paid_total)
    completed_count = sum(1 for i in installments if i.get("status") == STATUS_LUNAS)
    loan = dict(loan)
    loan.update({
        "installments": installments,
        "paid_total": paid_total,
        "remaining_total": remaining_total,
        "completed_count": completed_count,
    })
    return loan
