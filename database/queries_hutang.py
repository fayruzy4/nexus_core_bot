from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

from database.supabase import get_supabase


def _db():
    return get_supabase()


def _now() -> str:
    return datetime.utcnow().isoformat()


def _first(data):
    if isinstance(data, list):
        return data[0] if data else None
    return data


def _select_one(resp):
    return _first(getattr(resp, "data", None))


def _select_many(resp) -> List[Dict[str, Any]]:
    data = getattr(resp, "data", None)
    return data if isinstance(data, list) else ([] if data is None else [data])


def calculate_company_loan_breakdown(
    nominal_awal: int,
    bunga_persen: float | int | str,
    jumlah_cicilan: int,
) -> Dict[str, Any]:
    if nominal_awal < 0:
        raise ValueError("nominal_awal tidak boleh negatif.")
    if jumlah_cicilan <= 0:
        raise ValueError("jumlah_cicilan harus lebih dari 0.")

    nominal_awal_dec = Decimal(str(nominal_awal))
    bunga_dec = Decimal(str(bunga_persen))
    total_hutang = int(
        (nominal_awal_dec * (Decimal("1") + (bunga_dec / Decimal("100")))).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )

    nominal_per_cicilan = total_hutang // jumlah_cicilan
    sisa = total_hutang % jumlah_cicilan

    installment_amounts = [
        nominal_per_cicilan + (1 if i < sisa else 0)
        for i in range(jumlah_cicilan)
    ]

    return {
        "nominal_awal": nominal_awal,
        "bunga_persen": float(bunga_dec),
        "total_hutang": total_hutang,
        "jumlah_cicilan": jumlah_cicilan,
        "nominal_per_cicilan": nominal_per_cicilan,
        "installment_amounts": installment_amounts,
    }


# =========================
# HUTANG PERORANGAN
# =========================

def create_person_loan(
    user_id: int,
    nama: str,
    nominal: int,
    catatan: str | None = None,
) -> Dict[str, Any]:
    db = _db()
    resp = db.table("loan_person").insert({
        "user_id": user_id,
        "nama": nama,
        "nominal": int(nominal),
        "catatan": catatan,
        "status": "BELUM",
    }).execute()
    row = _select_one(resp)
    if not row:
        raise RuntimeError("Gagal membuat hutang perorangan.")
    return row


def list_person_loans(user_id: int) -> List[Dict[str, Any]]:
    db = _db()
    resp = (
        db.table("loan_person")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .order("id", desc=True)
        .execute()
    )
    return _select_many(resp)


def get_person_loan(user_id: int, loan_id: int) -> Optional[Dict[str, Any]]:
    db = _db()
    resp = (
        db.table("loan_person")
        .select("*")
        .eq("user_id", user_id)
        .eq("id", loan_id)
        .limit(1)
        .execute()
    )
    return _select_one(resp)


def update_person_loan(
    user_id: int,
    loan_id: int,
    *,
    nama: str | None = None,
    nominal: int | None = None,
    catatan: str | None = None,
    status: str | None = None,
) -> Optional[Dict[str, Any]]:
    fields: Dict[str, Any] = {"updated_at": _now()}
    if nama is not None:
        fields["nama"] = nama
    if nominal is not None:
        fields["nominal"] = int(nominal)
    if catatan is not None:
        fields["catatan"] = catatan
    if status is not None:
        fields["status"] = status

    if len(fields) == 1:
        return get_person_loan(user_id, loan_id)

    db = _db()
    resp = (
        db.table("loan_person")
        .update(fields)
        .eq("user_id", user_id)
        .eq("id", loan_id)
        .execute()
    )
    row = _select_one(resp)
    if row:
        return row
    return get_person_loan(user_id, loan_id)


def set_person_loan_status(user_id: int, loan_id: int, status: str) -> Optional[Dict[str, Any]]:
    return update_person_loan(user_id, loan_id, status=status)


def mark_person_loan_lunas(user_id: int, loan_id: int) -> Optional[Dict[str, Any]]:
    return set_person_loan_status(user_id, loan_id, "LUNAS")


def delete_person_loan(user_id: int, loan_id: int) -> None:
    db = _db()
    db.table("loan_person").delete().eq("user_id", user_id).eq("id", loan_id).execute()


# =========================
# HUTANG LEMBAGA / PINJOL
# =========================

def create_company_loan(
    user_id: int,
    nama_lembaga: str,
    nominal_awal: int,
    bunga_persen: float | int | str,
    jumlah_cicilan: int,
) -> Dict[str, Any]:
    breakdown = calculate_company_loan_breakdown(
        nominal_awal=nominal_awal,
        bunga_persen=bunga_persen,
        jumlah_cicilan=jumlah_cicilan,
    )

    db = _db()
    company_resp = db.table("loan_company").insert({
        "user_id": user_id,
        "nama_lembaga": nama_lembaga,
        "nominal_awal": breakdown["nominal_awal"],
        "bunga_persen": breakdown["bunga_persen"],
        "total_hutang": breakdown["total_hutang"],
        "jumlah_cicilan": breakdown["jumlah_cicilan"],
        "nominal_per_cicilan": breakdown["nominal_per_cicilan"],
        "cicilan_selesai": 0,
        "sisa_hutang": breakdown["total_hutang"],
        "status": "BELUM",
    }).execute()

    company = _select_one(company_resp)
    if not company:
        raise RuntimeError("Gagal membuat pinjaman lembaga.")

    installment_rows = []
    for idx, amount in enumerate(breakdown["installment_amounts"], start=1):
        installment_rows.append({
            "loan_company_id": company["id"],
            "urutan": idx,
            "nominal": amount,
            "status": "BELUM",
        })

    if installment_rows:
        db.table("loan_company_installments").insert(installment_rows).execute()

    return get_company_loan_summary(user_id, company["id"]) or company


def list_company_loans(user_id: int) -> List[Dict[str, Any]]:
    db = _db()
    resp = (
        db.table("loan_company")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .order("id", desc=True)
        .execute()
    )
    rows = _select_many(resp)
    result: List[Dict[str, Any]] = []
    for row in rows:
        summary = get_company_loan_summary(user_id, row["id"])
        if summary:
            result.append(summary)
    return result


def get_company_loan(user_id: int, loan_id: int) -> Optional[Dict[str, Any]]:
    db = _db()
    resp = (
        db.table("loan_company")
        .select("*")
        .eq("user_id", user_id)
        .eq("id", loan_id)
        .limit(1)
        .execute()
    )
    return _select_one(resp)


def update_company_loan(
    user_id: int,
    loan_id: int,
    *,
    nama_lembaga: str | None = None,
    nominal_awal: int | None = None,
    bunga_persen: float | int | str | None = None,
    total_hutang: int | None = None,
    jumlah_cicilan: int | None = None,
    nominal_per_cicilan: int | None = None,
    cicilan_selesai: int | None = None,
    sisa_hutang: int | None = None,
    status: str | None = None,
) -> Optional[Dict[str, Any]]:
    fields: Dict[str, Any] = {"updated_at": _now()}
    if nama_lembaga is not None:
        fields["nama_lembaga"] = nama_lembaga
    if nominal_awal is not None:
        fields["nominal_awal"] = int(nominal_awal)
    if bunga_persen is not None:
        fields["bunga_persen"] = float(Decimal(str(bunga_persen)))
    if total_hutang is not None:
        fields["total_hutang"] = int(total_hutang)
    if jumlah_cicilan is not None:
        fields["jumlah_cicilan"] = int(jumlah_cicilan)
    if nominal_per_cicilan is not None:
        fields["nominal_per_cicilan"] = int(nominal_per_cicilan)
    if cicilan_selesai is not None:
        fields["cicilan_selesai"] = int(cicilan_selesai)
    if sisa_hutang is not None:
        fields["sisa_hutang"] = int(sisa_hutang)
    if status is not None:
        fields["status"] = status

    if len(fields) == 1:
        return get_company_loan(user_id, loan_id)

    db = _db()
    resp = (
        db.table("loan_company")
        .update(fields)
        .eq("user_id", user_id)
        .eq("id", loan_id)
        .execute()
    )
    row = _select_one(resp)
    if row:
        return row
    return get_company_loan(user_id, loan_id)


def delete_company_loan(user_id: int, loan_id: int) -> None:
    db = _db()
    db.table("loan_company").delete().eq("user_id", user_id).eq("id", loan_id).execute()


def list_company_installments(loan_company_id: int) -> List[Dict[str, Any]]:
    db = _db()
    resp = (
        db.table("loan_company_installments")
        .select("*")
        .eq("loan_company_id", loan_company_id)
        .order("urutan", desc=False)
        .order("id", desc=False)
        .execute()
    )
    return _select_many(resp)


def get_company_installment_by_order(
    loan_company_id: int,
    urutan: int,
) -> Optional[Dict[str, Any]]:
    db = _db()
    resp = (
        db.table("loan_company_installments")
        .select("*")
        .eq("loan_company_id", loan_company_id)
        .eq("urutan", urutan)
        .limit(1)
        .execute()
    )
    return _select_one(resp)


def get_company_installment_by_id(
    loan_company_id: int,
    installment_id: int,
) -> Optional[Dict[str, Any]]:
    db = _db()
    resp = (
        db.table("loan_company_installments")
        .select("*")
        .eq("loan_company_id", loan_company_id)
        .eq("id", installment_id)
        .limit(1)
        .execute()
    )
    return _select_one(resp)


def update_company_installment_status(
    loan_company_id: int,
    installment_id: int,
    status: str,
) -> Optional[Dict[str, Any]]:
    db = _db()
    resp = (
        db.table("loan_company_installments")
        .update({
            "status": status,
            "updated_at": _now(),
        })
        .eq("loan_company_id", loan_company_id)
        .eq("id", installment_id)
        .execute()
    )
    row = _select_one(resp)
    if row:
        return row
    return get_company_installment_by_id(loan_company_id, installment_id)


def update_company_installment_status_by_order(
    loan_company_id: int,
    urutan: int,
    status: str,
) -> Optional[Dict[str, Any]]:
    installment = get_company_installment_by_order(loan_company_id, urutan)
    if not installment:
        return None
    return update_company_installment_status(
        loan_company_id,
        installment["id"],
        status,
    )


def mark_company_installment_paid(
    loan_company_id: int,
    installment_id: int,
) -> Optional[Dict[str, Any]]:
    updated = update_company_installment_status(loan_company_id, installment_id, "LUNAS")
    if updated is None:
        return None
    return recalculate_company_progress(loan_company_id)


def mark_company_installment_paid_by_order(
    loan_company_id: int,
    urutan: int,
) -> Optional[Dict[str, Any]]:
    installment = get_company_installment_by_order(loan_company_id, urutan)
    if not installment:
        return None
    return mark_company_installment_paid(loan_company_id, installment["id"])


def unmark_company_installment_paid(
    loan_company_id: int,
    installment_id: int,
) -> Optional[Dict[str, Any]]:
    updated = update_company_installment_status(loan_company_id, installment_id, "BELUM")
    if updated is None:
        return None
    return recalculate_company_progress(loan_company_id)


def recalculate_company_progress(
    loan_company_id: int,
) -> Optional[Dict[str, Any]]:
    db = _db()
    company_resp = (
        db.table("loan_company")
        .select("*")
        .eq("id", loan_company_id)
        .limit(1)
        .execute()
    )
    company = _select_one(company_resp)
    if not company:
        return None

    installments = list_company_installments(loan_company_id)
    paid_count = sum(1 for item in installments if item.get("status") == "LUNAS")
    paid_total = sum(int(item.get("nominal") or 0) for item in installments if item.get("status") == "LUNAS")
    total_hutang = int(company.get("total_hutang") or 0)
    remaining = max(0, total_hutang - paid_total)
    status = "LUNAS" if remaining == 0 and installments else "BELUM"

    update_company_loan(
        int(company["user_id"]),
        loan_company_id,
        cicilan_selesai=paid_count,
        sisa_hutang=remaining,
        status=status,
    )

    company.update({
        "installments": installments,
        "paid_count": paid_count,
        "already_paid": paid_total,
        "remaining": remaining,
        "status": status,
    })
    return company


def get_company_loan_summary(
    user_id: int,
    loan_id: int,
) -> Optional[Dict[str, Any]]:
    company = get_company_loan(user_id, loan_id)
    if not company:
        return None

    installments = list_company_installments(loan_id)
    paid_count = sum(1 for item in installments if item.get("status") == "LUNAS")
    paid_total = sum(int(item.get("nominal") or 0) for item in installments if item.get("status") == "LUNAS")
    total_hutang = int(company.get("total_hutang") or 0)
    remaining = max(0, total_hutang - paid_total)
    status = "LUNAS" if remaining == 0 and installments else "BELUM"

    update_company_loan(
        user_id,
        loan_id,
        cicilan_selesai=paid_count,
        sisa_hutang=remaining,
        status=status,
    )

    company.update({
        "installments": installments,
        "paid_count": paid_count,
        "already_paid": paid_total,
        "remaining": remaining,
        "status": status,
    })
    return company


def list_company_loans_with_summary(user_id: int) -> List[Dict[str, Any]]:
    rows = list_company_loans(user_id)
    return rows


def delete_company_installments(loan_company_id: int) -> None:
    db = _db()
    db.table("loan_company_installments").delete().eq("loan_company_id", loan_company_id).execute()


def reset_hutang_data(user_id: int) -> None:
    db = _db()
    db.table("loan_person").delete().eq("user_id", user_id).execute()
    db.table("loan_company").delete().eq("user_id", user_id).execute()
    # loan_company_installments ikut terhapus lewat cascade dari loan_company
