from __future__ import annotations

from typing import Any, Dict, List, Optional

from telegram import Update
from telegram.ext import ContextTypes

from config import (
    MAIN_MENU,
    BTN_KEUANGAN,
    BTN_HUTANG,
    BTN_BACK,
    BTN_CANCEL,
    BTN_SAVE,
    BTN_SKIP_NOTE,
    BTN_YES,
    BTN_DELETE_CONFIRM,
    BTN_DELETE_CANCEL,
    BTN_DEBT_PERSON,
    BTN_DEBT_COMPANY,
    BTN_PERSON_ADD,
    BTN_PERSON_HISTORY,
    BTN_COMPANY_ADD,
    BTN_COMPANY_LIST,
    BTN_MARK_PAID,
    BTN_DEBT_DELETE,
    BTN_COUNT_OTHER,
)
from database.queries_hutang import (
    STATUS_BELUM,
    STATUS_LUNAS,
    create_person_loan,
    list_person_loans,
    get_person_loan,
    mark_person_loan_paid,
    delete_person_loan,
    get_person_summary,
    create_company_loan,
    list_company_loans,
    get_company_loan_detail,
    mark_company_installment_paid,
    delete_company_loan,
    get_company_summary,
)
from features.keuangan.keyboard import keuangan_gate, main_menu
from features.keuangan.keyboard_hutang import (
    root_keyboard,
    person_dashboard_keyboard,
    company_dashboard_keyboard,
    note_keyboard,
    save_cancel_keyboard,
    yes_cancel_keyboard,
    delete_keyboard,
    count_keyboard,
    person_detail_keyboard,
    company_detail_keyboard,
    list_keyboard,
    add_cancel_keyboard,
)
from features.keuangan.utils import rupiah, parse_amount
from features.keuangan.utils_hutang import (
    state,
    reset_state,
    clear_selection,
    parse_percentage,
    parse_installment_count,
    split_total_into_installments,
    calc_company_total,
    company_percent_label,
    installment_label,
    person_item_label,
    company_item_label,
    note_or_dash,
    count_input_hint,
    percentage_input_hint,
)


def _company_installment_labels(loan: Dict[str, Any]) -> List[str]:
    labels: List[str] = []
    for inst in loan.get("installments") or []:
        labels.append(
            installment_label(
                int(inst["nomor"]),
                int(inst["nominal"]),
                inst.get("status") == STATUS_LUNAS,
            )
        )
    return labels


def _company_installment_map(telegram_id: int) -> Dict[str, int]:
    s = state(telegram_id)
    mapping: Dict[str, int] = {}
    for inst in s.get("installments", []) or []:
        label = installment_label(
            int(inst["nomor"]),
            int(inst["nominal"]),
            inst.get("status") == STATUS_LUNAS,
        )
        mapping[label] = int(inst["id"])
    return mapping


def _current_company_loan_id(telegram_id: int, installment_id: int) -> Optional[int]:
    s = state(telegram_id)
    for inst in s.get("installments", []) or []:
        if int(inst["id"]) == int(installment_id):
            return int(inst["loan_id"])
    return None


def _build_person_list(user_id: int) -> tuple[str, Dict[str, int]]:
    loans = list_person_loans(user_id)
    if not loans:
        return "Belum ada hutang perorangan.", {}

    lines = ["📜 Riwayat Hutang Perorangan", ""]
    items: Dict[str, int] = {}
    for idx, loan in enumerate(loans, start=1):
        label = person_item_label(idx, loan["nama"], int(loan["nominal"]), loan.get("status") == STATUS_LUNAS)
        items[label] = int(loan["id"])
        lines.append(label)
        lines.append("──────────")
    lines.append("Tekan salah satu tombol buat lihat detail.")
    return "\n".join(lines), items


def _build_company_list(user_id: int) -> tuple[str, Dict[str, int]]:
    loans = list_company_loans(user_id)
    if not loans:
        return "Belum ada pinjaman lembaga / pinjol.", {}

    lines = ["📂 Daftar Pinjaman", ""]
    items: Dict[str, int] = {}
    for idx, loan in enumerate(loans, start=1):
        detail = get_company_loan_detail(user_id, int(loan["id"]))
        remaining = int(detail["remaining_total"]) if detail else int(loan["total"])
        label = company_item_label(
            idx,
            loan["nama_lembaga"],
            remaining,
            int(loan["total"]),
            loan.get("status") == STATUS_LUNAS,
        )
        items[label] = int(loan["id"])
        lines.append(label)
        lines.append("──────────")
    lines.append("Tekan salah satu tombol buat lihat detail.")
    return "\n".join(lines), items


def _person_detail_text(loan: Dict[str, Any]) -> str:
    lines = [
        "👤 Hutang Perorangan",
        "",
        f"Nama: {loan['nama']}",
        f"Nominal: {rupiah(int(loan['nominal']))}",
        f"Status: {loan['status']}",
    ]
    catatan = note_or_dash(loan.get("catatan"))
    if catatan != "-":
        lines.append(f"Catatan: {catatan}")
    return "\n".join(lines)


def _company_detail_text(loan: Dict[str, Any]) -> str:
    total = int(loan["total"])
    nominal_awal = int(loan["nominal_awal"])
    bunga = float(loan["bunga"])
    paid_total = int(loan.get("paid_total") or 0)
    remaining_total = int(loan.get("remaining_total") or 0)
    completed_count = int(loan.get("completed_count") or 0)
    count = int(loan["jumlah_cicilan"])
    percentage = company_percent_label(bunga)
    lines = [
        "🏦 Hutang Lembaga / Pinjol",
        "",
        f"Nama: {loan['nama_lembaga']}",
        f"Nominal Awal: {rupiah(nominal_awal)}",
        f"Bunga: {percentage}",
        f"Total Hutang: {rupiah(total)}",
        f"Sudah Dibayar: {rupiah(paid_total)}",
        f"Sisa Hutang: {rupiah(remaining_total)}",
        f"Progress: {completed_count} / {count} cicilan",
        "",
        "Tekan cicilan yang sudah dibayar.",
    ]
    if loan.get("status") == STATUS_LUNAS:
        lines.append("")
        lines.append("🎉 Hutang sudah lunas.")
    return "\n".join(lines)


async def send_root_dashboard(update: Update) -> None:
    await update.message.reply_text(
        "💳 Catat Hutang\n\nPilih jenis hutang dulu ya 👇",
        reply_markup=root_keyboard(),
    )


async def send_person_dashboard(update: Update) -> None:
    summary = get_person_summary(db_user["id"])
    text = (
        "👤 Hutang Perorangan\n\n"
        f"Total Data: {summary['count']}\n"
        f"Total Nilai: {rupiah(summary['total'])}\n"
        f"Masih Belum Lunas: {rupiah(summary['open_total'])}\n\n"
        "Pilih aksi yang mau dilakukan."
    )
    await update.message.reply_text(text, reply_markup=person_dashboard_keyboard())


async def send_company_dashboard(update: Update) -> None:
    summary = get_company_summary(db_user["id"])
    text = (
        "🏦 Hutang Lembaga / Pinjol\n\n"
        f"Total Pinjaman: {summary['count']}\n"
        f"Total Nilai: {rupiah(summary['total'])}\n"
        f"Sisa yang Belum Lunas: {rupiah(summary['open_total'])}\n\n"
        "Pilih aksi yang mau dilakukan."
    )
    await update.message.reply_text(text, reply_markup=company_dashboard_keyboard())


async def _show_person_list(update: Update, user_id: int) -> bool:
    text, items = _build_person_list(user_id)
    s = state(user_id)
    s["items"] = items
    s["step"] = "pick_person"
    if not items:
        await update.message.reply_text(text, reply_markup=person_dashboard_keyboard())
        return True
    await update.message.reply_text(text, reply_markup=list_keyboard(list(items.keys())))
    return True


async def _show_company_list(update: Update, user_id: int) -> bool:
    text, items = _build_company_list(user_id)
    s = state(user_id)
    s["items"] = items
    s["step"] = "pick_company"
    if not items:
        await update.message.reply_text(text, reply_markup=company_dashboard_keyboard())
        return True
    await update.message.reply_text(text, reply_markup=list_keyboard(list(items.keys())))
    return True


async def _show_person_detail(update: Update, telegram_id: int, loan_id: int) -> bool:
    loan = get_person_loan(telegram_id, loan_id)
    if not loan:
        await _show_person_list(update, telegram_id)
        return True

    s = state(telegram_id)
    s["selected_id"] = loan_id
    s["step"] = "person_detail"
    await update.message.reply_text(_person_detail_text(loan), reply_markup=person_detail_keyboard())
    return True


async def _show_company_detail(update: Update, telegram_id: int, loan_id: int) -> bool:
    loan = get_company_loan_detail(telegram_id, loan_id)
    if not loan:
        await _show_company_list(update, telegram_id)
        return True

    s = state(telegram_id)
    s["selected_id"] = loan_id
    s["step"] = "company_detail"
    s["installments"] = loan.get("installments") or []
    buttons = _company_installment_labels(loan)
    await update.message.reply_text(
        _company_detail_text(loan),
        reply_markup=company_detail_keyboard(buttons),
    )
    return True


async def handle_hutang_text(update: Update, context: ContextTypes.DEFAULT_TYPE, db_user: Dict[str, Any], text: str) -> bool:
    user = update.effective_user
    telegram_id = user.id
    s = state(telegram_id)

    if text == MAIN_MENU:
        reset_state(telegram_id)
        await update.message.reply_text("Pilih menu utama dulu.", reply_markup=main_menu())
        return True

    if text == BTN_KEUANGAN:
        reset_state(telegram_id)
        await update.message.reply_text("Masuk ke menu keuangan.", reply_markup=keuangan_gate())
        return True

    if text == BTN_HUTANG:
        reset_state(telegram_id)
        s = state(telegram_id)
        s["flow"] = "root"
        s["step"] = None
        await send_root_dashboard(update)
        return True

    if s["flow"] is None:
        return False

    if s["flow"] == "root":
        return await _handle_root_flow(update, text)

    if s["flow"] == "person":
        return await _handle_person_flow(update, text)

    if s["flow"] == "company":
        return await _handle_company_flow(update, text)

    return False


async def _handle_root_flow(update: Update, text: str) -> bool:
    user_id = db_user["id"]
    s = state(telegram_id)

    if text == BTN_DEBT_PERSON:
        s["flow"] = "person"
        s["step"] = None
        s["payload"] = {}
        clear_selection(telegram_id)
        await send_person_dashboard(update)
        return True

    if text == BTN_DEBT_COMPANY:
        s["flow"] = "company"
        s["step"] = None
        s["payload"] = {}
        clear_selection(telegram_id)
        await send_company_dashboard(update)
        return True

    if text == BTN_BACK:
        reset_state(telegram_id)
        await update.message.reply_text("Kembali ke menu keuangan.", reply_markup=keuangan_gate())
        return True

    await update.message.reply_text("Pilih tombol yang tersedia.", reply_markup=root_keyboard())
    return True


async def _handle_person_flow(update: Update, text: str) -> bool:
    user_id = db_user["id"]
    s = state(telegram_id)

    if text == BTN_BACK and s["step"] in {None, "pick_person"}:
        s["flow"] = "root"
        s["step"] = None
        s["payload"] = {}
        clear_selection(telegram_id)
        await send_root_dashboard(update)
        return True

    if s["step"] is None:
        if text == BTN_PERSON_ADD:
            s["step"] = "person_name"
            s["payload"] = {}
            await update.message.reply_text(
                "Nama orangnya siapa?",
                reply_markup=add_cancel_keyboard(),
            )
            return True

        if text == BTN_PERSON_HISTORY:
            await _show_person_list(update, telegram_id)
            return True

        await update.message.reply_text("Pilih tombol yang tersedia.", reply_markup=person_dashboard_keyboard())
        return True

    if s["step"] == "person_name":
        if text in {BTN_BACK, BTN_CANCEL}:
            s["step"] = None
            s["payload"] = {}
            await send_person_dashboard(update)
            return True
        if not text.strip():
            await update.message.reply_text("Nama orangnya masih kosong.", reply_markup=add_cancel_keyboard())
            return True
        s["payload"]["nama"] = text.strip()
        s["step"] = "person_amount"
        await update.message.reply_text("Nominalnya berapa?", reply_markup=add_cancel_keyboard())
        return True

    if s["step"] == "person_amount":
        if text in {BTN_BACK, BTN_CANCEL}:
            s["step"] = None
            s["payload"] = {}
            await send_person_dashboard(update)
            return True
        amount = parse_amount(text)
        if not amount or amount <= 0:
            await update.message.reply_text("Nominalnya belum kebaca. Tulis angka saja ya.", reply_markup=add_cancel_keyboard())
            return True
        s["payload"]["nominal"] = amount
        s["step"] = "person_note"
        await update.message.reply_text("Catatannya mau diisi apa? Kalau tidak ada, klik Lewati.", reply_markup=note_keyboard())
        return True

    if s["step"] == "person_note":
        if text == BTN_BACK or text == BTN_CANCEL:
            s["step"] = None
            s["payload"] = {}
            await send_person_dashboard(update)
            return True
        if text == BTN_SKIP_NOTE:
            s["payload"]["catatan"] = ""
        else:
            s["payload"]["catatan"] = text.strip()
        payload = s["payload"]
        s["step"] = "person_confirm"
        await update.message.reply_text(
            "Cek dulu ya:\n\n"
            f"Nama: {payload['nama']}\n"
            f"Nominal: {rupiah(int(payload['nominal']))}\n"
            f"Catatan: {payload['catatan'] or '-'}\n\n"
            "Kalau sudah pas, simpan aja.",
            reply_markup=save_cancel_keyboard(),
        )
        return True

    if s["step"] == "person_confirm":
        if text == BTN_SAVE:
            payload = s["payload"]
            create_person_loan(
                user_id,
                payload["nama"],
                int(payload["nominal"]),
                payload.get("catatan") or None,
            )
            s["step"] = None
            s["payload"] = {}
            await update.message.reply_text("Sip, hutang perorangan sudah disimpan.", reply_markup=person_dashboard_keyboard())
            await send_person_dashboard(update)
            return True
        if text in {BTN_CANCEL, BTN_BACK}:
            s["step"] = None
            s["payload"] = {}
            await send_person_dashboard(update)
            return True
        await update.message.reply_text("Pilih Simpan atau Batal.", reply_markup=save_cancel_keyboard())
        return True

    if s["step"] == "pick_person":
        items = s.get("items") or {}
        if text in items:
            await _show_person_detail(update, telegram_id, int(items[text]))
            return True
        if text == BTN_BACK:
            s["step"] = None
            clear_selection(telegram_id)
            await send_person_dashboard(update)
            return True
        await update.message.reply_text("Pilih hutang dari tombol yang ada.", reply_markup=list_keyboard(list(items.keys())))
        return True

    if s["step"] == "person_detail":
        if text == BTN_MARK_PAID:
            s["step"] = "person_paid_confirm"
            await update.message.reply_text(
                "Yakin hutang ini sudah lunas?",
                reply_markup=yes_cancel_keyboard(),
            )
            return True

        if text == BTN_DEBT_DELETE:
            s["step"] = "person_delete_confirm"
            await update.message.reply_text(
                "Yakin mau hapus hutang ini?",
                reply_markup=delete_keyboard(),
            )
            return True

        if text == BTN_BACK:
            await _show_person_list(update, telegram_id)
            return True

        await update.message.reply_text("Pilih tombol yang tersedia.", reply_markup=person_detail_keyboard())
        return True

    if s["step"] == "person_paid_confirm":
        loan_id = s.get("selected_id")
        if text == BTN_YES and loan_id is not None:
            mark_person_loan_paid(telegram_id, int(loan_id))
            s["step"] = None
            s["selected_id"] = None
            await update.message.reply_text("Hutang sudah ditandai lunas.", reply_markup=person_dashboard_keyboard())
            await send_person_dashboard(update)
            return True
        if text in {BTN_CANCEL, BTN_BACK}:
            await _show_person_detail(update, telegram_id, int(loan_id))
            return True
        await update.message.reply_text("Pilih Ya atau Batal.", reply_markup=yes_cancel_keyboard())
        return True

    if s["step"] == "person_delete_confirm":
        loan_id = s.get("selected_id")
        if text == BTN_DELETE_CONFIRM and loan_id is not None:
            delete_person_loan(telegram_id, int(loan_id))
            s["step"] = None
            s["selected_id"] = None
            await update.message.reply_text("Hutang sudah dihapus.", reply_markup=person_dashboard_keyboard())
            await send_person_dashboard(update)
            return True
        if text in {BTN_DELETE_CANCEL, BTN_CANCEL, BTN_BACK}:
            await _show_person_detail(update, telegram_id, int(loan_id))
            return True
        await update.message.reply_text("Pilih HAPUS atau BATAL.", reply_markup=delete_keyboard())
        return True

    await update.message.reply_text("Pilih tombol yang tersedia.", reply_markup=person_dashboard_keyboard())
    return True


async def _show_company_confirm(update: Update, s: Dict[str, Any]) -> None:
    payload = s["payload"]
    nominal_awal = int(payload["nominal_awal"])
    bunga = float(payload["bunga"])
    jumlah_cicilan = int(payload["jumlah_cicilan"])
    total = calc_company_total(nominal_awal, bunga)
    installment_values = split_total_into_installments(total, jumlah_cicilan)
    formatted_installments = "\n".join([f"{idx + 1}. {rupiah(val)}" for idx, val in enumerate(installment_values)])
    await update.message.reply_text(
        "Cek dulu ya:\n\n"
        f"Nama Lembaga: {payload['nama_lembaga']}\n"
        f"Nominal Awal: {rupiah(nominal_awal)}\n"
        f"Bunga: {company_percent_label(bunga)}\n"
        f"Jumlah Cicilan: {jumlah_cicilan}\n"
        f"Total Hutang: {rupiah(total)}\n\n"
        "Perkiraan cicilan tetap:\n"
        f"{formatted_installments}\n\n"
        "Kalau sudah pas, simpan aja.",
        reply_markup=save_cancel_keyboard(),
    )
    s["step"] = "company_confirm"


async def _handle_company_flow(update: Update, text: str) -> bool:
    user_id = db_user["id"]
    s = state(telegram_id)

    if text == BTN_BACK and s["step"] in {None, "pick_company"}:
        s["flow"] = "root"
        s["step"] = None
        s["payload"] = {}
        clear_selection(telegram_id)
        await send_root_dashboard(update)
        return True

    if s["step"] is None:
        if text == BTN_COMPANY_ADD:
            s["step"] = "company_name"
            s["payload"] = {}
            await update.message.reply_text(
                "Nama lembaganya apa?",
                reply_markup=add_cancel_keyboard(),
            )
            return True

        if text == BTN_COMPANY_LIST:
            await _show_company_list(update, telegram_id)
            return True

        await update.message.reply_text("Pilih tombol yang tersedia.", reply_markup=company_dashboard_keyboard())
        return True

    if s["step"] == "company_name":
        if text in {BTN_BACK, BTN_CANCEL}:
            s["step"] = None
            s["payload"] = {}
            await send_company_dashboard(update)
            return True
        if not text.strip():
            await update.message.reply_text("Nama lembaganya masih kosong.", reply_markup=add_cancel_keyboard())
            return True
        s["payload"]["nama_lembaga"] = text.strip()
        s["step"] = "company_amount"
        await update.message.reply_text("Nominal awalnya berapa?", reply_markup=add_cancel_keyboard())
        return True

    if s["step"] == "company_amount":
        if text in {BTN_BACK, BTN_CANCEL}:
            s["step"] = None
            s["payload"] = {}
            await send_company_dashboard(update)
            return True
        amount = parse_amount(text)
        if not amount or amount <= 0:
            await update.message.reply_text("Nominalnya belum kebaca. Tulis angka saja ya.", reply_markup=add_cancel_keyboard())
            return True
        s["payload"]["nominal_awal"] = amount
        s["step"] = "company_bunga"
        await update.message.reply_text(percentage_input_hint(), reply_markup=add_cancel_keyboard())
        return True

    if s["step"] == "company_bunga":
        if text in {BTN_BACK, BTN_CANCEL}:
            s["step"] = None
            s["payload"] = {}
            await send_company_dashboard(update)
            return True
        percent = parse_percentage(text)
        if percent is None:
            await update.message.reply_text(percentage_input_hint(), reply_markup=add_cancel_keyboard())
            return True
        s["payload"]["bunga"] = percent
        s["step"] = "company_count"
        await update.message.reply_text(count_input_hint(), reply_markup=count_keyboard())
        return True

    if s["step"] == "company_count":
        if text in {BTN_BACK, BTN_CANCEL}:
            s["step"] = None
            s["payload"] = {}
            await send_company_dashboard(update)
            return True
        if text == BTN_COUNT_OTHER:
            s["step"] = "company_count_custom"
            await update.message.reply_text("Tulis jumlah cicilannya ya. Contoh: 5", reply_markup=add_cancel_keyboard())
            return True
        count = parse_installment_count(text)
        if count is None:
            await update.message.reply_text(count_input_hint(), reply_markup=count_keyboard())
            return True
        s["payload"]["jumlah_cicilan"] = count
        await _show_company_confirm(update, s)
        return True

    if s["step"] == "company_count_custom":
        if text in {BTN_BACK, BTN_CANCEL}:
            s["step"] = "company_count"
            await update.message.reply_text(count_input_hint(), reply_markup=count_keyboard())
            return True
        count = parse_installment_count(text)
        if count is None:
            await update.message.reply_text("Jumlah cicilannya belum kebaca. Tulis angka saja ya.", reply_markup=add_cancel_keyboard())
            return True
        s["payload"]["jumlah_cicilan"] = count
        await _show_company_confirm(update, s)
        return True

    if s["step"] == "company_confirm":
        if text == BTN_SAVE:
            payload = s["payload"]
            create_company_loan(
                user_id,
                payload["nama_lembaga"],
                int(payload["nominal_awal"]),
                float(payload["bunga"]),
                int(payload["jumlah_cicilan"]),
            )
            s["step"] = None
            s["payload"] = {}
            await update.message.reply_text("Sip, pinjaman sudah disimpan.", reply_markup=company_dashboard_keyboard())
            await send_company_dashboard(update)
            return True
        if text in {BTN_CANCEL, BTN_BACK}:
            s["step"] = None
            s["payload"] = {}
            await send_company_dashboard(update)
            return True
        await update.message.reply_text("Pilih Simpan atau Batal.", reply_markup=save_cancel_keyboard())
        return True

    if s["step"] == "pick_company":
        items = s.get("items") or {}
        if text in items:
            await _show_company_detail(update, telegram_id, int(items[text]))
            return True
        if text == BTN_BACK:
            s["step"] = None
            clear_selection(telegram_id)
            await send_company_dashboard(update)
            return True
        await update.message.reply_text("Pilih pinjaman dari tombol yang ada.", reply_markup=list_keyboard(list(items.keys())))
        return True

    if s["step"] == "company_detail":
        items = _company_installment_map(telegram_id)
        if text in items:
            s["pending_action"] = "installment_paid"
            s["selected_id"] = int(items[text])
            s["step"] = "company_installment_confirm"
            inst = next((x for x in s.get("installments", []) if int(x["id"]) == int(items[text])), None)
            nominal = rupiah(int(inst["nominal"])) if inst else "-"
            nomor = inst["nomor"] if inst else "?"
            await update.message.reply_text(
                f"Yakin cicilan {nomor} sudah dibayar?\nNominal tetap {nominal}.",
                reply_markup=yes_cancel_keyboard(),
            )
            return True

        if text == BTN_DEBT_DELETE:
            s["step"] = "company_delete_confirm"
            await update.message.reply_text(
                "Yakin mau hapus pinjaman ini?",
                reply_markup=delete_keyboard(),
            )
            return True

        if text == BTN_BACK:
            await _show_company_list(update, telegram_id)
            return True

        await update.message.reply_text("Pilih tombol yang tersedia.", reply_markup=company_detail_keyboard(list(items.keys())))
        return True

    if s["step"] == "company_installment_confirm":
        installment_id = s.get("selected_id")
        if text == BTN_YES and installment_id is not None:
            mark_company_installment_paid(int(installment_id))
            loan_id = _current_company_loan_id(telegram_id, int(installment_id))
            s["step"] = None
            s["selected_id"] = None
            s["pending_action"] = None
            if loan_id is not None:
                await _show_company_detail(update, telegram_id, int(loan_id))
                loan = get_company_loan_detail(telegram_id, int(loan_id))
                if loan and loan.get("status") == STATUS_LUNAS:
                    await update.message.reply_text("🎉 Hutangnya sudah lunas.", reply_markup=company_detail_keyboard(_company_installment_labels(loan)))
            else:
                await send_company_dashboard(update)
            return True

        if text in {BTN_CANCEL, BTN_BACK}:
            loan_id = _current_company_loan_id(telegram_id, int(installment_id)) if installment_id is not None else None
            s["step"] = "company_detail"
            s["pending_action"] = None
            s["selected_id"] = loan_id
            if loan_id is not None:
                await _show_company_detail(update, telegram_id, int(loan_id))
            else:
                await send_company_dashboard(update)
            return True

        await update.message.reply_text("Pilih Ya atau Batal.", reply_markup=yes_cancel_keyboard())
        return True

    if s["step"] == "company_delete_confirm":
        loan_id = s.get("selected_id")
        if text == BTN_DELETE_CONFIRM and loan_id is not None:
            delete_company_loan(telegram_id, int(loan_id))
            s["step"] = None
            s["selected_id"] = None
            await update.message.reply_text("Pinjaman sudah dihapus.", reply_markup=company_dashboard_keyboard())
            await send_company_dashboard(update)
            return True
        if text in {BTN_DELETE_CANCEL, BTN_CANCEL, BTN_BACK}:
            await _show_company_detail(update, telegram_id, int(loan_id))
            return True
        await update.message.reply_text("Pilih HAPUS atau BATAL.", reply_markup=delete_keyboard())
        return True

    await update.message.reply_text("Pilih tombol yang tersedia.", reply_markup=company_dashboard_keyboard())
    return True
