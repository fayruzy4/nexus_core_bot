from __future__ import annotations

import math
import os
import re
import tempfile
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import matplotlib.pyplot as plt


def rupiah(value: int | float | None) -> str:
    amount = int(value or 0)
    sign = "-" if amount < 0 else ""
    amount = abs(amount)
    return f"{sign}Rp {amount:,}".replace(",", ".")


def parse_amount(text: str) -> Optional[int]:
    if text is None:
        return None
    raw = text.strip().lower()
    raw = raw.replace("rp", "").replace(" ", "")
    raw = raw.replace(".", "").replace(",", "")
    raw = re.sub(r"[^0-9-]", "", raw)
    if raw in {"", "-", "--"}:
        return None
    try:
        amount = int(raw)
    except ValueError:
        return None
    return amount


def safe_text(value: Any, default: str = "-") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _human_date(raw: Optional[str]) -> str:
    if not raw:
        return "-"
    try:
        dt = datetime.fromisoformat(raw)
        return dt.strftime("%d-%m-%Y %H:%M")
    except Exception:
        if len(raw) >= 10:
            return raw[:10]
        return raw


def target_progress(dana_terkumpul: int, nominal_target: int) -> float:
    target = max(0, int(nominal_target or 0))
    gathered = max(0, int(dana_terkumpul or 0))
    if target <= 0:
        return 0.0
    return round(min((gathered / target) * 100, 100.0), 1)


def target_sisa(dana_terkumpul: int, nominal_target: int) -> int:
    return max(int(nominal_target or 0) - int(dana_terkumpul or 0), 0)


def status_label(status: str) -> str:
    return "✅ SELESAI" if status == "SELESAI" else "🟡 AKTIF"


def format_target_detail(target: Dict[str, Any]) -> str:
    gathered = int(target.get("dana_terkumpul", 0) or 0)
    goal = int(target.get("nominal_target", 0) or 0)
    remaining = target_sisa(gathered, goal)
    progress = target_progress(gathered, goal)
    lines = [
        "━━━━━━━━━━━━━━",
        "🎯 DETAIL TARGET",
        "━━━━━━━━━━━━━━",
        "",
        f"Nama Target: {safe_text(target.get('nama_target'))}",
        f"Nominal Target: {rupiah(goal)}",
        f"Dana Terkumpul: {rupiah(gathered)}",
        f"Sisa Dana: {rupiah(remaining)}",
        f"Progress: {progress}%",
        f"Tanggal Dibuat: {_human_date(target.get('created_at'))}",
        f"Catatan: {safe_text(target.get('catatan'))}",
        f"Status: {status_label(safe_text(target.get('status'), 'AKTIF'))}",
    ]
    return "\n".join(lines)


def format_target_summary(summary: Dict[str, Any]) -> str:
    total_target = int(summary.get("total_nominal_target", 0) or 0)
    total_gathered = int(summary.get("total_dana_terkumpul", 0) or 0)
    total_sisa = int(summary.get("total_sisa", 0) or 0)
    progress = float(summary.get("progress", 0.0) or 0.0)
    lines = [
        "━━━━━━━━━━━━━━",
        "📊 RINGKASAN TARGET",
        "━━━━━━━━━━━━━━",
        "",
        f"Jumlah Target Aktif: {int(summary.get('jumlah_aktif', 0) or 0)}",
        f"Jumlah Target Selesai: {int(summary.get('jumlah_selesai', 0) or 0)}",
        f"Total Nominal Target: {rupiah(total_target)}",
        f"Total Dana Terkumpul: {rupiah(total_gathered)}",
        f"Total Sisa: {rupiah(total_sisa)}",
        f"Progress Keseluruhan: {progress}%",
    ]
    return "\n".join(lines)


def format_completion_message(target: Dict[str, Any], previous_total: int) -> str:
    goal = int(target.get("nominal_target", 0) or 0)
    gathered = int(target.get("dana_terkumpul", 0) or 0)
    return (
        "━━━━━━━━━━━━━━\n"
        "🎉 TARGET SELESAI\n"
        "━━━━━━━━━━━━━━\n\n"
        f"Nama Target: {safe_text(target.get('nama_target'))}\n"
        f"Nominal Target: {rupiah(goal)}\n"
        f"Dana Terkumpul: {rupiah(gathered)}\n"
        f"Tambahan Terakhir: {rupiah(gathered - previous_total)}\n\n"
        "Perjalanan target ini sudah sampai garis akhir. "
        "Kalau mau lanjut bikin target baru, tinggal pakai tombol Buat Target."
    )


def build_pie_chart(dana_terkumpul: int, sisa_dana: int, title: str, prefix: str = "target") -> str:
    gathered = max(0, int(dana_terkumpul or 0))
    remaining = max(0, int(sisa_dana or 0))
    total = gathered + remaining
    if total <= 0:
        gathered = 1
        remaining = 0
        total = 1

    fig, ax = plt.subplots(figsize=(6, 6))
    labels = ["Dana Terkumpul", "Sisa Dana"]
    values = [gathered, remaining]
    explode = [0.03, 0.03]
    autopct = lambda pct: f"{pct:.1f}%" if pct > 0 else ""
    ax.pie(values, labels=labels, autopct=autopct, startangle=90, explode=explode)
    ax.set_title(title)
    ax.axis("equal")

    filename = f"{prefix}_pie_{os.getpid()}_{abs(hash((gathered, remaining, title))) % 100000}.png"
    path = os.path.join(tempfile.gettempdir(), filename)
    fig.savefig(path, bbox_inches="tight", dpi=160)
    plt.close(fig)
    return path


def calc_detail_metrics(target: Dict[str, Any]) -> Dict[str, Any]:
    gathered = int(target.get("dana_terkumpul", 0) or 0)
    goal = int(target.get("nominal_target", 0) or 0)
    remaining = target_sisa(gathered, goal)
    progress = target_progress(gathered, goal)
    return {
        "dana_terkumpul": gathered,
        "nominal_target": goal,
        "sisa_dana": remaining,
        "progress": progress,
    }


def normalize_menu_choice(text: str) -> str:
    return (text or "").strip()


def is_amount_text(text: str) -> bool:
    return parse_amount(text) is not None
