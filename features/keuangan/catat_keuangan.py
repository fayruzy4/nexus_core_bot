from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, CommandHandler, filters

from config import (
    MAIN_MENU, BTN_KEUANGAN, BTN_CATAT, BTN_HUTANG, BTN_ADD, BTN_HISTORY, BTN_REPORT, BTN_SETTINGS, BTN_BACK,
    BTN_INCOME, BTN_EXPENSE, BTN_SKIP_NOTE, BTN_TODAY, BTN_CUSTOM_DATE, BTN_SAVE, BTN_EDIT, BTN_CANCEL,
    BTN_PERIOD_TODAY, BTN_PERIOD_WEEK, BTN_PERIOD_MONTH, BTN_PERIOD_ALL, BTN_PERIOD_SEARCH,
    BTN_REPORT_1M, BTN_REPORT_2M, BTN_REPORT_3M, BTN_REPORT_6M, BTN_REPORT_9M, BTN_REPORT_1Y,
    BTN_SET_BALANCE, BTN_RESET, BTN_EXPORT, BTN_IMPORT, BTN_DELETE_CONFIRM, BTN_DELETE_CANCEL,
    BTN_EDIT_AMOUNT, BTN_EDIT_CATEGORY, BTN_EDIT_NOTE, BTN_EDIT_DATE, BTN_EDIT_TYPE, BTN_EDIT_SAVE, BTN_EDIT_ABORT,
)
from database.queries import (
    get_or_create_user, seed_default_categories, get_user_by_telegram_id, get_user_summary,
    create_transaction, get_categories, list_transactions, get_transaction_by_id, update_transaction,
    delete_transaction, set_initial_balance, reset_user_data, export_user_bundle, import_user_bundle,
    get_report_rows,
)
from features.keuangan.keyboard import (
    main_menu, keuangan_gate, catat_dashboard, add_type, note_keyboard, date_keyboard, confirm_keyboard,
    history_period_keyboard, report_period_keyboard, settings_keyboard, delete_confirm_keyboard,
    edit_menu_keyboard, categories_keyboard, edit_type_keyboard,
)
from features.keuangan.utils import (
    state, reset_state, set_flow, rupiah, parse_amount, parse_date, today_iso, period_range,
    to_history_key, to_period_key, summarize_rows, build_insights, format_transaction_line, report_days,
    day_label,
)
from features.keuangan.catat_hutang import handle_hutang_text, reset_state as reset_hutang_state
from features.ai.chat_ai import handle_ai_text
from features.ai.voice_handler import handle_ai_voice
from features.keuangan.target import handle_target_text
def register(application: Application) -> None:
    seed_default_categories()
    application.add_handler(CommandHandler(["start", "menu"], start))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(
    MessageHandler(
        filters.VOICE | filters.AUDIO,
        handle_ai_voice,
    )
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db_user = get_or_create_user(user.id, user.username, user.full_name)
    reset_state(user.id)
    await update.message.reply_text(
        "Halo. Masuk ke menu utama dulu.",
        reply_markup=main_menu(),
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db_user = get_or_create_user(user.id, user.username, user.full_name)
    s = state(user.id)
    if s["flow"] != "import":
        await update.message.reply_text("File ini belum dipakai di alur sekarang.", reply_markup=catat_dashboard())
        return
    doc = update.message.document
    file = await context.bot.get_file(doc.file_id)
    data = await file.download_as_bytearray()
    try:
        payload = json.loads(data.decode("utf-8"))
        import_user_bundle(db_user["id"], payload)
        reset_state(user.id)
        await send_dashboard(update, db_user["id"])
    except Exception:
        await update.message.reply_text("Isi file JSON-nya belum kebaca. Coba kirim file yang valid.", reply_markup=settings_keyboard())

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db_user = get_or_create_user(user.id, user.username, user.full_name)
    s = state(user.id)
    text = (update.message.text or "").strip()
    if await handle_ai_text(update, context, db_user, text):
        return
    
   
    if await handle_target_text(update, context, db_user, text):
        return

    if text == MAIN_MENU:
        reset_state(user.id)
        reset_hutang_state(user.id)
        await update.message.reply_text("Pilih menu.", reply_markup=main_menu())
        return

    if s["flow"] == "import":
        if text == BTN_BACK:
            reset_state(user.id)
            await send_dashboard(update, db_user["id"])
            return
        try:
            payload = json.loads(text)
            import_user_bundle(db_user["id"], payload)
            reset_state(user.id)
            await send_dashboard(update, db_user["id"])
        except Exception:
            await update.message.reply_text("Format JSON belum valid. Kirim JSON yang benar atau file dokumentasinya.", reply_markup=settings_keyboard())
        return

    if s["flow"] == "add":
        await handle_add_flow(update, db_user, text)
        return

    if s["flow"] == "history":
        await handle_history_flow(update, db_user, text)
        return

    if s["flow"] == "report":
        await handle_report_flow(update, db_user, text)
        return

    if s["flow"] == "settings":
        await handle_settings_flow(update, db_user, text)
        return

    if s["flow"] == "edit":
        await handle_edit_flow(update, db_user, text)
        return

    if await handle_hutang_text(update, context, db_user, text):
        return

    if text == BTN_ADD:
        reset_state(user.id)
        reset_hutang_state(user.id)
        s = state(user.id)
        s["flow"] = "add"
        s["step"] = "type"
        await update.message.reply_text("Mau nyatet apa nih?", reply_markup=add_type())
        return

    if text == BTN_HISTORY:
        reset_state(user.id)
        reset_hutang_state(user.id)
        s = state(user.id)
        s["flow"] = "history"
        s["step"] = "period"
        await update.message.reply_text("Mau lihat periode yang mana?", reply_markup=history_period_keyboard())
        return

    if text == BTN_REPORT:
        reset_state(user.id)
        reset_hutang_state(user.id)
        s = state(user.id)
        s["flow"] = "report"
        s["step"] = "period"
        await update.message.reply_text("Pilih periode analisis.", reply_markup=report_period_keyboard())
        return

    if text == BTN_SETTINGS:
        reset_state(user.id)
        reset_hutang_state(user.id)
        s = state(user.id)
        s["flow"] = "settings"
        s["step"] = None
        await update.message.reply_text("Pengaturan data transaksi.", reply_markup=settings_keyboard())
        return

    if text == BTN_KEUANGAN:
        reset_state(user.id)
        reset_hutang_state(user.id)
        await update.message.reply_text(
            "Masuk ke modul keuangan dulu.\nLanjut ke catat keuangan.",
            reply_markup=keuangan_gate(),
        )
        return

    if text == BTN_CATAT:
        reset_state(user.id)
        reset_hutang_state(user.id)
        await send_dashboard(update, db_user["id"])
        return

    if text == BTN_BACK:
        reset_state(user.id)
        reset_hutang_state(user.id)
        await update.message.reply_text("Kembali ke menu utama.", reply_markup=main_menu())
        return

    await update.message.reply_text("Pilih tombol yang tersedia.", reply_markup=main_menu())

async def send_dashboard(update: Update, user_id: int) -> None:
    summary = get_user_summary(user_id)
    text = (
        "━━━━━━━━━━━━━━\n"
        "💰 CATAT KEUANGAN\n"
        "━━━━━━━━━━━━━━\n\n"
        f"Saldo Saat Ini\n{rupiah(summary['saldo'])}\n\n"
        f"Pemasukan\n{rupiah(summary['pemasukan'])}\n\n"
        f"Pengeluaran\n{rupiah(summary['pengeluaran'])}\n\n"
        f"Jumlah Transaksi\n{summary['jumlah_transaksi']}\n\n"
        "Ada yang mau dilakukan?"
    )
    await update.message.reply_text(text, reply_markup=catat_dashboard())

async def handle_add_flow(update: Update, user: Dict[str, Any], text: str) -> None:
    s = state(update.effective_user.id)

    if text == BTN_BACK or text == BTN_CANCEL:
        reset_state(update.effective_user.id)
        await send_dashboard(update, user["id"])
        return

    if s["step"] == "type":
        if text not in {BTN_INCOME, BTN_EXPENSE}:
            await update.message.reply_text("Pilih pemasukan atau pengeluaran dulu.", reply_markup=add_type())
            return
        s["payload"] = {
            "jenis": "pemasukan" if text == BTN_INCOME else "pengeluaran",
            "nominal": None,
            "kategori": None,
            "catatan": "",
            "tanggal_transaksi": today_iso(),
        }
        s["step"] = "amount"
        await update.message.reply_text("Oke, masukin nominalnya ya 😄\nContoh: 25000", reply_markup=note_keyboard())
        return

    if s["step"] == "amount":
        amount = parse_amount(text)
        if not amount or amount <= 0:
            await update.message.reply_text("Nominalnya belum kebaca. Tulis angka saja, misal 25000.", reply_markup=note_keyboard())
            return
        s["payload"]["nominal"] = amount
        s["step"] = "category"
        cats = get_categories(user["id"], s["payload"]["jenis"])
        await update.message.reply_text("Ini masuk kategori apa nih?", reply_markup=categories_keyboard(cats))
        return

    if s["step"] == "category":
        cats = get_categories(user["id"], s["payload"]["jenis"])
        valid = {f"{c.get('emoji','')} {c['nama']}".strip() for c in cats}
        if text not in valid and text != BTN_BACK:
            await update.message.reply_text("Pilih kategori dari tombol yang ada.", reply_markup=categories_keyboard(cats))
            return
        s["payload"]["kategori"] = text
        s["step"] = "note"
        await update.message.reply_text("Catatannya mau diisi apa? Kalau nggak ada, klik Lewati.", reply_markup=note_keyboard())
        return

    if s["step"] == "note":
        if text == BTN_SKIP_NOTE:
            s["payload"]["catatan"] = ""
        else:
            s["payload"]["catatan"] = text
        s["step"] = "date"
        await update.message.reply_text("Mau pakai tanggal hari ini atau tulis sendiri?", reply_markup=date_keyboard())
        return

    if s["step"] == "date":
        if text == BTN_TODAY:
            s["payload"]["tanggal_transaksi"] = today_iso()
            s["step"] = "confirm"
            await show_add_confirm(update, s["payload"])
            return
        if text == BTN_CUSTOM_DATE:
            s["step"] = "date_input"
            await update.message.reply_text("Tulis tanggalnya ya.\nFormat: DD-MM-YYYY", reply_markup=date_keyboard())
            return
        await update.message.reply_text("Pilih tanggal dulu.", reply_markup=date_keyboard())
        return

    if s["step"] == "date_input":
        dt = parse_date(text)
        if not dt:
            await update.message.reply_text("Format tanggalnya belum pas. Pakai DD-MM-YYYY.", reply_markup=date_keyboard())
            return
        s["payload"]["tanggal_transaksi"] = dt
        s["step"] = "confirm"
        await show_add_confirm(update, s["payload"])
        return

    if s["step"] == "confirm":
        if text == BTN_EDIT:
            s["step"] = "type"
            await update.message.reply_text("Ulang dari awal ya. Pilih jenis transaksi.", reply_markup=add_type())
            return
        if text == BTN_SAVE:
            p = s["payload"]
            create_transaction(
                user["id"],
                p["jenis"],
                int(p["nominal"]),
                p["kategori"],
                p["catatan"],
                p["tanggal_transaksi"],
            )
            reset_state(update.effective_user.id)
            await update.message.reply_text("Sip, udah aku simpan.", reply_markup=catat_dashboard())
            await send_dashboard(update, user["id"])
            return
        if text == BTN_CANCEL:
            reset_state(update.effective_user.id)
            await send_dashboard(update, user["id"])
            return

    if s["step"] is None:
        if text == BTN_ADD:
            s["flow"] = "add"
            s["step"] = "type"
            await update.message.reply_text("Mau nyatet apa nih?", reply_markup=add_type())
            return

async def show_add_confirm(update: Update, payload: Dict[str, Any]) -> None:
    text = (
        "Cek dulu ya:\n\n"
        f"Jenis: {payload['jenis']}\n"
        f"Nominal: {rupiah(payload['nominal'])}\n"
        f"Kategori: {payload['kategori']}\n"
        f"Catatan: {payload['catatan'] or '-'}\n"
        f"Tanggal: {payload['tanggal_transaksi']}\n\n"
        "Kalau udah pas, simpan aja."
    )
    await update.message.reply_text(text, reply_markup=confirm_keyboard())

async def handle_history_flow(update: Update, user: Dict[str, Any], text: str) -> None:
    s = state(update.effective_user.id)

    if text == BTN_BACK or text == BTN_CANCEL:
        reset_state(update.effective_user.id)
        await send_dashboard(update, user["id"])
        return

    if s["step"] == "period":
        key = to_history_key(text)
        if not key:
            await update.message.reply_text("Pilih periode dari tombol yang ada.", reply_markup=history_period_keyboard())
            return
        if key == "search":
            s["step"] = "search_text"
            await update.message.reply_text("Tulis kata kunci yang mau dicari.", reply_markup=history_period_keyboard())
            return
        if key == "today":
            start, end = period_range("today")
        elif key == "week":
            start, end = period_range("week")
        elif key == "month":
            start, end = period_range("month")
        else:
            start, end = "1970-01-01", date.today().isoformat()
        rows = list_transactions(user["id"], start, end)
        await show_history_list(update, s, rows, f"Riwayat {text}")
        return

    if s["step"] == "search_text":
        rows = list_transactions(user["id"], search=text)
        await show_history_list(update, s, rows, f"Hasil pencarian: {text}")
        return

    if s["step"] == "pick_item":
        if not text.isdigit():
            await update.message.reply_text("Ketik nomor transaksi yang ada di daftar.", reply_markup=history_period_keyboard())
            return
        idx = int(text) - 1
        items = s.get("items") or []
        if idx < 0 or idx >= len(items):
            await update.message.reply_text("Nomornya belum cocok.", reply_markup=history_period_keyboard())
            return
        tx = items[idx]
        s["selected_tx"] = tx["id"]
        s["step"] = "detail"
        detail = (
            f"Detail Transaksi\n\n"
            f"{'💵' if tx['jenis']=='pemasukan' else '💸'} {tx['jenis'].title()}\n"
            f"Nominal: {rupiah(tx['nominal'])}\n"
            f"Kategori: {tx['kategori']}\n"
            f"Catatan: {tx['catatan'] or '-'}\n"
            f"Tanggal: {tx['tanggal_transaksi']}\n"
        )
        await update.message.reply_text(detail, reply_markup=edit_menu_keyboard())
        return

    if s["step"] is None:
        if text == BTN_HISTORY:
            s["flow"] = "history"
            s["step"] = "period"
            await update.message.reply_text("Mau lihat periode yang mana?", reply_markup=history_period_keyboard())
            return

async def show_history_list(update: Update, s: Dict[str, Any], rows: List[Dict[str, Any]], title: str) -> None:
    s["items"] = rows
    if not rows:
        reset_state(update.effective_user.id)
        await update.message.reply_text("Hmm, belum ada transaksi di periode ini.", reply_markup=catat_dashboard())
        return
    text = [title, ""]
    for i, tx in enumerate(rows[:20], 1):
        text.append(format_transaction_line(i, tx))
        text.append("──────────")
    text.append("\nKetik nomor transaksi buat lihat detail.")
    s["step"] = "pick_item"
    await update.message.reply_text("\n".join(text), reply_markup=history_period_keyboard())

async def handle_report_flow(update: Update, user: Dict[str, Any], text: str) -> None:
    s = state(update.effective_user.id)

    if text == BTN_BACK or text == BTN_CANCEL:
        reset_state(update.effective_user.id)
        await send_dashboard(update, user["id"])
        return

    if s["step"] == "period":
        key = to_period_key(text)
        if not key:
            await update.message.reply_text("Pilih periode laporan dari tombol yang ada.", reply_markup=report_period_keyboard())
            return
        days = report_days(key)
        end = date.today()
        start = end - timedelta(days=days - 1)
        prev_end = start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=days - 1)

        current_rows = get_report_rows(user["id"], start.isoformat(), end.isoformat())
        previous_rows = get_report_rows(user["id"], prev_start.isoformat(), prev_end.isoformat())
        current = summarize_rows(current_rows, saldo_awal=0)
        insights = build_insights(current_rows, previous_rows)

        header = (
            f"📊 Laporan {text}\n\n"
            f"Total Pemasukan: {rupiah(current['pemasukan'])}\n"
            f"Total Pengeluaran: {rupiah(current['pengeluaran'])}\n"
            f"Saldo Bersih: {rupiah(current['saldo'])}\n"
            f"Jumlah Transaksi: {current['count']}\n\n"
            "Evaluasi:\n"
            + "\n".join([f"• {x}" for x in insights])
        )
        await update.message.reply_text(header, reply_markup=report_period_keyboard())

        charts = [
            (create_pie_chart(current_rows, f"Distribusi Pengeluaran {text}"), "Pie chart"),
            (create_line_chart(current_rows, f"Tren Transaksi {text}"), "Line chart"),
            (create_bar_chart(current_rows, f"Perbandingan Kategori {text}"), "Bar chart"),
            (create_area_chart(current_rows, f"Saldo Bersih {text}"), "Area chart"),
        ]
        for path, cap in charts:
            if path:
                with open(path, "rb") as f:
                    await update.message.reply_photo(photo=f, caption=cap)
        reset_state(update.effective_user.id)
        await send_dashboard(update, user["id"])
        return

    if s["step"] is None:
        if text == BTN_REPORT:
            s["flow"] = "report"
            s["step"] = "period"
            await update.message.reply_text("Pilih periode analisis.", reply_markup=report_period_keyboard())
            return

async def handle_settings_flow(update: Update, user: Dict[str, Any], text: str) -> None:
    s = state(update.effective_user.id)

    if text == BTN_BACK or text == BTN_CANCEL:
        reset_state(update.effective_user.id)
        await send_dashboard(update, user["id"])
        return

    if s["step"] == "set_balance":
        amount = parse_amount(text)
        if amount is None:
            await update.message.reply_text("Tulis angka saldo awalnya ya.", reply_markup=settings_keyboard())
            return
        set_initial_balance(user["id"], amount)
        reset_state(update.effective_user.id)
        await update.message.reply_text("Saldo awal sudah disimpan.", reply_markup=catat_dashboard())
        await send_dashboard(update, user["id"])
        return

    if s["step"] == "reset_confirm":
        if text == BTN_DELETE_CONFIRM:
            reset_user_data(user["id"])
            reset_state(update.effective_user.id)
            await update.message.reply_text("Semua data sudah dihapus.", reply_markup=catat_dashboard())
            await send_dashboard(update, user["id"])
            return
        if text == BTN_DELETE_CANCEL:
            reset_state(update.effective_user.id)
            await send_dashboard(update, user["id"])
            return

    if s["step"] == "import_wait":
        return

    if s["step"] is None:
        if text == BTN_SETTINGS:
            s["flow"] = "settings"
            s["step"] = None
            await update.message.reply_text("Pengaturan data transaksi.", reply_markup=settings_keyboard())
            return
        if text == BTN_SET_BALANCE:
            s["step"] = "set_balance"
            await update.message.reply_text("Tulis saldo awalnya.", reply_markup=settings_keyboard())
            return
        if text == BTN_RESET:
            s["step"] = "reset_confirm"
            await update.message.reply_text("Yakin mau hapus semua data transaksi?", reply_markup=delete_confirm_keyboard())
            return
        if text == BTN_EXPORT:
            bundle = export_user_bundle(user["id"])
            payload = json.dumps(bundle, ensure_ascii=False, indent=2)
            await update.message.reply_document(document=payload.encode("utf-8"), filename="nexus_export.json")
            await update.message.reply_text("File export sudah dikirim.", reply_markup=settings_keyboard())
            return
        if text == BTN_IMPORT:
            s["step"] = "import_wait"
            s["flow"] = "import"
            await update.message.reply_text("Kirim file JSON export atau paste JSON-nya langsung.", reply_markup=settings_keyboard())
            return

async def handle_edit_flow(update: Update, user: Dict[str, Any], text: str) -> None:
    s = state(update.effective_user.id)
    tx_id = s.get("selected_tx")
    if not tx_id:
        reset_state(update.effective_user.id)
        await send_dashboard(update, user["id"])
        return

    if text == BTN_BACK or text == BTN_EDIT_ABORT or text == BTN_CANCEL:
        reset_state(update.effective_user.id)
        await send_dashboard(update, user["id"])
        return

    tx = get_transaction_by_id(user["id"], tx_id)
    if not tx:
        reset_state(update.effective_user.id)
        await send_dashboard(update, user["id"])
        return

    if s["step"] is None:
        s["flow"] = "edit"
        s["step"] = "pick_field"
        s["payload"] = {
            "jenis": tx["jenis"],
            "nominal": int(tx["nominal"]),
            "kategori": tx["kategori"],
            "catatan": tx.get("catatan") or "",
            "tanggal_transaksi": tx["tanggal_transaksi"],
        }
        await update.message.reply_text("Mau ubah bagian yang mana?", reply_markup=edit_menu_keyboard())
        return

    payload = s["payload"]

    if s["step"] == "pick_field":
        if text == BTN_EDIT_AMOUNT:
            s["step"] = "amount"
            await update.message.reply_text("Tulis nominal barunya.", reply_markup=edit_menu_keyboard())
            return
        if text == BTN_EDIT_CATEGORY:
            s["step"] = "category"
            cats = get_categories(user["id"], payload["jenis"])
            await update.message.reply_text("Pilih kategori barunya.", reply_markup=categories_keyboard(cats))
            return
        if text == BTN_EDIT_NOTE:
            s["step"] = "note"
            await update.message.reply_text("Tulis catatan barunya. Kalau mau kosongkan, kirim tanda minus (-).", reply_markup=edit_menu_keyboard())
            return
        if text == BTN_EDIT_DATE:
            s["step"] = "date"
            await update.message.reply_text("Tulis tanggal baru. Format DD-MM-YYYY.", reply_markup=edit_menu_keyboard())
            return
        if text == BTN_EDIT_TYPE:
            s["step"] = "type"
            await update.message.reply_text("Pilih jenis barunya.", reply_markup=edit_type_keyboard())
            return
        if text == BTN_EDIT_SAVE:
            update_transaction(tx_id, payload)
            reset_state(update.effective_user.id)
            await update.message.reply_text("Perubahan sudah disimpan.", reply_markup=catat_dashboard())
            await send_dashboard(update, user["id"])
            return

    if s["step"] == "amount":
        amount = parse_amount(text)
        if not amount:
            await update.message.reply_text("Nominalnya belum kebaca.", reply_markup=edit_menu_keyboard())
            return
        payload["nominal"] = amount
        s["step"] = "pick_field"
        await update.message.reply_text("Nominal sudah diubah.", reply_markup=edit_menu_keyboard())
        return

    if s["step"] == "category":
        cats = get_categories(user["id"], payload["jenis"])
        valid = {f"{c.get('emoji','')} {c['nama']}".strip() for c in cats}
        if text not in valid and text != BTN_BACK:
            await update.message.reply_text("Pilih kategori dari tombol yang ada.", reply_markup=categories_keyboard(cats))
            return
        payload["kategori"] = text
        s["step"] = "pick_field"
        await update.message.reply_text("Kategori sudah diubah.", reply_markup=edit_menu_keyboard())
        return

    if s["step"] == "note":
        payload["catatan"] = "" if text == "-" else text
        s["step"] = "pick_field"
        await update.message.reply_text("Catatan sudah diubah.", reply_markup=edit_menu_keyboard())
        return

    if s["step"] == "date":
        dt = parse_date(text)
        if not dt:
            await update.message.reply_text("Format tanggal belum pas.", reply_markup=edit_menu_keyboard())
            return
        payload["tanggal_transaksi"] = dt
        s["step"] = "pick_field"
        await update.message.reply_text("Tanggal sudah diubah.", reply_markup=edit_menu_keyboard())
        return

    if s["step"] == "type":
        if text not in {BTN_INCOME, BTN_EXPENSE}:
            await update.message.reply_text("Pilih jenis transaksi dari tombol.", reply_markup=edit_type_keyboard())
            return
        payload["jenis"] = "pemasukan" if text == BTN_INCOME else "pengeluaran"
        cats = get_categories(user["id"], payload["jenis"])
        s["step"] = "category"
        await update.message.reply_text("Sekarang pilih kategori yang cocok.", reply_markup=categories_keyboard(cats))
        return

async def handle_confirm_delete(update: Update, user: Dict[str, Any], tx_id: int) -> None:
    delete_transaction(tx_id)
    reset_state(update.effective_user.id)
    await update.message.reply_text("Transaksinya sudah dihapus.", reply_markup=catat_dashboard())
    await send_dashboard(update, user["id"])
