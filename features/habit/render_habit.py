from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from features.habit.utils_habit import (
    ACHIEVEMENT_STREAKS,
    build_boss_title,
    format_moneyless_int,
    habit_item_line,
    mission_line,
    progress_bar,
    achievement_line,
)


def render_dashboard_text(
    progression: Dict[str, Any],
    inventory: Dict[str, Any],
    habit_count: int,
    today_completed: int,
    today_total: int,
) -> str:
    bar = progress_bar(
        int(progression.get("current_xp_in_rank") or 0),
        int(progression.get("current_xp_needed") or 100),
        10,
    )
    streak = int(progression.get("current_streak") or 0)
    shield = int(inventory.get("shield_count") or 0)
    consistency = float(progression.get("consistency_rating") or 0)
    return (
        "━━━━━━━━━━━━━━━━━━\n"
        "🛰️ NEXUS HABIT MATRIX\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"Tier : {progression.get('current_tier_name')} {progression.get('current_rank_label')}\n"
        f"XP   : [{bar}] {int(progression.get('current_xp_in_rank') or 0)} / {int(progression.get('current_xp_needed') or 100)} XP\n"
        f"Streak Link : 🔥 {streak} Hari\n"
        f"Shield Charge : 🛡️ x{shield}\n"
        f"Total Habit Aktif : {habit_count}\n"
        f"Daily Mission : {today_completed} / {today_total}\n"
        f"Consistency : {consistency:.2f}% [{progression.get('consistency_class')}]\n"
    )


def render_habits_text(habits: List[Dict[str, Any]]) -> str:
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


def render_progress_text(progression: Dict[str, Any], inventory: Dict[str, Any]) -> str:
    bar = progress_bar(
        int(progression.get("current_xp_in_rank") or 0),
        int(progression.get("current_xp_needed") or 100),
        10,
    )
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


def render_inventory_text(inventory: Dict[str, Any]) -> str:
    return (
        "━━━━━━━━━━━━━━━━━━\n"
        "🎒 INVENTORY\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"Shield Charge : 🛡️ x{int(inventory.get('shield_count') or 0)}\n"
        f"Cap           : 2\n"
    )


def render_achievement_text(achievements: List[Dict[str, Any]]) -> str:
    unlocked = {a.get("achievement_key"): a for a in achievements}
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


def render_evaluation_text(
    progression: Dict[str, Any],
    habits: List[Dict[str, Any]],
    achievements: List[Dict[str, Any]],
    active_codes: List[Dict[str, Any]],
) -> str:
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


def render_settings_text(
    daily_brief_time: str,
    night_alert_time: str,
    channel_id: str,
) -> str:
    return (
        "━━━━━━━━━━━━━━━━━━\n"
        "⚙️ HABIT SETTINGS\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"Daily Briefing : {daily_brief_time}\n"
        f"Night Alert    : {night_alert_time}\n"
        f"Channel ID     : {channel_id or '-'}\n"
    )


def render_cache_text() -> str:
    return (
        "━━━━━━━━━━━━━━━━━━\n"
        "🎟️ DATA CACHE\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Gunakan kode redeem yang dikirim sistem dengan command:\n"
        "/redeem <CODE>\n\n"
        "Kode hanya berlaku 4 jam dan hanya untuk owner."
    )


def render_daily_text(
    target_date: date,
    progression: Dict[str, Any],
    inventory: Dict[str, Any],
    rows: List[Dict[str, Any]],
) -> str:
    completed = sum(1 for row in rows if row.get("is_completed"))
    total = len(rows)
    bar = progress_bar(
        int(progression.get("current_xp_in_rank") or 0),
        int(progression.get("current_xp_needed") or 100),
        10,
    )
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


def render_add_confirm_text(payload: Dict[str, Any]) -> str:
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


def render_delete_confirm_text(habit: Dict[str, Any]) -> str:
    return (
        "⚠️ DELETE HABIT\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"{habit.get('emoji', '🛰️')} {habit.get('title')}\n"
        f"Kategori: {habit.get('category')}\n"
        f"Difficulty: {habit.get('difficulty_code')}\n\n"
        "Hapus permanen?"
    )


def render_reward_code_text(code: Dict[str, Any]) -> str:
    return (
        "🎟️ DATA CACHE GENERATED\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"{code.get('code')}\n"
        f"Source: {code.get('source_type')}\n"
        "Expired in 4 hours.\n"
    )


def render_tier_up_text(code: Dict[str, Any]) -> str:
    return (
        "🪐 CRITICAL CORE UPGRADE DETECTED!\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Congratulations, Captain.\n"
        f"Code issued: {code.get('code')}\n"
        f"Expires: {code.get('expires_at')}\n"
    )


def render_daily_brief_text(rows: List[Dict[str, Any]]) -> str:
    text = (
        "🛰️ NEXUS CORE: DAILY MISSION BRIEFING\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Captain, matrix initialization successful. Daily missions for today are online:\n\n"
    )
    for idx, row in enumerate(rows, 1):
        text += mission_line(idx, row) + "\n"
    text += "\n*Status: Awaiting execution. Zero tolerance for slacking today. Engage now.*"
    return text


def render_night_alert_text(unfinished: List[Dict[str, Any]]) -> str:
    text = (
        "🚨 TACTICAL ALERT: CORE INTEGRITY AT RISK! 🚨\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Warning! Synchronization failure detected. You have 3 Hours remaining before system purge.\n"
        f"Unfinished Missions: {len(unfinished)}\n\n"
    )
    for idx, row in enumerate(unfinished, 1):
        text += mission_line(idx, row) + "\n"
    text += "\n*Action Required: Complete the mission now.*"
    return text


def render_boss_title_text(active_habit_count: int, target_date: date) -> str:
    return build_boss_title(active_habit_count) + f" | {target_date.isoformat()}"
