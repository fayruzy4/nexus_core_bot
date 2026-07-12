from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple

from telegram import Update
from telegram.ext import ContextTypes

try:
    from config import BTN_BACK, BTN_CANCEL, BTN_TARGET
except Exception:
    BTN_BACK = "⬅️ Kembali"
    BTN_CANCEL = "❌ Batal"
    BTN_TARGET = "🎯 Target"

from database.queries_target import (
    create_target,
    delete_target,
    get_target_by_id,
    get_target_summary,
    list_active_targets,
    list_done_targets,
    update_target_full,
    change_target_balance,
)
from features.keuangan.keyboard_target import (
    target_amount_keyboard,
    target_confirm_keyboard,
    target_create_keyboard,
    target_dashboard_keyboard,
    target_delete_confirm_keyboard,
    target_detail_keyboard_active,
    target_detail_keyboard_done,
    target_edit_pick_keyboard,
    target_list_keyboard,
)
from features.keuangan.utils_target import (
    build_pie_chart,
    calc_detail_metrics,
    format_completion_message,
    format_target_detail,
    format_target_summary,
    parse_amount,
    rupiah,
    safe_text,
)


TARGET_STATES: Dict[int, Dict[str, Any]] = {}


def _state(user_id: int) -> Dict[str, Any]:
    state = TARGET_STATES.setdefault(
        user_id,
        {
            "mode": None,
            "step": None,
            "selected_target_id": None,
            "list_ids": [],
            "list_kind": None,
            "payload": {},
            "delete_target_id": None,
            "pending_field": None,
        },
    )
    return state


def reset_target_state(user_id: int) -> None:
    TARGET_STATES.pop(user_id, None)


def _is_back(text: str) -> bool:
    return text == BTN_BACK


def _is_cancel(text: str) -> bool:
    return text == BTN_CANCEL


def _selection_index(text: str) -> Optional[int]:
    match = re.match(r"^(\d+)\.\s+", text.strip())
    if not match:
        return None
    return int(match.group(1)) - 1


def _send_text(update: Update, text: str, reply_markup=None) -> None:
    return update.message.reply_text(text, reply_markup=reply_markup)


async def _show_dashboard(update: Update, user_id: int) -> None:
    s = _state(user_id)
    s["mode"] = "dashboard"
    s["step"] = "menu"
    summary = get_target_summary(user_id)
    text = (
        "━━━━━━━━━━━━━━\n"
        "🎯 TARGET\n"
        "━━━━━━━━━━━━━━\n\n"
        f"Jumlah Target Aktif: {summary.get('jumlah_aktif', 0)}\n"
        f"Jumlah Target Selesai: {summary.get('jumlah_selesai', 0)}\n"
        f"Total Nominal Target: {rupiah(summary.get('total_nominal_target', 0))}\n"
        f"Total Dana Terkumpul: {rupiah(summary.get('total_dana_terkumpul', 0))}\n"
        f"Total Sisa: {rupiah(summary.get('total_sisa', 0))}\n"
        f"Progress Keseluruhan: {summary.get('progress', 0.0)}%\n\n"
        "Pilih aksi."
    )
    await _send_text(update, text, reply_markup=target_dashboard_keyboard())


async def _show_list(update: Update, user_id: int, mode: str) -> None:
    rows = list_active_targets(user_id) if mode == "active" else list_done_targets(user_id)
    s = _state(user_id)
    s["mode"] = "list"
    s["step"] = "pick"
    s["list_kind"] = mode
    s["list_ids"] = [int(row["id"]) for row in rows]

    if not rows:
        reset_target_state(user_id)
        await _send_text(
            update,
            "Belum ada target di daftar ini.",
            reply_markup=target_dashboard_keyboard(),
        )
        return

    title = "📂 TARGET AKTIF" if mode == "active" else "✅ TARGET SELESAI"
    lines = [
        "━━━━━━━━━━━━━━",
        title,
        "━━━━━━━━━━━━━━",
        "",
    ]
    for idx, row in enumerate(rows, 1):
        name = safe_text(row.get("nama_target"), "(Tanpa Nama)")
        goal = rupiah(row.get("nominal_target", 0))
        gathered = rupiah(row.get("dana_terkumpul", 0))
        lines.append(f"{idx}. {name}")
        lines.append(f"   Target: {goal} | Terkumpul: {gathered}")
    lines.append("")
    lines.append("Pilih target dari tombol di bawah.")
    await _send_text(update, "\n".join(lines), reply_markup=target_list_keyboard(rows, mode=mode))


async def _show_detail(update: Update, user_id: int, target_id: int, *, from_after_save: bool = False) -> None:
    target = get_target_by_id(user_id, target_id)
    if not target:
        await _show_dashboard(update, user_id)
        return

    s = _state(user_id)
    s["mode"] = "detail"
    s["step"] = "view"
    s["selected_target_id"] = target_id
    s["payload"] = {
        "nama_target": target["nama_target"],
        "nominal_target": int(target["nominal_target"]),
        "nominal_awal": int(target["nominal_awal"]),
        "dana_terkumpul": int(target["dana_terkumpul"]),
        "catatan": target.get("catatan") or "",
    }

    detail_text = format_target_detail(target)
    metrics = calc_detail_metrics(target)
    chart_path = build_pie_chart(
        metrics["dana_terkumpul"],
        metrics["sisa_dana"],
        f"Pie Chart {safe_text(target.get('nama_target'))}",
        prefix=f"target_{user_id}_{target_id}",
    )

    await _send_text(update, detail_text, reply_markup=(
        target_detail_keyboard_done()
        if target.get("status") == "SELESAI"
        else target_detail_keyboard_active()
    ))

    try:
        with open(chart_path, "rb") as fh:
            await update.message.reply_photo(photo=fh, caption="Pie chart Dana Terkumpul vs Sisa Dana")
    finally:
        try:
            os.remove(chart_path)
        except OSError:
            pass

    if from_after_save and target.get("status") == "SELESAI":
        await _send_text(
            update,
            format_completion_message(target, s.get("after_save_previous_total", int(target.get("dana_terkumpul", 0) or 0))),
            reply_markup=target_detail_keyboard_done(),
        )


async def _show_summary(update: Update, user_id: int) -> None:
    summary = get_target_summary(user_id)
    text = format_target_summary(summary)
    chart_path = build_pie_chart(
        int(summary.get("total_dana_terkumpul", 0) or 0),
        int(summary.get("total_sisa", 0) or 0),
        "Pie Chart Ringkasan Target",
        prefix=f"target_summary_{user_id}",
    )
    await _send_text(update, text, reply_markup=target_dashboard_keyboard())
    try:
        with open(chart_path, "rb") as fh:
            await update.message.reply_photo(photo=fh, caption="Pie chart keseluruhan")
    finally:
        try:
            os.remove(chart_path)
        except OSError:
            pass


async def _start_create(update: Update, user_id: int) -> None:
    s = _state(user_id)
    s["mode"] = "create"
    s["step"] = "name"
    s["payload"] = {
        "nama_target": "",
        "nominal_target": None,
        "nominal_awal": 0,
        "catatan": "",
    }
    await _send_text(update, "Tulis nama targetnya.", reply_markup=target_create_keyboard())


async def _show_create_confirm(update: Update, user_id: int) -> None:
    s = _state(user_id)
    p = s["payload"]
    text = (
        "━━━━━━━━━━━━━━\n"
        "✅ KONFIRMASI TARGET\n"
        "━━━━━━━━━━━━━━\n\n"
        f"Nama Target: {safe_text(p.get('nama_target'))}\n"
        f"Nominal Target: {rupiah(p.get('nominal_target'))}\n"
        f"Nominal Awal: {rupiah(p.get('nominal_awal'))}\n"
        f"Catatan: {safe_text(p.get('catatan'))}\n\n"
        "Kalau sudah benar, simpan."
    )
    s["step"] = "confirm"
    await _send_text(update, text, reply_markup=target_confirm_keyboard())


async def _finish_create(update: Update, user_id: int) -> None:
    s = _state(user_id)
    p = s["payload"]
    row = create_target(
        user_id,
        p["nama_target"],
        int(p["nominal_target"]),
        int(p.get("nominal_awal") or 0),
        p.get("catatan") or "",
    )
    completed_now = row.get("status") == "SELESAI"
    previous_total = int(p.get("nominal_awal") or 0)
    reset_target_state(user_id)
    if completed_now:
        await _send_text(update, format_completion_message(row, previous_total), reply_markup=target_detail_keyboard_done())
    await _show_detail(update, user_id, int(row["id"]), from_after_save=False)


async def _start_edit(update: Update, user_id: int, target_id: int) -> None:
    target = get_target_by_id(user_id, target_id)
    if not target:
        await _show_dashboard(update, user_id)
        return
    s = _state(user_id)
    s["mode"] = "edit"
    s["step"] = "pick"
    s["selected_target_id"] = target_id
    s["payload"] = {
        "nama_target": target["nama_target"],
        "nominal_target": int(target["nominal_target"]),
        "nominal_awal": int(target["nominal_awal"]),
        "dana_terkumpul": int(target["dana_terkumpul"]),
        "catatan": target.get("catatan") or "",
        "original_dana_terkumpul": int(target["dana_terkumpul"]),
        "original_nominal_awal": int(target["nominal_awal"]),
        "previous_status": target.get("status"),
    }
    await _send_text(update, "Pilih bagian yang mau diubah.", reply_markup=target_edit_pick_keyboard())


async def _save_edit(update: Update, user_id: int) -> None:
    s = _state(user_id)
    target_id = s.get("selected_target_id")
    p = s["payload"]
    original_dana = int(p.get("original_dana_terkumpul", 0))
    original_awal = int(p.get("original_nominal_awal", 0))
    new_awal = int(p.get("nominal_awal", 0))
    dana_terkumpul = max(original_dana - original_awal + new_awal, 0)

    row = update_target_full(
        user_id,
        int(target_id),
        nama_target=p["nama_target"],
        nominal_target=int(p["nominal_target"]),
        nominal_awal=new_awal,
        dana_terkumpul=dana_terkumpul,
        catatan=p.get("catatan") or "",
    )
    previous_status = p.get("previous_status")
    previous_total = original_dana

    reset_target_state(user_id)

    if row and previous_status != "SELESAI" and row.get("status") == "SELESAI":
        await _send_text(update, format_completion_message(row, previous_total), reply_markup=target_detail_keyboard_done())

    await _show_detail(update, user_id, int(target_id), from_after_save=False)


async def _change_balance(update: Update, user_id: int, delta: int) -> None:
    s = _state(user_id)
    target_id = int(s.get("selected_target_id") or 0)
    if not target_id:
        await _show_dashboard(update, user_id)
        return

    target = get_target_by_id(user_id, target_id)
    if not target:
        await _show_dashboard(update, user_id)
        return

    previous_total = int(target.get("dana_terkumpul", 0) or 0)
    try:
        row = change_target_balance(user_id, target_id, delta)
    except ValueError:
        await _send_text(update, "Dana terkumpul tidak boleh negatif.", reply_markup=target_detail_keyboard_active())
        return

    if not row:
        await _show_dashboard(update, user_id)
        return

    reset_target_state(user_id)
    if target.get("status") != "SELESAI" and row.get("status") == "SELESAI":
        await _send_text(update, format_completion_message(row, previous_total), reply_markup=target_detail_keyboard_done())
    await _show_detail(update, user_id, target_id, from_after_save=False)


async def _start_delete(update: Update, user_id: int) -> None:
    s = _state(user_id)
    if not s.get("selected_target_id"):
        await _show_dashboard(update, user_id)
        return
    s["mode"] = "delete"
    s["step"] = "confirm"
    await _send_text(update, "Yakin mau hapus target ini?", reply_markup=target_delete_confirm_keyboard())


async def _finish_delete(update: Update, user_id: int) -> None:
    s = _state(user_id)
    target_id = int(s.get("selected_target_id") or 0)
    if not target_id:
        reset_target_state(user_id)
        await _show_dashboard(update, user_id)
        return
    delete_target(user_id, target_id)
    reset_target_state(user_id)
    await _send_text(update, "Target sudah dihapus.", reply_markup=target_dashboard_keyboard())


async def _handle_create_flow(update: Update, user_id: int, text: str) -> bool:
    s = _state(user_id)
    if s.get("mode") != "create":
        return False

    if _is_back(text) or _is_cancel(text):
        reset_target_state(user_id)
        await _show_dashboard(update, user_id)
        return True

    step = s.get("step")
    payload = s["payload"]

    if step == "name":
        if not text:
            await _send_text(update, "Nama target belum boleh kosong.", reply_markup=target_create_keyboard())
            return True
        payload["nama_target"] = text
        s["step"] = "nominal_target"
        await _send_text(update, "Tulis nominal targetnya.", reply_markup=target_amount_keyboard())
        return True

    if step == "nominal_target":
        amount = parse_amount(text)
        if amount is None or amount <= 0:
            await _send_text(update, "Nominal target harus angka lebih dari 0.", reply_markup=target_amount_keyboard())
            return True
        payload["nominal_target"] = amount
        s["step"] = "nominal_awal"
        await _send_text(update, "Tulis nominal awalnya. Kalau tidak ada, isi 0.", reply_markup=target_amount_keyboard())
        return True

    if step == "nominal_awal":
        amount = parse_amount(text)
        if amount is None or amount < 0:
            await _send_text(update, "Nominal awal harus angka 0 atau lebih.", reply_markup=target_amount_keyboard())
            return True
        payload["nominal_awal"] = amount
        s["step"] = "catatan"
        await _send_text(update, "Tulis catatan kalau ada. Kalau kosong, kirim tanda minus (-).", reply_markup=target_create_keyboard())
        return True

    if step == "catatan":
        payload["catatan"] = "" if text.strip() == "-" else text
        await _show_create_confirm(update, user_id)
        return True

    if step == "confirm":
        if text in {"✅ Simpan"}:
            await _finish_create(update, user_id)
            return True
        if text in {"✏ Edit"}:
            s["step"] = "name"
            await _send_text(update, "Ulang dari nama target. Tulis nama targetnya.", reply_markup=target_create_keyboard())
            return True
        if _is_back(text) or _is_cancel(text):
            reset_target_state(user_id)
            await _show_dashboard(update, user_id)
            return True

    return True


async def _handle_edit_flow(update: Update, user_id: int, text: str) -> bool:
    s = _state(user_id)
    if s.get("mode") != "edit":
        return False

    if _is_back(text) or _is_cancel(text):
        target_id = s.get("selected_target_id")
        if target_id:
            await _show_detail(update, user_id, int(target_id))
        else:
            reset_target_state(user_id)
            await _show_dashboard(update, user_id)
        return True

    step = s.get("step")
    payload = s["payload"]

    if step == "pick":
        if text == "✏ Nama Target":
            s["step"] = "nama_target"
            await _send_text(update, "Tulis nama target barunya.", reply_markup=target_amount_keyboard())
            return True
        if text == "💰 Nominal Target":
            s["step"] = "nominal_target"
            await _send_text(update, "Tulis nominal target barunya.", reply_markup=target_amount_keyboard())
            return True
        if text == "🏷 Nominal Awal":
            s["step"] = "nominal_awal"
            await _send_text(update, "Tulis nominal awal barunya.", reply_markup=target_amount_keyboard())
            return True
        if text == "📝 Catatan":
            s["step"] = "catatan"
            await _send_text(update, "Tulis catatan barunya. Kirim tanda minus (-) untuk mengosongkan.", reply_markup=target_amount_keyboard())
            return True
        if text == "✅ Simpan":
            await _save_edit(update, user_id)
            return True
        await _send_text(update, "Pilih tombol yang tersedia.", reply_markup=target_edit_pick_keyboard())
        return True

    if step == "nama_target":
        if not text:
            await _send_text(update, "Nama target tidak boleh kosong.", reply_markup=target_amount_keyboard())
            return True
        payload["nama_target"] = text
        s["step"] = "pick"
        await _send_text(update, "Nama target disimpan.", reply_markup=target_edit_pick_keyboard())
        return True

    if step == "nominal_target":
        amount = parse_amount(text)
        if amount is None or amount <= 0:
            await _send_text(update, "Nominal target harus angka lebih dari 0.", reply_markup=target_amount_keyboard())
            return True
        payload["nominal_target"] = amount
        s["step"] = "pick"
        await _send_text(update, "Nominal target disimpan.", reply_markup=target_edit_pick_keyboard())
        return True

    if step == "nominal_awal":
        amount = parse_amount(text)
        if amount is None or amount < 0:
            await _send_text(update, "Nominal awal harus 0 atau lebih.", reply_markup=target_amount_keyboard())
            return True
        payload["nominal_awal"] = amount
        s["step"] = "pick"
        await _send_text(update, "Nominal awal disimpan.", reply_markup=target_edit_pick_keyboard())
        return True

    if step == "catatan":
        payload["catatan"] = "" if text.strip() == "-" else text
        s["step"] = "pick"
        await _send_text(update, "Catatan disimpan.", reply_markup=target_edit_pick_keyboard())
        return True

    return True


async def _handle_list_flow(update: Update, user_id: int, text: str) -> bool:
    s = _state(user_id)
    if s.get("mode") != "list":
        return False

    if _is_back(text):
        reset_target_state(user_id)
        await _show_dashboard(update, user_id)
        return True

    if s.get("step") != "pick":
        return True

    idx = _selection_index(text)
    if idx is None:
        kind = s.get("list_kind") or "active"
        rows = list_active_targets(user_id) if kind == "active" else list_done_targets(user_id)
        await _send_text(update, "Pilih target dari tombol yang tersedia.", reply_markup=target_list_keyboard(rows, mode=kind))
        return True

    list_ids = s.get("list_ids") or []
    if idx < 0 or idx >= len(list_ids):
        await _send_text(update, "Target yang dipilih belum cocok.", reply_markup=target_dashboard_keyboard())
        return True

    target_id = int(list_ids[idx])
    await _show_detail(update, user_id, target_id)
    return True


async def _handle_detail_flow(update: Update, user_id: int, text: str) -> bool:
    s = _state(user_id)
    if s.get("mode") != "detail":
        return False

    target_id = int(s.get("selected_target_id") or 0)
    target = get_target_by_id(user_id, target_id) if target_id else None
    if not target:
        reset_target_state(user_id)
        await _show_dashboard(update, user_id)
        return True

    if _is_back(text):
        reset_target_state(user_id)
        await _show_dashboard(update, user_id)
        return True

    if target.get("status") == "SELESAI":
        if text == "🗑 Hapus Target":
            await _start_delete(update, user_id)
            return True
        await _send_text(update, "Gunakan tombol yang tersedia.", reply_markup=target_detail_keyboard_done())
        return True

    if text == "➕ Tambah Dana":
        s["mode"] = "add"
        s["step"] = "amount"
        await _send_text(update, "Tulis nominal dana yang mau ditambahkan.", reply_markup=target_amount_keyboard())
        return True

    if text == "➖ Kurangi Dana":
        s["mode"] = "subtract"
        s["step"] = "amount"
        await _send_text(update, "Tulis nominal dana yang mau dikurangi.", reply_markup=target_amount_keyboard())
        return True

    if text == "✏ Edit Target":
        await _start_edit(update, user_id, target_id)
        return True

    if text == "🗑 Hapus Target":
        await _start_delete(update, user_id)
        return True

    await _send_text(update, "Gunakan tombol yang tersedia.", reply_markup=target_detail_keyboard_active())
    return True


async def _handle_balance_flow(update: Update, user_id: int, text: str) -> bool:
    s = _state(user_id)
    if s.get("mode") not in {"add", "subtract"}:
        return False

    if _is_back(text) or _is_cancel(text):
        target_id = int(s.get("selected_target_id") or 0)
        if target_id:
            await _show_detail(update, user_id, target_id)
        else:
            reset_target_state(user_id)
            await _show_dashboard(update, user_id)
        return True

    amount = parse_amount(text)
    if amount is None or amount <= 0:
        await _send_text(update, "Nominal harus angka lebih dari 0.", reply_markup=target_amount_keyboard())
        return True

    if s["mode"] == "add":
        await _change_balance(update, user_id, amount)
    else:
        await _change_balance(update, user_id, -amount)
    return True


async def _handle_delete_flow(update: Update, user_id: int, text: str) -> bool:
    s = _state(user_id)
    if s.get("mode") != "delete":
        return False

    if _is_back(text) or _is_cancel(text) or text == "❌ Batal":
        target_id = int(s.get("selected_target_id") or 0)
        if target_id:
            await _show_detail(update, user_id, target_id)
        else:
            reset_target_state(user_id)
            await _show_dashboard(update, user_id)
        return True

    if text == "🗑 Ya, Hapus":
        await _finish_delete(update, user_id)
        return True

    await _send_text(update, "Pilih tombol konfirmasi.", reply_markup=target_delete_confirm_keyboard())
    return True


async def handle_target_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_user: Dict[str, Any],
    text: str,
) -> bool:
    user_id = int(db_user["id"])
    text = (text or "").strip()
    s = _state(user_id)

    if text == BTN_TARGET and s.get("mode") is None:
        await _show_dashboard(update, user_id)
        return True

    if s.get("mode") is None:
        return False

    if s.get("mode") == "dashboard":
        if text == "➕ Buat Target":
            await _start_create(update, user_id)
            return True
        if text == "📂 Target Aktif":
            await _show_list(update, user_id, "active")
            return True
        if text == "✅ Target Selesai":
            await _show_list(update, user_id, "done")
            return True
        if text == "📊 Ringkasan Target":
            await _show_summary(update, user_id)
            return True
        if _is_back(text):
            reset_target_state(user_id)
            return False
        await _show_dashboard(update, user_id)
        return True

    if await _handle_create_flow(update, user_id, text):
        return True
    if await _handle_edit_flow(update, user_id, text):
        return True
    if await _handle_list_flow(update, user_id, text):
        return True
    if await _handle_detail_flow(update, user_id, text):
        return True
    if await _handle_balance_flow(update, user_id, text):
        return True
    if await _handle_delete_flow(update, user_id, text):
        return True

    return False
