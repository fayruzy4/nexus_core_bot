from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

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
    nominal_awal_dec = Decimal(str(nominal_awal))
    bunga_dec = Decimal(str(bunga_percent))
    total = nominal_awal_dec + (nominal_awal_dec * bunga_dec / Decimal("100"))
    return int(total.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _calculate_company_breakdown(
    nominal_awal: int,
    bunga_persen: float,
    jumlah_cicilan: int,
) -> Dict[str, Any]:
    if nominal_awal < 0:
        raise ValueError("nominal_awal must be >= 0")
    if bunga_persen < 0:
        raise ValueError("bunga_persen must be >= 0")
    if jumlah_cicilan <= 0:
        raise ValueError("jumlah_cicilan must be > 0")

    total_hutang = calc_company_total(nominal_awal, bunga_persen)
    installment_values = split_total_into_installments(total_hutang, jumlah_cicilan)
    nominal_per_cicilan = installment_values[0] if installment_values else 0

    return {
        "nominal_awal": int(nominal_awal),
        "bunga_persen": float(bunga_persen),
        "total_hutang": int(total_hutang),
        "jumlah_cicilan": int(jumlah_cicilan),
        "nominal_per_cicilan": int(nominal_per_cicilan),
        "installment_values": installment_values,
    }


# ---------------------------------------------------------------------------
# HUTANG PERORANGAN
# ---------------------------------------------------------------------------

def create_person_loan(
    user_id: int,
    nama: str,
    nominal: int,
    catatan: str | None = None,
) -> Dict[str, Any]:
    payload = {
        "user_id": int(user_id),
        "nama": nama.strip(),
        "nominal": int(nominal),
        "catatan": (catatan or "").strip() or None,
        "status": STATUS_BELUM,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    resp = _db().table("loan_person").insert(payload).execute()
    row = _first(resp)
    return row or payload


def list_person_loans(user_id: int, status: str | None = None) -> List[Dict[str, Any]]:
    q = (
        _db()
        .table("loan_person")
        .select("*")
        .eq("user_id", int(user_id))
        .order("created_at", desc=True)
        .order("id", desc=True)
    )
    if status:
        q = q.eq("status", status)
    return q.execute().data or []


def get_person_loan(user_id: int, loan_id: int) -> Optional[Dict[str, Any]]:
    resp = (
        _db()
        .table("loan_person")
        .select("*")
        .eq("user_id", int(user_id))
        .eq("id", int(loan_id))
        .limit(1)
        .execute()
    )
    return _first(resp)


def update_person_loan(
    user_id: int,
    loan_id: int,
    fields: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    payload = {**fields, "updated_at": now_iso()}
    resp = (
        _db()
        .table("loan_person")
        .update(payload)
        .eq("user_id", int(user_id))
        .eq("id", int(loan_id))
        .execute()
    )
    row = _first(resp)
    return row or get_person_loan(user_id, loan_id)


def mark_person_loan_paid(user_id: int, loan_id: int) -> Optional[Dict[str, Any]]:
    return update_person_loan(user_id, loan_id, {"status": STATUS_LUNAS})


# alias aman kalau ada file lama yang masih memanggil nama ini
def mark_person_loan_lunas(user_id: int, loan_id: int) -> Optional[Dict[str, Any]]:
    return mark_person_loan_paid(user_id, loan_id)


def delete_person_loan(user_id: int, loan_id: int) -> None:
    _db().table("loan_person").delete().eq("user_id", int(user_id)).eq("id", int(loan_id)).execute()


def get_person_summary(user_id: int) -> Dict[str, int]:
    loans = list_person_loans(user_id)
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
# HUTANG LEMBAGA / PINJOL
# ---------------------------------------------------------------------------

def create_company_loan(
    user_id: int,
    nama_lembaga: str,
    nominal_awal: int,
    bunga_persen: float,
    jumlah_cicilan: int,
) -> Dict[str, Any]:
    breakdown = _calculate_company_breakdown(nominal_awal, bunga_persen, jumlah_cicilan)

    loan_payload = {
        "user_id": int(user_id),
        "nama_lembaga": nama_lembaga.strip(),
        "nominal_awal": breakdown["nominal_awal"],
        "bunga_persen": breakdown["bunga_persen"],
        "total_hutang": breakdown["total_hutang"],
        "jumlah_cicilan": breakdown["jumlah_cicilan"],
        "nominal_per_cicilan": breakdown["nominal_per_cicilan"],
        "cicilan_selesai": 0,
        "sisa_hutang": breakdown["total_hutang"],
        "status": STATUS_BELUM,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }

    resp = _db().table("loan_company").insert(loan_payload).execute()
    loan = _first(resp) or loan_payload

    loan_id = loan.get("id")
    if loan_id is None:
        raise RuntimeError("Gagal membuat data loan_company.")

    installment_rows = []
    for nomor, nominal in enumerate(breakdown["installment_values"], start=1):
        installment_rows.append({
            "loan_company_id": int(loan_id),
            "urutan": nomor,
            "nominal": int(nominal),
            "status": STATUS_BELUM,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        })

    if installment_rows:
        _db().table("loan_company_installments").insert(installment_rows).execute()

    return get_company_loan_detail(user_id, int(loan_id)) or loan


def list_company_loans(user_id: int, status: str | None = None) -> List[Dict[str, Any]]:
    q = (
        _db()
        .table("loan_company")
        .select("*")
        .eq("user_id", int(user_id))
        .order("created_at", desc=True)
        .order("id", desc=True)
    )
    if status:
        q = q.eq("status", status)
    return q.execute().data or []


def get_company_loan(user_id: int, loan_id: int) -> Optional[Dict[str, Any]]:
    resp = (
        _db()
        .table("loan_company")
        .select("*")
        .eq("user_id", int(user_id))
        .eq("id", int(loan_id))
        .limit(1)
        .execute()
    )
    return _first(resp)


def update_company_loan(
    user_id: int,
    loan_id: int,
    fields: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    payload = {**fields, "updated_at": now_iso()}
    resp = (
        _db()
        .table("loan_company")
        .update(payload)
        .eq("user_id", int(user_id))
        .eq("id", int(loan_id))
        .execute()
    )
    row = _first(resp)
    return row or get_company_loan(user_id, loan_id)


def delete_company_loan(user_id: int, loan_id: int) -> None:
    _db().table("loan_company").delete().eq("user_id", int(user_id)).eq("id", int(loan_id)).execute()


def list_company_installments(loan_company_id: int) -> List[Dict[str, Any]]:
    return (
        _db()
        .table("loan_company_installments")
        .select("*")
        .eq("loan_company_id", int(loan_company_id))
        .order("urutan", desc=False)
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
        .eq("id", int(installment_id))
        .limit(1)
        .execute()
    )
    return _first(resp)


def get_company_installment_by_order(
    loan_company_id: int,
    urutan: int,
) -> Optional[Dict[str, Any]]:
    resp = (
        _db()
        .table("loan_company_installments")
        .select("*")
        .eq("loan_company_id", int(loan_company_id))
        .eq("urutan", int(urutan))
        .limit(1)
        .execute()
    )
    return _first(resp)


def update_company_installment_status(
    installment_id: int,
    status: str,
) -> Optional[Dict[str, Any]]:
    payload = {
        "status": status,
        "updated_at": now_iso(),
    }
    resp = (
        _db()
        .table("loan_company_installments")
        .update(payload)
        .eq("id", int(installment_id))
        .execute()
    )
    row = _first(resp)
    return row or get_company_installment(installment_id)


def mark_company_installment_paid(installment_id: int) -> Optional[Dict[str, Any]]:
    installment = get_company_installment(installment_id)
    if not installment:
        return None

    if installment.get("status") == STATUS_LUNAS:
        return get_company_loan_detail_by_id(int(installment["loan_company_id"])) or installment

    update_company_installment_status(installment_id, STATUS_LUNAS)
    return recalculate_company_progress(int(installment["loan_company_id"]))


def unmark_company_installment_paid(installment_id: int) -> Optional[Dict[str, Any]]:
    installment = get_company_installment(installment_id)
    if not installment:
        return None
    update_company_installment_status(installment_id, STATUS_BELUM)
    return recalculate_company_progress(int(installment["loan_company_id"]))


def recalculate_company_progress(loan_company_id: int) -> Optional[Dict[str, Any]]:
    loan = get_company_loan_by_id(loan_company_id)
    if not loan:
        return None

    installments = list_company_installments(loan_company_id)
    paid_total = sum(int(i["nominal"]) for i in installments if i.get("status") == STATUS_LUNAS)
    completed_count = sum(1 for i in installments if i.get("status") == STATUS_LUNAS)
    total_hutang = int(loan["total_hutang"])
    remaining_total = max(0, total_hutang - paid_total)
    status = STATUS_LUNAS if remaining_total == 0 and installments else STATUS_BELUM

    update_company_loan(
        int(loan["user_id"]),
        loan_company_id,
        {
            "cicilan_selesai": completed_count,
            "sisa_hutang": remaining_total,
            "status": status,
        },
    )

    loan = dict(loan)
    loan.update({
        "installments": installments,
        "paid_total": paid_total,
        "remaining_total": remaining_total,
        "completed_count": completed_count,
        "status": status,
    })
    return loan


def get_company_loan_by_id(loan_company_id: int) -> Optional[Dict[str, Any]]:
    resp = (
        _db()
        .table("loan_company")
        .select("*")
        .eq("id", int(loan_company_id))
        .limit(1)
        .execute()
    )
    return _first(resp)


def get_company_loan_detail(user_id: int, loan_id: int) -> Optional[Dict[str, Any]]:
    loan = get_company_loan(user_id, loan_id)
    if not loan:
        return None

    installments = list_company_installments(int(loan_id))
    paid_total = sum(int(i["nominal"]) for i in installments if i.get("status") == STATUS_LUNAS)
    completed_count = sum(1 for i in installments if i.get("status") == STATUS_LUNAS)
    remaining_total = max(0, int(loan["total_hutang"]) - paid_total)
    status = STATUS_LUNAS if remaining_total == 0 and installments else STATUS_BELUM

    update_company_loan(
        user_id,
        loan_id,
        {
            "cicilan_selesai": completed_count,
            "sisa_hutang": remaining_total,
            "status": status,
        },
    )

    loan = dict(loan)
    loan.update({
        "installments": installments,
        "paid_total": paid_total,
        "remaining_total": remaining_total,
        "completed_count": completed_count,
        "status": status,
    })
    return loan


def get_company_summary(user_id: int) -> Dict[str, int]:
    loans = list_company_loans(user_id)
    total = sum(int(r["total_hutang"]) for r in loans)
    open_total = 0
    paid_total = 0

    for loan in loans:
        installments = list_company_installments(int(loan["id"]))
        paid = sum(int(i["nominal"]) for i in installments if i.get("status") == STATUS_LUNAS)
        paid_total += paid
        open_total += max(0, int(loan["total_hutang"]) - paid)

    return {
        "count": len(loans),
        "total": total,
        "open_total": open_total,
        "paid_total": paid_total,
    }


def delete_company_installments(loan_company_id: int) -> None:
    _db().table("loan_company_installments").delete().eq("loan_company_id", int(loan_company_id)).execute()
