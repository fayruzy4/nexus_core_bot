from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

USER_STATE: Dict[int, Dict[str, Any]] = defaultdict(lambda: {
    "flow": None,
    "step": None,
    "payload": {},
    "items": [],
    "selected_tx": None,
})

def state(user_id: int) -> Dict[str, Any]:
    return USER_STATE[user_id]

def reset_state(user_id: int) -> None:
    USER_STATE[user_id] = {
        "flow": None,
        "step": None,
        "payload": {},
        "items": [],
        "selected_tx": None,
    }

def set_flow(user_id: int, flow: str | None, step: str | None = None, payload: Optional[Dict[str, Any]] = None) -> None:
    s = state(user_id)
    s["flow"] = flow
    s["step"] = step
    if payload is not None:
        s["payload"] = payload

def rupiah(value: int | float | str) -> str:
    n = int(float(value))
    return f"Rp{n:,}".replace(",", ".")

def parse_amount(text: str) -> Optional[int]:
    cleaned = text.strip().lower().replace("rp", "").replace(".", "").replace(",", "").replace(" ", "")
    if not cleaned.isdigit():
        return None
    return int(cleaned)

def parse_date(text: str) -> Optional[str]:
    raw = text.strip().replace("/", "-")
    for fmt in ("%d-%m-%Y", "%d-%m-%y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.date().isoformat()
        except ValueError:
            pass
    return None

def today_iso() -> str:
    return date.today().isoformat()

def week_range() -> Tuple[str, str]:
    end = date.today()
    start = end - timedelta(days=6)
    return start.isoformat(), end.isoformat()

def month_range() -> Tuple[str, str]:
    end = date.today()
    start = end - timedelta(days=29)
    return start.isoformat(), end.isoformat()

def period_range(label: str) -> Tuple[str, str]:
    today = date.today()
    if label == "today":
        d = today.isoformat()
        return d, d
    if label == "week":
        return week_range()
    if label == "month":
        return month_range()
    return "1970-01-01", today.isoformat()

def report_days(label: str) -> int:
    return {
        "1m": 30,
        "2m": 60,
        "3m": 90,
        "6m": 180,
        "9m": 270,
        "1y": 365,
    }.get(label, 30)

def to_period_key(text: str) -> Optional[str]:
    mapping = {
        "📅 1 Bulan": "1m",
        "📅 2 Bulan": "2m",
        "📅 3 Bulan": "3m",
        "📅 6 Bulan": "6m",
        "📅 9 Bulan": "9m",
        "📅 1 Tahun": "1y",
    }
    return mapping.get(text)

def to_history_key(text: str) -> Optional[str]:
    mapping = {
        "📅 Hari Ini": "today",
        "📅 Minggu Ini": "week",
        "📅 Bulan Ini": "month",
        "📅 Semua": "all",
        "🔍 Cari": "search",
    }
    return mapping.get(text)

def format_transaction_line(i: int, tx: Dict[str, Any]) -> str:
    return (
        f"{i}. [{tx['id']}]\n"
        f"{'💵' if tx['jenis']=='pemasukan' else '💸'} {tx['kategori']}\n"
        f"{rupiah(tx['nominal'])}\n"
        f"{tx['tanggal_transaksi']}"
    )

def summarize_rows(rows: List[Dict[str, Any]], saldo_awal: int = 0) -> Dict[str, Any]:
    income = sum(int(r["nominal"]) for r in rows if r["jenis"] == "pemasukan")
    expense = sum(int(r["nominal"]) for r in rows if r["jenis"] == "pengeluaran")
    net = saldo_awal + income - expense
    count = len(rows)
    return {
        "pemasukan": income,
        "pengeluaran": expense,
        "saldo": net,
        "count": count,
    }

def top_category(rows: List[Dict[str, Any]], jenis: str = "pengeluaran") -> Optional[Tuple[str, int]]:
    totals: Dict[str, int] = {}
    for r in rows:
        if r["jenis"] != jenis:
            continue
        totals[r["kategori"]] = totals.get(r["kategori"], 0) + int(r["nominal"])
    if not totals:
        return None
    kategori = max(totals, key=totals.get)
    return kategori, totals[kategori]

def average_transaction(rows: List[Dict[str, Any]]) -> int:
    if not rows:
        return 0
    return int(sum(int(r["nominal"]) for r in rows) / len(rows))

def build_insights(current_rows: List[Dict[str, Any]], previous_rows: List[Dict[str, Any]] | None = None) -> List[str]:
    lines: List[str] = []
    current = summarize_rows(current_rows)
    if current["count"] == 0:
        return ["Belum ada transaksi di periode ini."]
    top = top_category(current_rows, "pengeluaran")
    if top:
        lines.append(f"Pengeluaran terbesar ada di kategori {top[0]} ({rupiah(top[1])}).")
    avg = average_transaction(current_rows)
    lines.append(f"Rata-rata nominal transaksi sekitar {rupiah(avg)}.")
    if current["pengeluaran"] > current["pemasukan"]:
        lines.append("Pengeluaran masih lebih besar dari pemasukan.")
    else:
        lines.append("Pemasukan masih cukup menutup pengeluaran.")
    if previous_rows is not None:
        prev = summarize_rows(previous_rows)
        if prev["pengeluaran"] > 0:
            delta = ((current["pengeluaran"] - prev["pengeluaran"]) / prev["pengeluaran"]) * 100
            if delta >= 0:
                lines.append(f"Pengeluaran naik sekitar {delta:.1f}% dibanding periode sebelumnya.")
            else:
                lines.append(f"Pengeluaran turun sekitar {abs(delta):.1f}% dibanding periode sebelumnya.")
    return lines

def day_label(d: str) -> str:
    return datetime.strptime(d, "%Y-%m-%d").strftime("%d %b %Y")
