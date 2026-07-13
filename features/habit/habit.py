from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

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
    BTN_HABIT_DELETE,
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
from database.queries_habit import (
    apply_xp,
    create_habit,
    create_reward_code,
    delete_habit,
    ensure_daily_snapshot,
    ensure_defaults,
    evaluate_previous_day,
    get_achievements,
    get_active_reward_codes,
    get_config_value,
    get_daily_row_by_id,
    get_daily_rows,
    get_evaluation_snapshot,
    get_final_alert_payload,
    get_or_create_inventory,
    get_or_create_progression,
    get_progress_snapshot,
    get_recent_events,
    get_config_value,
    get_daily_briefing_payload,
    get_habit_by_id,
    get_progress_snapshot,
    get_daily_row_by_id,
    get_habit_by_id,
    get_daily_rows,
    get_active_reward_codes,
    get_achievements,
    get_evaluation_snapshot,
    list_habits,
    log_event,
    redeem_code,
    set_config_value,
    update_progress_consistency,
)
from features.habit.keyboard_habit import (
    habit_add_category_keyboard,
    habit_add_difficulty_keyboard,
    habit_confirm_keyboard,
    habit_daily_inline_keyboard,
    habit_delete_confirm_inline,
    habit_list_inline_keyboard,
    habit_main_keyboard,
    habit_settings_keyboard,
)
from features.habit.utils_habit import (
    ACHIEVEMENT_STREAKS,
    CATEGORY_PRESETS,
    DIFFICULTY_CHOICES,
    achievement_line,
    build_boss_title,
    classify_consistency,
    difficulty_label,
    format_date_only,
    format_dt,
    format_moneyless_int,
    habit_item_line,
    mission_line,
    normalize_category,
    now_local,
    parse_hhmm,
    phase_xp_for_tier,
    progress_bar,
    rank_label,
    today_local,
    tier_name,
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


def _dashboard_text(user_id: int) -> str:
    snapshot = get_progress_snapshot(user_id)
    progression = snapshot["progression"]
    inventory = snapshot["inventory"]
    habits = list_habits(user_id)
    today_rows = ensure_daily_snapshot(user_id, today_local())
    completed = sum(1 for row in today_rows if row.get("is_completed"))
    total = len(today_rows)
    streak = int(progression.get("current_streak") or 0)
    shield = int(inventory.get("shield_count") or 0)
    consistency = float(progression.get("consistency_rating") or 0)

    bar = progress_bar(int(progression.get("current_xp_in_rank") or 0), int(progression.get("current_xp_needed") or 100), 10)

    return (
        "━━━━━━━━━━━━━━━━━━\n"
        "🛰️ NEXUS HABIT MATRIX\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"Tier : {progression.get('current_tier_name')} {progression.get('current_rank_label')}\n"
        f"XP   : [{bar}] {int(progression.get('current_xp_in_rank') or 0)} / {int(progression.get('current_xp_needed') or 100)} XP\n"
        f"Streak Link : 🔥 {streak} Hari\n"
        f"Shield Charge : 🛡️ x{shield}\n"
        f"Total Habit Aktif : {len(habits)}\n"
        f"Daily Mission : {completed} / {total}\n"
        f"Consistency : {consistency:.2f}% [{progression.get('consistency_class')}]\n"
    )


def _habits_text(user_id: int) -> str:
    habits = list_habits(user_id)
    if not habits:
        return "━━━━━━━━━━━━━━━━━━\n📜 DAFTAR HABIT\n━━━━━━━━━━━━━━━━━━\n\nBelum ada habit yang didaftarkan."
    lines = [
        "━━━━━━━━━━━━━━━━━━",
        "📜 DAFTAR HABIT",
        "━━━━━━━━━━━━━━━━━━",
        "",
    ]
    for idx, habit in enumerate(habits, 1):
        lines.append(habit_item_line(idx, habit))
        lines.append("──────────")
    return "\n".join(lines)


def _progress_text(user_id: int) -> str:
    snapshot = get_progress_snapshot(user_id)
    progression = snapshot["progression"]
    inventory = snapshot["inventory"]
    bar = progress_bar(int(progression.get("current_xp_in_rank") or 0), int(progression.get("current_xp_needed") or 100), 10)
    return (
        "━━━━━━━━━━━━━━━━━━\n"
        "🎖️ PROGRESS MATRIX\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"Tier        : {progression.get('current_tier_index')} - {progression.get('current_tier_name')}\n"
        f"Rank        : {progression.get('current_rank_label')}\n"
        f"EXP         : [{bar}] {int(progression.get('current_xp_in_rank') or 0)} / {int(progression.get('current_xp_needed') or 100)} XP\n"
        f"Total XP    : {format_moneyless_int(int(progression.get('total_xp') or 0))}\n"
        f"Streak Link : 🔥 {int(progression.get('current_streak') or 0)}\n"
        f"Highest     : {int(progression.get('highest_streak') or 0)}\n"
        f"Shield      : 🛡️ x{int(inventory.get('shield_count') or 0)}\n"
    )


def _inventory_text(user_id: int) -> str:
    inventory = get_or_create_inventory(user_id)
    return (
        "━━━━━━━━━━━━━━━━━━\n"
        "🎒 INVENTORY\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"Shield Charge : 🛡️ x{int(inventory.get('shield_count') or 0)}\n"
        f"Cap           : 2\n"
    )


def _achievement_text(user_id: int) -> str:
    unlocked = {a.get("achievement_key"): a for a in get_achievements(user_id)}
    lines = [
        "━━━━━━━━━━━━━━━━━━",
        "🏆 ACHIEVEMENT",
        "━━━━━━━━━━━━━━━━━━",
        "",
    ]
    for streak, (name, icon) in ACHIEVEMENT_STREAKS.items():
        key = f"STREAK_{streak}"
        lines.append(achievement_line(key in unlocked, icon, name, streak))
    if len(lines) == 4:
        lines.append("Belum ada lencana yang terbuka.")
    return "\n".join(lines)


def _evaluation_text(user_id: int) -> str:
    data = get_evaluation_snapshot(user_id)
    progression = data["progression"]
    habits = data["habits"]
    achievements = data["achievements"]
    active_codes = data["active_codes"]
    return (
        "━━━━━━━━━━━━━━━━━━\n"
        "📊 EVALUASI MATRIX\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"Total Days Monitored : {int(progression.get('total_days_monitored') or 0)}\n"
        f"Total Missions Cleared: {int(progression.get('total_missions_cleared') or 0)}\n"
        f"Total Days Completed  : {int(progression.get('total_days_fully_completed') or 0)}\n"
        f"Current Streak Link   : {int(progression.get('current_streak') or 0)}\n"
        f"Highest Streak Link   : {int(progression.get('highest_streak') or 0)}\n"
        f"Consistency           : {float(progression.get('consistency_rating') or 0):.2f}% [{progression.get('consistency_class')}]\n"
        f"Habits                : {len(habits)}\n"
        f"Achievements          : {len(achievements)}\n"
        f"Active Data Cache     : {len(active_codes)}\n"
    )


def _settings_text() -> str:
    return (
        "━━━━━━━━━━━━━━━━━━\n"
        "⚙️ H ABIT SETTINGS\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"Daily Briefing : {get_config_value('daily_brief_time', HABIT_DAILY_BRIEF_TIME)}\n"
        f"Night Alert    : {get_config_value('night_alert_time', HABIT_NIGHT_ALERT_TIME)}\n"
        f"Channel ID     : {get_config_value('notification_channel_id', '-') or '-'}\n"
    )


def _cache_text() -> str:
    return (
        "━━━━━━━━━━━━━━━━━━\n"
        "🎟️ DATA CACHE\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Gunakan kode redeem yang dikirim sistem dengan command:\n"
        "/redeem <CODE>\n\n"
        "Kode hanya berlaku 4 jam dan hanya untuk owner."
    )


def _daily_text(user_id: int, target_date: Optional[date] = None) -> str:
    target_date = target_date or today_local()
    rows = ensure_daily_snapshot(user_id, target_date)
    progression = get_or_create_progression(user_id)
    inventory = get_or_create_inventory(user_id)
    completed = sum(1 for row in rows if row.get("is_completed"))
    total = len(rows)
    bar = progress_bar(int(progression.get("current_xp_in_rank") or 0), int(progression.get("current_xp_needed") or 100), 10)

    lines = [
        "━━━━━━━━━━━━━━━━━━",
        "📅 DAILY MISSION MATRIX",
        "━━━━━━━━━━━━━━━━━━",
        "",
        f"Date : {target_date.isoformat()}",
        f"Tier : {progression.get('current_tier_name')} {progression.get('current_rank_label')}",
        f"EXP  : [{bar}] {int(progression.get('current_xp_in_rank') or 0)} / {int(progression.get('current_xp_needed') or 100)} XP",
        f"Streak: 🔥 {int(progression.get('current_streak') or 0)} | 🛡️ x{int(inventory.get('shield_count') or 0)}",
        f"Mission: {completed} / {total}",
        "",
    ]
    if not rows:
        lines.append("Belum ada habit aktif.")
    else:
        for idx, row in enumerate(rows, 1):
            lines.append(mission_line(idx, row))
            lines.append("──────────")
    return "\n".join(lines)


def _settings_help_text() -> str:
    return (
        "Gunakan tombol pengaturan untuk mengubah:\n"
        "• Channel notifikasi\n"
        "• Jam briefing pagi\n"
        "• Jam alert malam\n"
    )


def _category_prompt_text() -> str:
    return (
        "Masukkan kategori habit.\n"
        "Contoh: Health, Learning, Coding, Spiritual, Mindset, Life, Work, Other."
    )


def _boss_prompt_text(user_id: int) -> str:
    today = today_local()
    rows = list_habits(user_id)
    return build_boss_title(len(rows)) + f" | {today.isoformat()}"


def _render_add_confirm(payload: Dict[str, Any]) -> str:
    return (
        "━━━━━━━━━━━━━━━━━━\n"
        "➕ TAMBAH HABIT\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"Nama Habit   : {payload.get('title')}\n"
        f"Kategori     : {payload.get('category')}\n"
        f"Emoji        : {payload.get('emoji')}\n"
        f"Difficulty   : {payload.get('difficulty_label')}\n"
        f"XP           : +{payload.get('xp_value')} XP\n"
        f"Mulai Aktif  : Besok\n"
    )


def _send_text(update: Update, text: str, reply_markup=None) -> None:
    return update.effective_message.reply_text(text, reply_markup=reply_markup)


async def _send_dashboard(update: Update, user_id: int) -> None:
    await update.effective_message.reply_text(_dashboard_text(user_id), reply_markup=habit_main_keyboard())


async def _send_daily(update: Update, user_id: int) -> None:
    rows = ensure_daily_snapshot(user_id, today_local())
    await update.effective_message.reply_text(_daily_text(user_id), reply_markup=habit_daily_inline_keyboard(rows))


async def _send_list(update: Update, user_id: int) -> None:
    habits = list_habits(user_id)
    await update.effective_message.reply_text(_habits_text(user_id), reply_markup=habit_list_inline_keyboard(habits))


async def _send_progress(update: Update, user_id: int) -> None:
    await update.effective_message.reply_text(_progress_text(user_id), reply_markup=habit_main_keyboard())


async def _send_inventory(update: Update, user_id: int) -> None:
    await update.effective_message.reply_text(_inventory_text(user_id), reply_markup=habit_main_keyboard())


async def _send_achievements(update: Update, user_id: int) -> None:
    await update.effective_message.reply_text(_achievement_text(user_id), reply_markup=habit_main_keyboard())


async def _send_evaluation(update: Update, user_id: int) -> None:
    await update.effective_message.reply_text(_evaluation_text(user_id), reply_markup=habit_main_keyboard())


async def _send_cache(update: Update) -> None:
    await update.effective_message.reply_text(_cache_text(), reply_markup=habit_main_keyboard())


async def _send_settings(update: Update) -> None:
    await update.effective_message.reply_text(_settings_text(), reply_markup=habit_settings_keyboard())


async def _start_add_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    st = _state(context)
    st["screen"] = "add"
    st["step"] = "title"
    st["payload"] = {}
    await update.effective_message.reply_text("Tulis nama habit utamanya.", reply_markup=habit_add_category_keyboard())


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
    await update.effective_message.reply_text("Kirim kode redeem sekarang atau gunakan /redeem <CODE>.", reply_markup=habit_main_keyboard())


async def _parse_diff_button(text: str) -> Optional[Tuple[str, int, str]]:
    if text not in DIFFICULTY_CHOICES:
        return None
    item = DIFFICULTY_CHOICES[text]
    return item["code"], item["xp"], item["label"]


def _find_category_emoji(category: str) -> str:
    category = normalize_category(category)
    for name, emoji in CATEGORY_PRESETS:
        if name.lower() == category.lower():
            return emoji
    return "🛰️"


async def _finish_add_flow(update: Update, context: ContextTypes.DEFAULT_TYPE, db_user: Dict[str, Any]) -> None:
    st = _state(context)
    payload = st.get("payload", {})
    habit = create_habit(
        int(db_user["id"]),
        payload["title"],
        payload["category"],
        payload["difficulty_code"],
    )
    _reset_state(context)
    await update.effective_message.reply_text(
        f"✅ Habit berhasil dibuat.\nMulai aktif besok: {habit.get('title')}\n+{habit.get('xp_value')} XP",
        reply_markup=habit_main_keyboard(),
    )


async def _finish_redeem_flow(update: Update, db_user: Dict[str, Any], code: str) -> None:
    try:
        result = redeem_code(int(db_user["id"]), code)
        msg = result.get("message", "Redeem berhasil.")
        await update.effective_message.reply_text(f"✅ {msg}", reply_markup=habit_main_keyboard())
    except ValueError as e:
        reason = str(e)
        if reason == "invalid_code":
            text = "Kode tidak valid."
        elif reason == "expired_code":
            text = "Kode sudah expired."
        elif reason == "already_used":
            text = "Kode sudah dipakai."
        elif reason == "not_owner":
            text = "Kode ini bukan milikmu."
        else:
            text = "Kode tidak bisa diproses."
        await update.effective_message.reply_text(f"❌ {text}", reply_markup=habit_main_keyboard())


async def _finish_settings_input(update: Update, context: ContextTypes.DEFAULT_TYPE, db_user: Dict[str, Any], value: str) -> bool:
    st = _state(context)
    step = st.get("step")
    if st.get("screen") != "settings":
        return False

    raw = (value or "").strip()

    if step == "channel":
        set_config_value("notification_channel_id", raw)
        st["step"] = None
        await update.effective_message.reply_text("✅ Channel notifikasi disimpan.", reply_markup=habit_settings_keyboard())
        return True

    if step == "brief_time":
        hhmm = parse_hhmm(raw)
        if not hhmm:
            await update.effective_message.reply_text("Format waktu tidak valid. Pakai HH:MM.", reply_markup=habit_settings_keyboard())
            return True
        set_config_value("daily_brief_time", hhmm)
        st["step"] = None
        await update.effective_message.reply_text("✅ Jam briefing disimpan.", reply_markup=habit_settings_keyboard())
        return True

    if step == "alert_time":
        hhmm = parse_hhmm(raw)
        if not hhmm:
            await update.effective_message.reply_text("Format waktu tidak valid. Pakai HH:MM.", reply_markup=habit_settings_keyboard())
            return True
        set_config_value("night_alert_time", hhmm)
        st["step"] = None
        await update.effective_message.reply_text("✅ Jam alert disimpan.", reply_markup=habit_settings_keyboard())
        return True

    return False


async def handle_habit_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_user: Dict[str, Any],
    text: str,
) -> bool:
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
            await update.effective_message.reply_text("Dibatalkan.", reply_markup=habit_main_keyboard())
            return True

        if st.get("step") == "title":
            st["payload"]["title"] = raw
            st["step"] = "category"
            await update.effective_message.reply_text(
                _category_prompt_text(),
                reply_markup=habit_add_category_keyboard(),
            )
            return True

        if st.get("step") == "category":
            if raw == BTN_HABIT_CATEGORY_CUSTOM:
                st["step"] = "category_custom"
                await update.effective_message.reply_text("Tulis kategori custom-nya.", reply_markup=habit_add_category_keyboard())
                return True
            if raw == BTN_BACK:
                st["step"] = "title"
                await update.effective_message.reply_text("Tulis nama habit utamanya lagi.", reply_markup=habit_add_category_keyboard())
                return True

            if " " in raw:
                parts = raw.split(" ", 1)
                category = parts[1].strip()
            else:
                category = raw.strip()

            st["payload"]["category"] = category
            st["payload"]["emoji"] = _find_category_emoji(category)
            st["step"] = "difficulty"
            await update.effective_message.reply_text("Pilih difficulty.", reply_markup=habit_add_difficulty_keyboard())
            return True

        if st.get("step") == "category_custom":
            st["payload"]["category"] = raw
            st["payload"]["emoji"] = _find_category_emoji(raw)
            st["step"] = "difficulty"
            await update.effective_message.reply_text("Pilih difficulty.", reply_markup=habit_add_difficulty_keyboard())
            return True

        if st.get("step") == "difficulty":
            diff = _parse_diff_button(raw)
            if not diff:
                await update.effective_message.reply_text("Pilih difficulty dari tombol.", reply_markup=habit_add_difficulty_keyboard())
                return True
            diff_code, xp_value, diff_label = diff
            st["payload"]["difficulty_code"] = diff_code
            st["payload"]["xp_value"] = xp_value
            st["payload"]["difficulty_label"] = diff_label
            st["step"] = "confirm"
            await update.effective_message.reply_text(_render_add_confirm(st["payload"]), reply_markup=habit_confirm_keyboard())
            return True

        if st.get("step") == "confirm":
            if raw == BTN_HABIT_SAVE:
                await _finish_add_flow(update, context, db_user)
                return True
            if raw in {BTN_HABIT_CANCEL, BTN_BACK}:
                _reset_state(context)
                await update.effective_message.reply_text("Dibatalkan.", reply_markup=habit_main_keyboard())
                return True

    if st.get("screen") == "settings":
        if raw in {BTN_BACK, BTN_HABIT_CANCEL}:
            _reset_state(context)
            await update.effective_message.reply_text("Kembali.", reply_markup=habit_main_keyboard())
            return True

        if st.get("step") == "channel":
            return await _finish_settings_input(update, context, db_user, raw)

        if st.get("step") == "brief_time":
            return await _finish_settings_input(update, context, db_user, raw)

        if st.get("step") == "alert_time":
            return await _finish_settings_input(update, context, db_user, raw)

        if raw == BTN_HABIT_SET_CHANNEL:
            st["step"] = "channel"
            await update.effective_message.reply_text("Kirim Channel ID notifikasi (-100...).", reply_markup=habit_input_keyboard())
            return True

        if raw == BTN_HABIT_SET_BRIEF:
            st["step"] = "brief_time"
            await update.effective_message.reply_text("Kirim jam briefing dalam format HH:MM.", reply_markup=habit_input_keyboard())
            return True

        if raw == BTN_HABIT_SET_ALERT:
            st["step"] = "alert_time"
            await update.effective_message.reply_text("Kirim jam alert malam dalam format HH:MM.", reply_markup=habit_input_keyboard())
            return True

    if st.get("screen") == "cache":
        if raw in {BTN_BACK, BTN_HABIT_CANCEL}:
            _reset_state(context)
            await update.effective_message.reply_text("Dibatalkan.", reply_markup=habit_main_keyboard())
            return True
        if st.get("step") == "redeem":
            if raw.startswith("/redeem"):
                parts = raw.split(maxsplit=1)
                if len(parts) < 2:
                    await update.effective_message.reply_text("Pakai: /redeem <CODE>", reply_markup=habit_main_keyboard())
                    return True
                code = parts[1].strip()
                await _finish_redeem_flow(update, db_user, code)
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
        await update.effective_message.reply_text("Kembali ke menu utama.", reply_markup=habit_main_keyboard())
        return True

    if st.get("screen") in {"add", "settings", "cache"}:
        return True

    return False


async def _edit_or_reply(query, text: str, reply_markup=None):
    try:
        await query.edit_message_text(text, reply_markup=reply_markup)
    except Exception:
        await query.message.reply_text(text, reply_markup=reply_markup)


async def _render_daily_query(query, user_id: int):
    rows = ensure_daily_snapshot(user_id, today_local())
    text = _daily_text(user_id, today_local())
    await _edit_or_reply(query, text, habit_daily_inline_keyboard(rows))


async def _render_list_query(query, user_id: int):
    habits = list_habits(user_id)
    text = _habits_text(user_id)
    await _edit_or_reply(query, text, habit_list_inline_keyboard(habits))


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
        await _edit_or_reply(query, _dashboard_text(user_id), habit_main_keyboard())
        return True

    if action == "refresh_daily":
        await _render_daily_query(query, user_id)
        return True

    if action == "daily":
        await _render_daily_query(query, user_id)
        return True

    if action == "refresh_list":
        await _render_list_query(query, user_id)
        return True

    if action == "list":
        await _render_list_query(query, user_id)
        return True

    if action == "progress":
        await _edit_or_reply(query, _progress_text(user_id), habit_main_keyboard())
        return True

    if action == "inventory":
        await _edit_or_reply(query, _inventory_text(user_id), habit_main_keyboard())
        return True

    if action == "achievement":
        await _edit_or_reply(query, _achievement_text(user_id), habit_main_keyboard())
        return True

    if action == "evaluation":
        await _edit_or_reply(query, _evaluation_text(user_id), habit_main_keyboard())
        return True

    if action == "settings":
        await _edit_or_reply(query, _settings_text(), habit_settings_keyboard())
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
        rows = ensure_daily_snapshot(user_id, today_local())
        progression = get_or_create_progression(user_id)
        inventory = get_or_create_inventory(user_id)
        text = _daily_text(user_id, today_local())

        await _edit_or_reply(query, text, habit_daily_inline_keyboard(rows))

        xp_delta = int(result.get("xp_delta") or 0)
        if xp_delta > 0:
            await query.message.reply_text(
                f"⚡ MATRIX UPDATE IN PROGRESS: INJECTING +{xp_delta} XP TO NEURAL LINK.",
                reply_markup=habit_main_keyboard(),
            )

        for code in result.get("tier_codes", []) or []:
            await query.message.reply_text(
                f"🪐 CRITICAL CORE UPGRADE DETECTED!\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"Congratulations, Captain.\n"
                f"Code issued: {code.get('code')}\n"
                f"Expires: {code.get('expires_at')}\n",
                reply_markup=habit_main_keyboard(),
            )

        if result.get("reward_code"):
            code = result["reward_code"]
            await query.message.reply_text(
                f"🎟️ DATA CACHE GENERATED\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"{code.get('code')}\n"
                f"Source: {code.get('source_type')}\n"
                f"Expired in 4 hours.\n",
                reply_markup=habit_main_keyboard(),
            )
        return True

    if action == "delete" and len(data) >= 3:
        habit_id = int(data[2])
        habit = get_habit_by_id(habit_id)
        if not habit:
            await query.message.reply_text("Habit tidak ditemukan.", reply_markup=habit_main_keyboard())
            return True
        text = (
            "⚠️ DELETE HABIT\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"{habit.get('emoji', '🛰️')} {habit.get('title')}\n"
            f"Kategori: {habit.get('category')}\n"
            f"Difficulty: {difficulty_label(habit.get('difficulty_code'))}\n\n"
            "Hapus permanen?"
        )
        await _edit_or_reply(query, text, habit_delete_confirm_inline(habit_id))
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
        await _edit_or_reply(query, _dashboard_text(user_id), habit_main_keyboard())
        return True

    return True


async def handle_habit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db_user = _user(update)
    user_id = int(db_user["id"])
    await update.message.reply_text(_dashboard_text(user_id), reply_markup=habit_main_keyboard())


async def handle_redeem_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db_user = _user(update)
    user_id = int(db_user["id"])
    if not context.args:
        await update.message.reply_text("Pakai: /redeem <CODE>", reply_markup=habit_main_keyboard())
        return
    code = " ".join(context.args).strip()
    try:
        result = redeem_code(user_id, code)
        await update.message.reply_text(f"✅ {result.get('message')}", reply_markup=habit_main_keyboard())
    except ValueError as e:
        reason = str(e)
        msg = {
            "invalid_code": "Kode tidak valid.",
            "expired_code": "Kode sudah expired.",
            "already_used": "Kode sudah dipakai.",
            "not_owner": "Kode ini bukan milikmu.",
            "empty_code": "Kode kosong.",
        }.get(reason, "Kode tidak bisa diproses.")
        await update.message.reply_text(f"❌ {msg}", reply_markup=habit_main_keyboard())


async def handle_evaluasi_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db_user = _user(update)
    user_id = int(db_user["id"])
    await update.message.reply_text(_evaluation_text(user_id), reply_markup=habit_main_keyboard())


async def _send_channel_message(application: Application, text: str) -> None:
    channel_id = get_config_value("notification_channel_id", "").strip()
    if not channel_id:
        return
    try:
        await application.bot.send_message(chat_id=channel_id, text=text)
    except Exception:
        pass


async def _run_daily_brief(application: Application) -> None:
    db_user = get_or_create_user(OWNER_ID, None, None)
    user_id = int(db_user["id"])
    rows = ensure_daily_snapshot(user_id, today_local())
    if not rows:
        return
    last = get_config_value("last_brief_sent_date", "")
    today_str = today_local().isoformat()
    if last == today_str:
        return

    text = (
        "🛰️ NEXUS CORE: DAILY MISSION BRIEFING\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Captain, matrix initialization successful. Daily missions for today are online:\n\n"
    )
    for idx, row in enumerate(rows, 1):
        text += mission_line(idx, row) + "\n"
    text += "\n*Status: Awaiting execution. Zero tolerance for slacking today. Engage now.*"

    await _send_channel_message(application, text)
    set_config_value("last_brief_sent_date", today_str)
    log_event(user_id, "DAILY_BRIEF_SENT", "cron.brief", {"date": today_str, "count": len(rows)})


async def _run_night_alert(application: Application) -> None:
    db_user = get_or_create_user(OWNER_ID, None, None)
    user_id = int(db_user["id"])
    rows = ensure_daily_snapshot(user_id, today_local())
    if not rows:
        return

    last = get_config_value("last_alert_sent_date", "")
    today_str = today_local().isoformat()
    if last == today_str:
        return

    unfinished = [row for row in rows if not row.get("is_completed")]
    if not unfinished:
        set_config_value("last_alert_sent_date", today_str)
        return

    text = (
        "🚨 TACTICAL ALERT: CORE INTEGRITY AT RISK! 🚨\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"Warning! Synchronization failure detected. You have 3 Hours remaining before system purge.\n"
        f"Unfinished Missions: {len(unfinished)}\n\n"
    )
    for idx, row in enumerate(unfinished, 1):
        text += mission_line(idx, row) + "\n"
    text += "\n*Action Required: Complete the mission now.*"

    await _send_channel_message(application, text)
    set_config_value("last_alert_sent_date", today_str)
    log_event(user_id, "NIGHT_ALERT_SENT", "cron.alert", {"date": today_str, "unfinished": len(unfinished)})


async def _run_midnight_rollover(application: Application) -> None:
    db_user = get_or_create_user(OWNER_ID, None, None)
    user_id = int(db_user["id"])
    yesterday = today_local() - timedelta(days=1)
    last = get_config_value("last_midnight_processed_date", "")
    if last == yesterday.isoformat():
        return

    result = evaluate_previous_day(user_id, yesterday)
    set_config_value("last_midnight_processed_date", yesterday.isoformat())

    today_rows = ensure_daily_snapshot(user_id, today_local())
    if today_rows:
        log_event(user_id, "MIDNIGHT_SNAPSHOT_CREATED", "cron.midnight", {"date": today_local().isoformat(), "rows": len(today_rows)})

    if result.get("reward_code"):
        # Reward code drop is sent directly to the private chat / owner side
        await application.bot.send_message(
            chat_id=OWNER_ID,
            text=(
                "🎟️ DATA CACHE GENERATED\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"{result['reward_code'].get('code')}\n"
                f"Source: {result['reward_code'].get('source_type')}\n"
                f"Expired in 4 hours.\n"
            ),
        )

    if result.get("status") in {"SUCCESS", "SHIELD_CONSUMED", "STREAK_RESET"}:
        log_event(user_id, "MIDNIGHT_ROLLOVER_RESULT", "cron.midnight", result)


async def _scheduler_loop(application: Application) -> None:
    while True:
        try:
            now = now_local()
            brief_time = parse_hhmm(get_config_value("daily_brief_time", HABIT_DAILY_BRIEF_TIME)) or "07:00"
            alert_time = parse_hhmm(get_config_value("night_alert_time", HABIT_NIGHT_ALERT_TIME)) or "21:00"

            today = now.date()
            brief_dt = datetime.combine(today, datetime.strptime(brief_time, "%H:%M").time()).astimezone()
            alert_dt = datetime.combine(today, datetime.strptime(alert_time, "%H:%M").time()).astimezone()
            midnight_dt = datetime.combine(today + timedelta(days=1), time(0, 0)).astimezone()

            candidates = [(brief_dt, "brief"), (alert_dt, "alert"), (midnight_dt, "midnight")]
            next_dt, kind = min(candidates, key=lambda item: item[0])
            sleep_for = max(1.0, (next_dt - now).total_seconds())
            await asyncio.sleep(sleep_for)

            if kind == "brief":
                await _run_daily_brief(application)
            elif kind == "alert":
                await _run_night_alert(application)
            elif kind == "midnight":
                await _run_midnight_rollover(application)

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Habit Scheduler] {e}")
            await asyncio.sleep(30)


async def post_init(application: Application) -> None:
    application.bot_data["habit_scheduler_task"] = application.create_task(_scheduler_loop(application))


def register(application: Application) -> None:
    ensure_defaults()
    application.add_handler(CommandHandler("habit", handle_habit_command))
    application.add_handler(CommandHandler("redeem", handle_redeem_command))
    application.add_handler(CommandHandler("evaluasi", handle_evaluasi_command))
    application.add_handler(CallbackQueryHandler(handle_habit_callback, pattern=r"^habit:"))
