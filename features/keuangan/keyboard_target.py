from __future__ import annotations

from typing import Any, Dict, Iterable, List

from telegram import KeyboardButton, ReplyKeyboardMarkup

try:
    from config import BTN_BACK, BTN_CANCEL, BTN_TARGET
except Exception:
    BTN_BACK = "⬅️ Kembali"
    BTN_CANCEL = "❌ Batal"
    BTN_TARGET = "🎯 Target"


def _markup(rows: List[List[str]]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(text=label) for label in row] for row in rows],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def target_dashboard_keyboard() -> ReplyKeyboardMarkup:
    return _markup(
        [
            ["➕ Buat Target"],
            ["📂 Target Aktif"],
            ["✅ Target Selesai"],
            ["📊 Ringkasan Target"],
            [BTN_BACK],
        ]
    )


def target_list_keyboard(targets: List[Dict[str, Any]], mode: str = "active") -> ReplyKeyboardMarkup:
    rows: List[List[str]] = []
    for idx, item in enumerate(targets, 1):
        name = str(item.get("nama_target", "")).strip() or "(Tanpa Nama)"
        rows.append([f"{idx}. {name}"])
    rows.append([BTN_BACK])
    return _markup(rows)


def target_detail_keyboard_active() -> ReplyKeyboardMarkup:
    return _markup(
        [
            ["➕ Tambah Dana", "➖ Kurangi Dana"],
            ["✏ Edit Target", "🗑 Hapus Target"],
            [BTN_BACK],
        ]
    )


def target_detail_keyboard_done() -> ReplyKeyboardMarkup:
    return _markup(
        [
            ["🗑 Hapus Target"],
            [BTN_BACK],
        ]
    )


def target_create_keyboard() -> ReplyKeyboardMarkup:
    return _markup([[BTN_BACK, BTN_CANCEL]])


def target_confirm_keyboard() -> ReplyKeyboardMarkup:
    return _markup(
        [
            ["✅ Simpan", "✏ Edit"],
            [BTN_CANCEL, BTN_BACK],
        ]
    )


def target_edit_pick_keyboard() -> ReplyKeyboardMarkup:
    return _markup(
        [
            ["✏ Nama Target", "💰 Nominal Target"],
            ["🏷 Nominal Awal", "📝 Catatan"],
            ["✅ Simpan", BTN_BACK],
        ]
    )


def target_amount_keyboard() -> ReplyKeyboardMarkup:
    return _markup([[BTN_BACK, BTN_CANCEL]])


def target_delete_confirm_keyboard() -> ReplyKeyboardMarkup:
    return _markup(
        [
            ["🗑 Ya, Hapus"],
            ["❌ Batal", BTN_BACK],
        ]
    )
