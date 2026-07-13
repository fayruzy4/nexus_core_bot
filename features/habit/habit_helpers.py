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

HABIT_STATE_KEY = "habit_state"

def _user(update: Update) -> Dict[str, Any]:
    tg_user = update.effective_user
    return get_or_create_user(tg_user.id, tg_user.username, tg_user.full_name)

def _state(context: ContextTypes.DEFAULT_TYPE) -> Dict[str, Any]:
    if HABIT_STATE_KEY not in context.user_data:
        context.user_data[HABIT_STATE_KEY] = {
            "screen": None,
            "step": None,
            "payload": {},
            "pending": None,
        }
    return context.user_data[HABIT_STATE_KEY]

def _reset_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data[HABIT_STATE_KEY] = {
        "screen": None,
        "step": None,
        "payload": {},
        "pending": None,
    }

def _find_category_emoji(category: str) -> str:
    category = normalize_category(category)
    for name, emoji in CATEGORY_PRESETS:
        if name.lower() == category.lower():
            return emoji
    return "🛰️"

def _parse_diff_button(text: str) -> Optional[Tuple[str, int, str]]:
    if text not in DIFFICULTY_CHOICES:
        return None
    item = DIFFICULTY_CHOICES[text]
    return item["code"], int(item["xp"]), item["label"]

def _reply_message(update: Update, text: str, reply_markup=None):
    return update.effective_message.reply_text(text, reply_markup=reply_markup)

async def _edit_or_reply(query, text: str, reply_markup=None):
    try:
        await query.edit_message_text(text, reply_markup=reply_markup)
    except Exception:
        await query.message.reply_text(text, reply_markup=reply_markup)

async def _send_dashboard(update: Update, user_id: int) -> None:
    snapshot = get_dashboard_snapshot(user_id, today_local())
    await _reply_message(
        update,
        render_dashboard_text(
            snapshot["progression"],
            snapshot["inventory"],
            len(snapshot["habits"]),
            snapshot["completed_today"],
            snapshot["total_today"],
        ),
        reply_markup=habit_main_keyboard(),
    )

async def _send_daily(update: Update, user_id: int) -> None:
    snapshot = get_daily_view_snapshot(user_id, today_local())
    await _reply_message(
        update,
        render_daily_text(snapshot["target_date"], snapshot["progression"], snapshot["inventory"], snapshot["rows"]),
        reply_markup=habit_daily_inline_keyboard(snapshot["rows"]),
    )

async def _send_list(update: Update, user_id: int) -> None:
    snapshot = get_list_snapshot(user_id)
    await _reply_message(
        update,
        render_habits_text(snapshot["habits"]),
        reply_markup=habit_list_inline_keyboard(snapshot["habits"]),
    )

async def _send_progress(update: Update, user_id: int) -> None:
    snapshot = get_progress_snapshot(user_id)
    await _reply_message(
        update,
        render_progress_text(snapshot["progression"], snapshot["inventory"]),
        reply_markup=habit_main_keyboard(),
    )

async def _send_inventory(update: Update, user_id: int) -> None:
    snapshot = get_or_create_inventory(user_id)
    await _reply_message(update, render_inventory_text(snapshot), reply_markup=habit_main_keyboard())

async def _send_achievements(update: Update, user_id: int) -> None:
    await _reply_message(update, render_achievement_text(get_achievements(user_id)), reply_markup=habit_main_keyboard())

async def _send_evaluation(update: Update, user_id: int) -> None:
    snapshot = get_evaluation_snapshot(user_id)
    await _reply_message(
        update,
        render_evaluation_text(snapshot["progression"], snapshot["habits"], snapshot["achievements"], snapshot["active_codes"]),
        reply_markup=habit_main_keyboard(),
    )

async def _send_settings(update: Update) -> None:
    snapshot = get_settings_snapshot()
    await _reply_message(
        update,
        render_settings_text(
            snapshot["daily_brief_time"],
            snapshot["night_alert_time"],
            str(snapshot["notification_channel_id"] or ""),
        ),
        reply_markup=habit_settings_keyboard(),
    )

async def _send_cache(update: Update) -> None:
    await _reply_message(update, render_cache_text(), reply_markup=habit_main_keyboard())

async def _start_add_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    st = _state(context)
    st["screen"] = "add"
    st["step"] = "title"
    st["payload"] = {}
    await _reply_message(update, "Tulis nama habit utamanya.", reply_markup=habit_add_category_keyboard())

async def _start_settings_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    st = _state(context)
    st["screen"] = "settings"
    st["step"] = None
    st["payload"] = {}
    await _send_settings(update)

async def _start_cache_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    st = _state(context)
    st["screen"] = "cache"
    st["step"] = "redeem"
    st["payload"] = {}
    await _reply_message(update, "Kirim kode redeem sekarang atau gunakan /redeem <CODE>.", reply_markup=habit_main_keyboard())

async def _finish_add_flow(update: Update, context: ContextTypes.DEFAULT_TYPE, db_user: Dict[str, Any]) -> None:
    st = _state(context)
    payload = st.get("payload", {})
    try:
        habit = create_habit(
            int(db_user["id"]),
            str(payload.get("title") or ""),
            str(payload.get("category") or ""),
            str(payload.get("difficulty_code") or ""),
        )
    except ValueError as exc:
        reason = str(exc)
        if reason == "habit_title_exists":
            text = "Habit dengan judul itu sudah ada."
        elif reason == "habit_title_empty":
            text = "Judul habit tidak boleh kosong."
        elif reason == "habit_category_empty":
            text = "Kategori habit tidak boleh kosong."
        elif reason == "difficulty_invalid":
            text = "Difficulty tidak valid."
        else:
            text = "Habit gagal dibuat."
        _reset_state(context)
        await _reply_message(update, f"❌ {text}", reply_markup=habit_main_keyboard())
        return

    _reset_state(context)
    await _reply_message(
        update,
        f"✅ Habit berhasil dibuat.\nMulai aktif besok: {habit.get('title')}\n+{habit.get('xp_value')} XP",
        reply_markup=habit_main_keyboard(),
    )

async def _finish_redeem_flow(update: Update, db_user: Dict[str, Any], code: str) -> None:
    try:
        result = redeem_code(int(db_user["id"]), code)
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

async def _finish_settings_input(update: Update, context: ContextTypes.DEFAULT_TYPE, value: str) -> bool:
    st = _state(context)
    step = st.get("step")
    if st.get("screen") != "settings":
        return False

    raw = (value or "").strip()

    if step == "channel":
        set_config_value("notification_channel_id", raw)
        st["step"] = None
        await _reply_message(update, "✅ Channel notifikasi disimpan.", reply_markup=habit_settings_keyboard())
        return True

    if step == "brief_time":
        hhmm = parse_hhmm(raw)
        if not hhmm:
            await _reply_message(update, "Format waktu tidak valid. Pakai HH:MM.", reply_markup=habit_settings_keyboard())
            return True
        set_config_value("daily_brief_time", hhmm)
        st["step"] = None
        await _reply_message(update, "✅ Jam briefing disimpan.", reply_markup=habit_settings_keyboard())
        return True

    if step == "alert_time":
        hhmm = parse_hhmm(raw)
        if not hhmm:
            await _reply_message(update, "Format waktu tidak valid. Pakai HH:MM.", reply_markup=habit_settings_keyboard())
            return True
        set_config_value("night_alert_time", hhmm)
        st["step"] = None
        await _reply_message(update, "✅ Jam alert disimpan.", reply_markup=habit_settings_keyboard())
        return True

    return False

