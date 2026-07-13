from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

from config import (
    BTN_HABIT_DIFF_VERY_EASY,
    BTN_HABIT_DIFF_EASY,
    BTN_HABIT_DIFF_HARD,
    BTN_HABIT_DIFF_VERY_HARD,
)

TIER_NAMES = [
    "Voyager",
    "Sentinel",
    "Ranger",
    "Vanguard",
    "Commander",
    "Captain",
    "Specter",
    "Operative",
    "Director",
    "Overseer",
    "Archon",
    "NEXUS Apex",
]

RANK_LABELS = ["VI", "V", "IV", "III", "II", "I"]

DIFFICULTY_CHOICES: Dict[str, Dict[str, Any]] = {
    BTN_HABIT_DIFF_VERY_EASY: {"code": "VERY_EASY", "xp": 10, "label": "Sangat Mudah"},
    BTN_HABIT_DIFF_EASY: {"code": "EASY", "xp": 15, "label": "Mudah"},
    BTN_HABIT_DIFF_HARD: {"code": "HARD", "xp": 25, "label": "Sulit"},
    BTN_HABIT_DIFF_VERY_HARD: {"code": "VERY_HARD", "xp": 40, "label": "Sangat Sulit"},
}

DIFFICULTY_BY_CODE = {v["code"]: v for v in DIFFICULTY_CHOICES.values()}

CATEGORY_PRESETS: List[Tuple[str, str]] = [
    ("Health", "🏃"),
    ("Learning", "📚"),
    ("Coding", "💻"),
    ("Spiritual", "🕌"),
    ("Mindset", "🧠"),
    ("Life", "🛠️"),
    ("Work", "💼"),
    ("Other", "➕"),
]

CATEGORY_EMOJI_MAP = {name.lower(): emoji for name, emoji in CATEGORY_PRESETS}

ACHIEVEMENT_STREAKS: Dict[int, Tuple[str, str]] = {
    1: ("Spark Activated", "🔥"),
    3: ("Ignition Link", "🔥🔥"),
    7: ("Weekly Orbit", "⚡"),
    14: ("Atmospheric Entry", "🌀"),
    30: ("Hyperdrive Engaged", "🌌"),
    90: ("Deep Space Voyager", "☄️"),
    180: ("Supernova Core", "🌟"),
    365: ("Galactic Eternal", "👑"),
}

STREAK_CODE_MILESTONES = {30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330, 360}


def now_local() -> datetime:
    return datetime.now().astimezone()


def today_local() -> date:
    return now_local().date()


def parse_hhmm(value: str) -> Optional[str]:
    raw = (value or "").strip()
    if not raw:
        return None
    parts = raw.split(":")
    if len(parts) != 2:
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return None
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def xp_for_difficulty_code(code: str) -> int:
    return int(DIFFICULTY_BY_CODE.get(code, {}).get("xp", 0))


def difficulty_label(code: str) -> str:
    return str(DIFFICULTY_BY_CODE.get(code, {}).get("label", code))


def tier_name(index: int) -> str:
    idx = max(1, min(12, int(index))) - 1
    return TIER_NAMES[idx]


def rank_label(step: int) -> str:
    idx = max(1, min(6, int(step))) - 1
    return RANK_LABELS[idx]


def phase_xp_for_tier(tier_index: int) -> int:
    tier_index = max(1, min(12, int(tier_index)))
    if tier_index <= 3:
        return 100
    if tier_index <= 6:
        return 300
    if tier_index <= 9:
        return 600
    return 1200


def progress_bar(current: int, total: int, length: int = 10) -> str:
    total = max(1, int(total))
    current = max(0, min(int(current), total))
    filled = int((current / total) * length)
    filled = max(0, min(length, filled))
    return "█" * filled + "░" * (length - filled)


def classify_consistency(percent: float) -> str:
    if percent >= 90:
        return "ELITE"
    if percent >= 70:
        return "STABLE"
    return "CRITICAL"


def normalize_category(category: str) -> str:
    return " ".join((category or "").strip().split())


def category_emoji(category: str) -> str:
    key = normalize_category(category).lower()
    return CATEGORY_EMOJI_MAP.get(key, "🛰️")


def build_boss_title(active_habit_count: int) -> str:
    if active_habit_count <= 0:
        return "WEEKLY BOSS: Forge the Matrix"
    if active_habit_count == 1:
        return "WEEKLY BOSS: Complete Your Solo Mission"
    return f"WEEKLY BOSS: Clear {active_habit_count} Active Missions"


def format_moneyless_int(value: int) -> str:
    return f"{int(value):,}".replace(",", ".")


def mission_line(idx: int, row: Dict[str, Any]) -> str:
    mark = "☑" if row.get("is_completed") else "☐"
    boss = "⚔️ " if row.get("is_boss") else ""
    xp = int(row.get("xp_value_snapshot") or 0)
    title = row.get("boss_title") if row.get("is_boss") else row.get("habit_title_snapshot")
    category = row.get("category_snapshot") if not row.get("is_boss") else "Boss"
    return (
        f"{idx}. {boss}[{mark}] {title}\n"
        f"   • {category} | +{xp} XP"
    )


def habit_item_line(idx: int, habit: Dict[str, Any]) -> str:
    return (
        f"{idx}. {habit.get('emoji', '🛰️')} {habit.get('title')}\n"
        f"   • {habit.get('category')} | {difficulty_label(habit.get('difficulty_code'))} | +{habit.get('xp_value')} XP"
    )


def achievement_line(unlocked: bool, icon: str, name: str, streak: int) -> str:
    mark = "✅" if unlocked else "⬜"
    return f"{mark} {icon} {name} ({streak} Hari)"


def reward_code_label(code: Dict[str, Any]) -> str:
    status = code.get("status", "ACTIVE")
    expires_at = code.get("expires_at", "-")
    return f"{code.get('code')} | {status} | Exp: {expires_at}"


def achievement_payload_map() -> Dict[int, Tuple[str, str]]:
    return ACHIEVEMENT_STREAKS


def checkpoint_label(total: int, max_total: int) -> str:
    return f"{total} / {max_total}"


def evaluation_class_text(consistency_class: str) -> str:
    return f"[{consistency_class}]"


def format_dt(dt_value: Optional[datetime]) -> str:
    if not dt_value:
        return "-"
    return dt_value.astimezone().strftime("%Y-%m-%d %H:%M:%S")


def format_date_only(value: Optional[date]) -> str:
    if not value:
        return "-"
    return value.isoformat()
