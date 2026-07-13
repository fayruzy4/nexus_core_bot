from __future__ import annotations

import asyncio
from datetime import datetime, time, timedelta
from typing import Any, Dict, Optional, Tuple

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from config import (
    OWNER_ID,
    BTN_BACK,
    BTN_HABIT,
    BTN_HABIT_DAILY,
    BTN_HABIT_ADD,
    BTN_HABIT_LIST,
    BTN_HABIT_PROGRESS,
    BTN_HABIT_INVENTORY,
    BTN_HABIT_CACHE,
    BTN_HABIT_ACHIEVEMENT,
    BTN_HABIT_EVALUATION,
    BTN_HABIT_SETTINGS,
    BTN_HABIT_SAVE,
    BTN_HABIT_CANCEL,
    BTN_HABIT_SET_CHANNEL,
    BTN_HABIT_SET_BRIEF,
    BTN_HABIT_SET_ALERT,
    BTN_HABIT_CATEGORY_CUSTOM,
    BTN_HABIT_DIFF_VERY_EASY,
    BTN_HABIT_DIFF_EASY,
    BTN_HABIT_DIFF_HARD,
    BTN_HABIT_DIFF_VERY_HARD,
    HABIT_DAILY_BRIEF_TIME,
    HABIT_NIGHT_ALERT_TIME,
)

from database.queries import get_or_create_user
from features.habit.habit_queries import (
    apply_xp,
    create_habit,
    delete_habit,
    ensure_daily_snapshot,
    ensure_defaults,
    evaluate_previous_day,
    get_achievements,
    get_active_reward_codes,
    get_dashboard_snapshot,
    get_daily_row_by_id,
    get_daily_view_snapshot,
    get_evaluation_snapshot,
    get_final_alert_payload,
    get_list_snapshot,
    get_or_create_inventory,
    get_or_create_progression,
    get_progress_snapshot,
    get_recent_events,
    get_settings_snapshot,
    get_config_value,
    list_habits,
    log_event,
    redeem_code,
    set_config_value,
    toggle_daily_row,
)
from features.habit.keyboard_habit import (
    habit_add_category_keyboard,
    habit_add_difficulty_keyboard,
    habit_confirm_keyboard,
    habit_daily_inline_keyboard,
    habit_delete_confirm_inline,
    habit_input_keyboard,
    habit_list_inline_keyboard,
    habit_main_keyboard,
    habit_settings_keyboard,
)
from features.habit.render_habit import (
    render_add_confirm_text,
    render_achievement_text,
    render_cache_text,
    render_dashboard_text,
    render_daily_brief_text,
    render_daily_text,
    render_delete_confirm_text,
    render_evaluation_text,
    render_habits_text,
    render_inventory_text,
    render_night_alert_text,
    render_progress_text,
    render_reward_code_text,
    render_settings_text,
    render_tier_up_text,
)
from features.habit.utils_habit import (
    ACHIEVEMENT_STREAKS,
    CATEGORY_PRESETS,
    DIFFICULTY_CHOICES,
    build_boss_title,
    normalize_category,
    now_local,
    parse_hhmm,
    today_local,
)

from features.habit.habit_scheduler import post_init

from features.habit.habit_helpers import (
    _user,
    _state,
    _reset_state,
    _find_category_emoji,
    _parse_diff_button,
    _reply_message,
    _edit_or_reply,
    _send_dashboard,
    _send_daily,
    _send_list,
    _send_progress,
    _send_inventory,
    _send_achievements,
    _send_evaluation,
    _send_settings,
    _send_cache,
    _start_add_flow,
    _start_settings_flow,
    _start_cache_flow,
    _finish_add_flow,
    _finish_redeem_flow,
    _finish_settings_input,
    _render_daily_query,
    _render_list_query,
)

async def handle_habit_text(update: Update, context: ContextTypes.DEFAULT_TYPE, db_user: Dict[str, Any], text: str) -> bool:
    raw = (text or "").strip()
    if not raw:
        return False

    st = _state(context)
    user_id = int(db_user["id"])

    if raw == BTN_HABIT or raw == "/habit":
        _reset_state(context)
        await _send_dashboard(update, user_id)
        return True

    if st.get("screen") == "add":
        if raw in {BTN_BACK, BTN_HABIT_CANCEL}:
            _reset_state(context)
            await _reply_message(update, "Dibatalkan.", reply_markup=habit_main_keyboard())
            return True

        if st.get("step") == "title":
            st["payload"]["title"] = raw
            st["step"] = "category"
            await _reply_message(update, "Masukkan kategori habit.", reply_markup=habit_add_category_keyboard())
            return True

        if st.get("step") == "category":
            if raw == BTN_HABIT_CATEGORY_CUSTOM:
                st["step"] = "category_custom"
                await _reply_message(update, "Tulis kategori custom-nya.", reply_markup=habit_add_category_keyboard())
                return True
            if raw == BTN_BACK:
                st["step"] = "title"
                await _reply_message(update, "Tulis nama habit utamanya lagi.", reply_markup=habit_add_category_keyboard())
                return True

            category = raw.split(" ", 1)[1].strip() if " " in raw else raw.strip()
            st["payload"]["category"] = category
            st["payload"]["emoji"] = _find_category_emoji(category)
            st["step"] = "difficulty"
            await _reply_message(update, "Pilih difficulty.", reply_markup=habit_add_difficulty_keyboard())
            return True

        if st.get("step") == "category_custom":
            st["payload"]["category"] = raw
            st["payload"]["emoji"] = _find_category_emoji(raw)
            st["step"] = "difficulty"
            await _reply_message(update, "Pilih difficulty.", reply_markup=habit_add_difficulty_keyboard())
            return True

        if st.get("step") == "difficulty":
            diff = _parse_diff_button(raw)
            if not diff:
                await _reply_message(update, "Pilih difficulty dari tombol.", reply_markup=habit_add_difficulty_keyboard())
                return True
            diff_code, xp_value, diff_label = diff
            st["payload"]["difficulty_code"] = diff_code
            st["payload"]["xp_value"] = xp_value
            st["payload"]["difficulty_label"] = diff_label
            st["step"] = "confirm"
            await _reply_message(update, render_add_confirm_text(st["payload"]), reply_markup=habit_confirm_keyboard())
            return True

        if st.get("step") == "confirm":
            if raw == BTN_HABIT_SAVE:
                await _finish_add_flow(update, context, db_user)
                return True
            if raw in {BTN_HABIT_CANCEL, BTN_BACK}:
                _reset_state(context)
                await _reply_message(update, "Dibatalkan.", reply_markup=habit_main_keyboard())
                return True

    if st.get("screen") == "settings":
        if raw in {BTN_BACK, BTN_HABIT_CANCEL}:
            _reset_state(context)
            await _reply_message(update, "Kembali.", reply_markup=habit_main_keyboard())
            return True

        if st.get("step") in {"channel", "brief_time", "alert_time"}:
            return await _finish_settings_input(update, context, raw)

        if raw == BTN_HABIT_SET_CHANNEL:
            st["step"] = "channel"
            await _reply_message(update, "Kirim Channel ID notifikasi (-100...).", reply_markup=habit_input_keyboard())
            return True

        if raw == BTN_HABIT_SET_BRIEF:
            st["step"] = "brief_time"
            await _reply_message(update, "Kirim jam briefing dalam format HH:MM.", reply_markup=habit_input_keyboard())
            return True

        if raw == BTN_HABIT_SET_ALERT:
            st["step"] = "alert_time"
            await _reply_message(update, "Kirim jam alert malam dalam format HH:MM.", reply_markup=habit_input_keyboard())
            return True

    if st.get("screen") == "cache":
        if raw in {BTN_BACK, BTN_HABIT_CANCEL}:
            _reset_state(context)
            await _reply_message(update, "Dibatalkan.", reply_markup=habit_main_keyboard())
            return True
        if st.get("step") == "redeem":
            if raw.startswith("/redeem"):
                parts = raw.split(maxsplit=1)
                if len(parts) < 2:
                    await _reply_message(update, "Pakai: /redeem <CODE>", reply_markup=habit_main_keyboard())
                    return True
                await _finish_redeem_flow(update, db_user, parts[1].strip())
                _reset_state(context)
                return True
            await _finish_redeem_flow(update, db_user, raw)
            _reset_state(context)
            return True

    if raw == BTN_HABIT_DAILY:
        _reset_state(context)
        await _send_daily(update, user_id)
        return True
    if raw == BTN_HABIT_ADD:
        await _start_add_flow(update, context)
        return True
    if raw == BTN_HABIT_LIST:
        _reset_state(context)
        await _send_list(update, user_id)
        return True
    if raw == BTN_HABIT_PROGRESS:
        _reset_state(context)
        await _send_progress(update, user_id)
        return True
    if raw == BTN_HABIT_INVENTORY:
        _reset_state(context)
        await _send_inventory(update, user_id)
        return True
    if raw == BTN_HABIT_CACHE:
        await _start_cache_flow(update, context)
        return True
    if raw == BTN_HABIT_ACHIEVEMENT:
        _reset_state(context)
        await _send_achievements(update, user_id)
        return True
    if raw == BTN_HABIT_EVALUATION:
        _reset_state(context)
        await _send_evaluation(update, user_id)
        return True
    if raw == BTN_HABIT_SETTINGS:
        await _start_settings_flow(update, context)
        return True
    if raw == BTN_BACK:
        _reset_state(context)
        await _reply_message(update, "Kembali ke menu utama.", reply_markup=habit_main_keyboard())
        return True

    if st.get("screen") in {"add", "settings", "cache"}:
        return True

    return False

async def _render_daily_query(query, user_id: int):
    snapshot = get_daily_view_snapshot(user_id, today_local())
    await _edit_or_reply(query, render_daily_text(snapshot["target_date"], snapshot["progression"], snapshot["inventory"], snapshot["rows"]), habit_daily_inline_keyboard(snapshot["rows"]))

async def _render_list_query(query, user_id: int):
    snapshot = get_list_snapshot(user_id)
    await _edit_or_reply(query, render_habits_text(snapshot["habits"]), habit_list_inline_keyboard(snapshot["habits"]))

async def handle_habit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("habit:"):
        return False

    await query.answer()
    db_user = _user(update)
    user_id = int(db_user["id"])

    data = query.data.split(":")
    action = data[1] if len(data) > 1 else ""

    if action == "dashboard":
        _reset_state(context)
        snapshot = get_dashboard_snapshot(user_id, today_local())
        await _edit_or_reply(
            query,
            render_dashboard_text(
                snapshot["progression"],
                snapshot["inventory"],
                len(snapshot["habits"]),
                snapshot["completed_today"],
                snapshot["total_today"],
            ),
            habit_main_keyboard(),
        )
        return True

    if action in {"refresh_daily", "daily"}:
        await _render_daily_query(query, user_id)
        return True

    if action in {"refresh_list", "list"}:
        await _render_list_query(query, user_id)
        return True

    if action == "progress":
        snapshot = get_progress_snapshot(user_id)
        await _edit_or_reply(query, render_progress_text(snapshot["progression"], snapshot["inventory"]), habit_main_keyboard())
        return True

    if action == "inventory":
        snapshot = get_or_create_inventory(user_id)
        await _edit_or_reply(query, render_inventory_text(snapshot), habit_main_keyboard())
        return True

    if action == "achievement":
        await _edit_or_reply(query, render_achievement_text(get_achievements(user_id)), habit_main_keyboard())
        return True

    if action == "evaluation":
        snapshot = get_evaluation_snapshot(user_id)
        await _edit_or_reply(
            query,
            render_evaluation_text(snapshot["progression"], snapshot["habits"], snapshot["achievements"], snapshot["active_codes"]),
            habit_main_keyboard(),
        )
        return True

    if action == "settings":
        snapshot = get_settings_snapshot()
        await _edit_or_reply(
            query,
            render_settings_text(
                snapshot["daily_brief_time"],
                snapshot["night_alert_time"],
                str(snapshot["notification_channel_id"] or ""),
            ),
            habit_settings_keyboard(),
        )
        return True

    if action == "toggle" and len(data) >= 3:
        row_id = int(data[2])
        row = get_daily_row_by_id(row_id)
        if not row:
            await query.message.reply_text("Data mission tidak ditemukan.", reply_markup=habit_main_keyboard())
            return True
        if int(row.get("user_id") or 0) != user_id:
            await query.message.reply_text("Data tidak cocok.", reply_markup=habit_main_keyboard())
            return True

        await _edit_or_reply(query, "📡 ACCESSING CORE MEMORY...\nSYNCHRONIZING INTEGRITY.", None)
        await asyncio.sleep(1)

        result = toggle_daily_row(user_id, row_id)
        snapshot = get_daily_view_snapshot(user_id, today_local())
        await _edit_or_reply(
            query,
            render_daily_text(snapshot["target_date"], snapshot["progression"], snapshot["inventory"], snapshot["rows"]),
            habit_daily_inline_keyboard(snapshot["rows"]),
        )

        xp_delta = int(result.get("xp_delta") or 0)
        if xp_delta > 0:
            await query.message.reply_text(
                f"⚡ MATRIX UPDATE IN PROGRESS: INJECTING +{xp_delta} XP TO NEURAL LINK.",
                reply_markup=habit_main_keyboard(),
            )

        for code in result.get("tier_codes", []) or []:
            await query.message.reply_text(render_tier_up_text(code), reply_markup=habit_main_keyboard())

        reward_code = result.get("reward_code")
        if reward_code:
            await query.message.reply_text(render_reward_code_text(reward_code), reply_markup=habit_main_keyboard())
        return True

    if action == "delete" and len(data) >= 3:
        habit_id = int(data[2])
        target = next((item for item in list_habits(user_id) if int(item.get("id") or 0) == habit_id), None)
        if not target:
            await query.message.reply_text("Habit tidak ditemukan.", reply_markup=habit_main_keyboard())
            return True
        await _edit_or_reply(query, render_delete_confirm_text(target), habit_delete_confirm_inline(habit_id))
        return True

    if action == "confirm_delete" and len(data) >= 3:
        habit_id = int(data[2])
        ok = delete_habit(user_id, habit_id)
        if ok:
            await _render_list_query(query, user_id)
            await query.message.reply_text("Habit dihapus permanen.", reply_markup=habit_main_keyboard())
        else:
            await query.message.reply_text("Habit gagal dihapus.", reply_markup=habit_main_keyboard())
        return True

    if action == "cancel_delete":
        await _render_list_query(query, user_id)
        return True

    if action == "back":
        snapshot = get_dashboard_snapshot(user_id, today_local())
        await _edit_or_reply(
            query,
            render_dashboard_text(
                snapshot["progression"],
                snapshot["inventory"],
                len(snapshot["habits"]),
                snapshot["completed_today"],
                snapshot["total_today"],
            ),
            habit_main_keyboard(),
        )
        return True

    return True

async def handle_habit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db_user = _user(update)
    await _send_dashboard(update, int(db_user["id"]))

async def handle_redeem_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db_user = _user(update)
    if not context.args:
        await _reply_message(update, "Pakai: /redeem <CODE>", reply_markup=habit_main_keyboard())
        return
    try:
        result = redeem_code(int(db_user["id"]), " ".join(context.args).strip())
        await _reply_message(update, f"✅ {result.get('message')}", reply_markup=habit_main_keyboard())
    except ValueError as exc:
        reason = str(exc)
        message = {
            "invalid_code": "Kode tidak valid.",
            "expired_code": "Kode sudah expired.",
            "already_used": "Kode sudah dipakai.",
            "not_owner": "Kode ini bukan milikmu.",
            "empty_code": "Kode kosong.",
        }.get(reason, "Kode tidak bisa diproses.")
        await _reply_message(update, f"❌ {message}", reply_markup=habit_main_keyboard())

async def handle_evaluasi_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db_user = _user(update)
    await _send_evaluation(update, int(db_user["id"]))

def register(application: Application) -> None:
    ensure_defaults()
    application.add_handler(CommandHandler("habit", handle_habit_command))
    application.add_handler(CommandHandler("redeem", handle_redeem_command))
    application.add_handler(CommandHandler("evaluasi", handle_evaluasi_command))
    application.add_handler(CallbackQueryHandler(handle_habit_callback, pattern=r"^habit:"))
