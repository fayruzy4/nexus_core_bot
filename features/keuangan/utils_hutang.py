from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from features.keuangan.utils import parse_amount, rupiah


HUTANG_STATE: Dict[int, Dict[str, Any]] = defaultdict(lambda: {
    "flow": None,
    "step": None,
    "payload": {},
    "items": {},
    "selected_id": None,
    "installments": [],
    "pending_action": None,
})


def state(user_id: int) -> Dict[str, Any]:
    return HUTANG_STATE[user_id]


def reset_state(user_id: int) -> None:
    HUTANG_STATE[user_id] = {
        "flow": None,
        "step": None,
        "payload": {},
        "items": {},
        "selected_id": None,
        "installments": [],
        "pending_action": None,
    }


def clear_selection(user_id: int) -> None:
    s = state(user_id)
    s["items"] = {}
    s["selected_id"] = None
    s["installments"] = []
    s["pending_action"] = None


def parse_percentage(text: str) -> Optional[float]:
    cleaned = (
        text.strip()
        .lower()
        .replace("%", "")
        .replace("persen", "")
        .replace("rp", "")
        .replace(" ", "")
        .replace(",", ".")
    )
    if not cleaned:
        return None
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value if value >= 0 else None


def parse_installment_count(text: str) -> Optional[int]:
    cleaned = (
        text.strip()
        .lower()
        .replace("x", "")
        .replace("kali", "")
        .replace("cicilan", "")
        .replace(" ", "")
    )
    if not cleaned.isdigit():
        return None
    count = int(cleaned)
    return count if count > 0 else None


def split_total_into_installments(total: int, count: int) -> List[int]:
    if count <= 0:
        raise ValueError("count must be positive")
    base, remainder = divmod(int(total), int(count))
    return [base + (1 if i < remainder else 0) for i in range(count)]


def calc_company_total(nominal_awal: int, bunga_percent: float) -> int:
    return int(round(float(nominal_awal) + (float(nominal_awal) * float(bunga_percent) / 100.0)))


def company_percent_label(percent: float) -> str:
    if float(percent).is_integer():
        return f"{int(percent)}%"
    return f"{percent:.2f}%"


def installment_label(nomor: int, nominal: int, paid: bool = False) -> str:
    box = "☑" if paid else "☐"
    return f"{box} Cicilan {nomor} • {rupiah(nominal)}"


def person_item_label(index: int, nama: str, nominal: int, paid: bool = False) -> str:
    box = "☑" if paid else "☐"
    return f"{index}. {box} {nama} • {rupiah(nominal)}"


def company_item_label(index: int, nama: str, remaining: int, total: int, paid: bool = False) -> str:
    box = "☑" if paid else "☐"
    return f"{index}. {box} {nama} • Sisa {rupiah(remaining)} / {rupiah(total)}"


def note_or_dash(note: str | None) -> str:
    return note.strip() if isinstance(note, str) and note.strip() else "-"


def percentage_input_hint() -> str:
    return "Tulis bunganya ya. Contoh: 10 atau 10.5"


def count_input_hint() -> str:
    return "Pilih jumlah cicilan dari tombol, atau ketik angkanya kalau mau yang lain."
