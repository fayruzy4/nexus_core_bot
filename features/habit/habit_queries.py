from __future__ import annotations

import secrets
import string
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from database.postgres import get_postgres
from features.habit.utils_habit import (
    ACHIEVEMENT_STREAKS,
    STREAK_CODE_MILESTONES,
    build_boss_title,
    category_emoji,
    classify_consistency,
    normalize_category,
    now_local,
    phase_xp_for_tier,
    rank_label,
    today_local,
    tier_name,
    xp_for_difficulty_code,
)

DEFAULT_CONFIGS: Dict[str, str] = {
    "module_started_at": "",
    "notification_channel_id": "",
    "daily_brief_time": "07:00",
    "night_alert_time": "21:00",
    "server_timezone": "SERVER_LOCAL",
    "shield_max": "2",
    "shield_expire_hours": "4",
    "redeem_expire_hours": "4",
    "last_midnight_processed_date": "",
    "last_brief_sent_date": "",
    "last_alert_sent_date": "",
}

_DEFAULTS_SEEDED = False


def _db():
    return get_postgres() ini 


def _now() -> datetime:
    return now_local()


def _today() -> date:
    return today_local()


def _iso(dt_value: datetime) -> str:
    return dt_value.astimezone().isoformat()


def _rows(resp) -> List[Dict[str, Any]]:
    data = getattr(resp, "data", None)
    if not data:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    return []


def _one(resp) -> Optional[Dict[str, Any]]:
    rows = _rows(resp)
    return rows[0] if rows else None


def _select_one(table: str, **filters) -> Optional[Dict[str, Any]]:
    db = _db()
    query = db.table(table).select("*")
    for key, value in filters.items():
        query = query.eq(key, value)
    return _one(query.limit(1).execute())


def _select_all(table: str, columns: str = "*", **filters) -> List[Dict[str, Any]]:
    db = _db()
    query = db.table(table).select(columns)
    for key, value in filters.items():
        query = query.eq(key, value)
    return _rows(query.execute())


def _insert(table: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return _one(_db().table(table).insert(payload).execute())


def _insert_many(table: str, payloads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not payloads:
        return []
    return _rows(_db().table(table).insert(payloads).execute())


def _update_one(table: str, key_field: str, key_value: Any, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return _one(_db().table(table).update(payload).eq(key_field, key_value).execute())


def _delete_one(table: str, key_field: str, key_value: Any) -> None:
    _db().table(table).delete().eq(key_field, key_value).execute()


def ensure_defaults() -> None:
    global _DEFAULTS_SEEDED
    if _DEFAULTS_SEEDED:
        return

    existing_keys = {str(row.get("config_key") or "") for row in _select_all("system_config", "config_key")}
    missing = [
        {"config_key": key, "config_value": value, "updated_at": _iso(_now())}
        for key, value in DEFAULT_CONFIGS.items()
        if key not in existing_keys
    ]
    if missing:
        _insert_many("system_config", missing)

    _DEFAULTS_SEEDED = True


def get_config_value(key: str, default: str = "") -> str:
    row = _select_one("system_config", config_key=key)
    if row is not None:
        return str(row.get("config_value") or default)
    if key in DEFAULT_CONFIGS:
        ensure_defaults()
        row = _select_one("system_config", config_key=key)
        if row is not None:
            return str(row.get("config_value") or default)
    return default


def set_config_value(key: str, value: str) -> Dict[str, Any]:
    ensure_defaults()
    row = _select_one("system_config", config_key=key)
    payload = {"config_value": str(value), "updated_at": _iso(_now())}
    if row:
        updated = _update_one("system_config", "config_key", key, payload)
        return updated or {**row, **payload}
    created = {"config_key": key, **payload}
    return _insert("system_config", created) or created


def get_or_create_progression(user_id: int) -> Dict[str, Any]:
    existing = _select_one("user_progression", user_id=user_id)
    if existing:
        return existing

    payload = {
        "user_id": user_id,
        "current_tier_index": 1,
        "current_tier_name": tier_name(1),
        "current_rank_step": 6,
        "current_rank_label": rank_label(6),
        "current_xp_in_rank": 0,
        "current_xp_needed": phase_xp_for_tier(1),
        "total_xp": 0,
        "current_streak": 0,
        "highest_streak": 0,
        "total_days_monitored": 0,
        "total_days_fully_completed": 0,
        "total_missions_cleared": 0,
        "consistency_rating": 0,
        "consistency_class": "CRITICAL",
        "module_started_at": None,
        "last_midnight_processed_date": None,
        "updated_at": _iso(_now()),
    }
    return _insert("user_progression", payload) or payload


def get_or_create_inventory(user_id: int) -> Dict[str, Any]:
    existing = _select_one("user_inventory", user_id=user_id)
    if existing:
        return existing

    payload = {"user_id": user_id, "shield_count": 0, "updated_at": _iso(_now())}
    return _insert("user_inventory", payload) or payload


def ensure_user_state(user_id: int) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    return get_or_create_progression(user_id), get_or_create_inventory(user_id)


def log_event(user_id: int, event_type: str, source: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    data = {
        "user_id": user_id,
        "event_type": event_type,
        "source": source,
        "event_date": _today().isoformat(),
        "payload": payload or {},
        "created_at": _iso(_now()),
    }
    return _insert("system_events", data) or data


def _habit_xp_from_code(difficulty_code: str) -> int:
    return xp_for_difficulty_code(difficulty_code)


def list_habits(user_id: int) -> List[Dict[str, Any]]:
    ensure_defaults()
    return _rows(
        _db()
        .table("habit_definitions")
        .select("*")
        .eq("user_id", user_id)
        .order("order_index", desc=False)
        .order("created_at", desc=False)
        .execute()
    )


def list_active_habits(user_id: int, habit_date: date) -> List[Dict[str, Any]]:
    ensure_defaults()
    return _rows(
        _db()
        .table("habit_definitions")
        .select("*")
        .eq("user_id", user_id)
        .lte("effective_from_date", habit_date.isoformat())
        .order("order_index", desc=False)
        .order("created_at", desc=False)
        .execute()
    )

def get_habit_by_id(habit_id: int) -> Optional[Dict[str, Any]]:
    return _select_one("habit_definitions", id=habit_id)


def _normalize_habit_title(title: str) -> str:
    return " ".join((title or "").strip().split())


def create_habit(user_id: int, title: str, category: str, difficulty_code: str) -> Dict[str, Any]:
    ensure_defaults()
    title = _normalize_habit_title(title)
    category = normalize_category(category)

    if not title:
        raise ValueError("habit_title_empty")
    if not category:
        raise ValueError("habit_category_empty")

    xp_value = _habit_xp_from_code(difficulty_code)
    if xp_value <= 0:
        raise ValueError("difficulty_invalid")

    if _select_one("habit_definitions", user_id=user_id, title=title):
        raise ValueError("habit_title_exists")

    _, _ = ensure_user_state(user_id)
    today_str = _today().isoformat()
    if not get_config_value("module_started_at", ""):
        set_config_value("module_started_at", today_str)
        current = get_or_create_progression(user_id)
        if not current.get("module_started_at"):
            _update_one(
                "user_progression",
                "user_id",
                user_id,
                {"module_started_at": today_str, "updated_at": _iso(_now())},
            )

    next_order = max([int(h.get("order_index") or 0) for h in list_habits(user_id)], default=0) + 1
    payload = {
        "user_id": user_id,
        "title": title,
        "category": category,
        "emoji": category_emoji(category),
        "difficulty_code": difficulty_code,
        "xp_value": xp_value,
        "order_index": next_order,
        "effective_from_date": (_today() + timedelta(days=1)).isoformat(),
        "created_at": _iso(_now()),
        "updated_at": _iso(_now()),
    }
    created = _insert("habit_definitions", payload)
    if not created:
        raise RuntimeError("habit_create_failed")
    log_event(user_id, "HABIT_CREATED", "habit.create", {"habit": created})
    return created


def delete_habit(user_id: int, habit_id: int) -> bool:
    habit = get_habit_by_id(habit_id)
    if not habit or int(habit.get("user_id") or 0) != int(user_id):
        return False
    log_event(user_id, "HABIT_DELETED", "habit.delete", {"habit": habit})
    _delete_one("habit_definitions", "id", habit_id)
    return True


def _is_sunday(day_value: date) -> bool:
    return day_value.weekday() == 6


def get_daily_rows(user_id: int, habit_date: date) -> List[Dict[str, Any]]:
    ensure_defaults()
    return _rows(
        _db()
        .table("daily_habit_status")
        .select("*")
        .eq("user_id", user_id)
        .eq("habit_date", habit_date.isoformat())
        .order("is_boss", desc=False)
        .order("order_index_snapshot", desc=False)
        .order("id", desc=False)
        .execute()
    )


def get_daily_row_by_id(row_id: int) -> Optional[Dict[str, Any]]:
    return _select_one("daily_habit_status", id=row_id)


def _snapshot_row_from_habit(user_id: int, habit: Dict[str, Any], habit_date: date, xp_override: Optional[int] = None) -> Dict[str, Any]:
    xp_value = int(habit.get("xp_value") or 0)
    if xp_override is not None:
        xp_value = int(xp_override)

    return {
        "user_id": user_id,
        "habit_id": habit.get("id"),
        "habit_date": habit_date.isoformat(),
        "habit_title_snapshot": habit.get("title"),
        "category_snapshot": habit.get("category"),
        "emoji_snapshot": habit.get("emoji") or category_emoji(habit.get("category") or ""),
        "difficulty_code_snapshot": habit.get("difficulty_code"),
        "xp_value_snapshot": xp_value,
        "order_index_snapshot": int(habit.get("order_index") or 0),
        "is_boss": False,
        "boss_title": None,
        "is_completed": False,
        "completed_at": None,
        "xp_awarded": False,
        "xp_awarded_at": None,
        "reward_code_issued": False,
        "reward_code_issued_at": None,
        "created_at": _iso(_now()),
        "updated_at": _iso(_now()),
    }


def _boss_snapshot(user_id: int, habit_date: date, active_count: int) -> Dict[str, Any]:
    boss_title = build_boss_title(active_count)
    return {
        "user_id": user_id,
        "habit_id": None,
        "habit_date": habit_date.isoformat(),
        "habit_title_snapshot": boss_title,
        "category_snapshot": "Boss",
        "emoji_snapshot": "⚔️",
        "difficulty_code_snapshot": "BOSS",
        "xp_value_snapshot": 0,
        "order_index_snapshot": 9999,
        "is_boss": True,
        "boss_title": boss_title,
        "is_completed": False,
        "completed_at": None,
        "xp_awarded": False,
        "xp_awarded_at": None,
        "reward_code_issued": False,
        "reward_code_issued_at": None,
        "created_at": _iso(_now()),
        "updated_at": _iso(_now()),
    }


def ensure_daily_snapshot(user_id: int, habit_date: Optional[date] = None) -> List[Dict[str, Any]]:
    ensure_defaults()
    habit_date = habit_date or _today()

    existing = get_daily_rows(user_id, habit_date)
    existing_ids = {row.get("habit_id") for row in existing if row.get("habit_id") is not None}
    has_boss = any(bool(row.get("is_boss")) for row in existing)

    habits = list_active_habits(user_id, habit_date)

    inserts: List[Dict[str, Any]] = []
    for habit in habits:
        habit_id = habit.get("id")
        if habit_id in existing_ids:
            continue
        inserts.append(_snapshot_row_from_habit(user_id, habit, habit_date, xp_override=0 if _is_sunday(habit_date) else None))

    if _is_sunday(habit_date) and not has_boss:
        inserts.append(_boss_snapshot(user_id, habit_date, len(habits)))

    inserted_rows: List[Dict[str, Any]] = []
    if inserts:
        inserted_rows = _insert_many("daily_habit_status", inserts)

    combined = existing + [row for row in inserted_rows if row not in existing]
    if not combined and inserts:
        combined = get_daily_rows(user_id, habit_date)

    combined.sort(
        key=lambda row: (
            bool(row.get("is_boss")),
            int(row.get("order_index_snapshot") or 0),
            int(row.get("id") or 0),
        )
    )
    return combined


def _complete_rank_progression(user_id: int, xp_add: int) -> Dict[str, Any]:
    progression = get_or_create_progression(user_id)
    tier = int(progression.get("current_tier_index") or 1)
    rank_step = int(progression.get("current_rank_step") or 6)
    rank_xp = int(progression.get("current_xp_in_rank") or 0)
    total_xp = int(progression.get("total_xp") or 0)

    total_xp += int(xp_add)
    rank_xp += int(xp_add)

    tier_up_codes: List[Dict[str, Any]] = []
    tier_up = False

    while tier <= 12:
        needed = phase_xp_for_tier(tier)
        if rank_xp < needed:
            break

        rank_xp -= needed
        if rank_step > 1:
            rank_step -= 1
        else:
            if tier == 12:
                rank_step = 1
                rank_xp = min(rank_xp, needed - 1)
                break
            previous_tier = tier
            tier += 1
            rank_step = 6
            tier_up = True
            tier_up_codes.append(
                create_reward_code(
                    user_id,
                    source_type="TIER_ASCENSION",
                    source_ref=f"tier:{previous_tier}->{tier}",
                )
            )

        if tier > 12:
            tier = 12
            rank_step = 1
            rank_xp = min(rank_xp, phase_xp_for_tier(12) - 1)
            break

    updated = _update_one(
        "user_progression",
        "user_id",
        user_id,
        {
            "current_tier_index": tier,
            "current_tier_name": tier_name(tier),
            "current_rank_step": rank_step,
            "current_rank_label": rank_label(rank_step),
            "current_xp_in_rank": rank_xp,
            "current_xp_needed": phase_xp_for_tier(tier),
            "total_xp": total_xp,
            "updated_at": _iso(_now()),
        },
    ) or progression

    return {"progression": updated, "tier_up_codes": tier_up_codes, "tier_up": tier_up}


def apply_xp(user_id: int, xp_add: int, source: str = "habit") -> Dict[str, Any]:
    if xp_add <= 0:
        return {"progression": get_or_create_progression(user_id), "tier_up_codes": []}

    result = _complete_rank_progression(user_id, xp_add)
    log_event(user_id, "XP_GRANTED", source, {"xp": xp_add, "result": result["progression"]})
    if result["tier_up_codes"]:
        log_event(user_id, "TIER_UP", source, {"codes": [c["code"] for c in result["tier_up_codes"]]})
    return result


def _update_inventory(user_id: int, shield_delta: int) -> Dict[str, Any]:
    inventory = get_or_create_inventory(user_id)
    shield_max = int(get_config_value("shield_max", "2") or 2)
    shield_count = int(inventory.get("shield_count") or 0)
    shield_count = max(0, min(shield_max, shield_count + shield_delta))
    updated = _update_one(
        "user_inventory",
        "user_id",
        user_id,
        {"shield_count": shield_count, "updated_at": _iso(_now())},
    ) or inventory
    updated["shield_count"] = shield_count
    return updated


def create_reward_code(user_id: int, source_type: str, source_ref: str) -> Dict[str, Any]:
    ensure_defaults()
    charset = string.ascii_uppercase + string.digits
    code = ""
    for _ in range(20):
        code_suffix = "".join(secrets.choice(charset) for _ in range(6))
        candidate = f"NEXUS-REWARD-{source_type[:3].upper()}-{code_suffix}"
        if not _select_one("reward_codes", code=candidate):
            code = candidate
            break
    if not code:
        code = f"NEXUS-REWARD-{source_type[:3].upper()}-{int(_now().timestamp())}"

    expires_in_hours = int(get_config_value("redeem_expire_hours", "4") or 4)
    payload = {
        "user_id": user_id,
        "code": code,
        "source_type": source_type,
        "source_ref": source_ref,
        "status": "ACTIVE",
        "issued_at": _iso(_now()),
        "expires_at": _iso(_now() + timedelta(hours=expires_in_hours)),
        "used_at": None,
        "used_by": None,
        "created_at": _iso(_now()),
    }
    return _insert("reward_codes", payload) or payload


def _draw_gacha_reward() -> str:
    roll = secrets.randbelow(100)
    if roll < 40:
        return "XP_200"
    if roll < 80:
        return "SHIELD_1"
    return "RESTORE"


def redeem_code(user_id: int, raw_code: str) -> Dict[str, Any]:
    ensure_defaults()
    code = " ".join((raw_code or "").strip().split())
    if not code:
        raise ValueError("empty_code")

    row = _select_one("reward_codes", code=code)
    if not row:
        raise ValueError("invalid_code")
    if int(row.get("user_id") or 0) != int(user_id):
        raise ValueError("not_owner")
    if row.get("status") != "ACTIVE":
        raise ValueError("already_used")

    expires_at = row.get("expires_at")
    if expires_at and datetime.fromisoformat(str(expires_at)) < _now():
        _update_one("reward_codes", "id", row["id"], {"status": "EXPIRED"})
        raise ValueError("expired_code")

    _update_one(
        "reward_codes",
        "id",
        row["id"],
        {
            "status": "USED",
            "used_at": _iso(_now()),
            "used_by": user_id,
        },
    )

    reward_kind = _draw_gacha_reward()
    reward_message = ""
    extra: Dict[str, Any] = {}

    if reward_kind == "XP_200":
        result = apply_xp(user_id, 200, source="redeem.common")
        reward_message = "⚪ Common Drop: Data Injection +200 XP"
        extra = {"xp": 200, "progression": result["progression"]}

    elif reward_kind == "SHIELD_1":
        inventory = get_or_create_inventory(user_id)
        shield_count = int(inventory.get("shield_count") or 0)
        if shield_count >= 2:
            result = apply_xp(user_id, 200, source="redeem.rare_overflow")
            reward_message = "🟢 Rare Drop overflow -> +200 XP"
            extra = {"xp": 200, "progression": result["progression"]}
        else:
            updated = _update_inventory(user_id, 1)
            reward_message = "🟢 Rare Drop: Shield Injection +1"
            extra = {"shield_count": updated["shield_count"]}

    else:
        progression = get_or_create_progression(user_id)
        streak = int(progression.get("current_streak") or 0)
        highest = int(progression.get("highest_streak") or 0)
        if streak == 0 and highest > 0:
            _update_one(
                "user_progression",
                "user_id",
                user_id,
                {"current_streak": highest, "updated_at": _iso(_now())},
            )
            reward_message = f"🟡 Legendary Drop: SYSTEM RESTORE -> streak restored to {highest}"
            extra = {"restored_streak": highest}
        else:
            inventory = get_or_create_inventory(user_id)
            shield_count = int(inventory.get("shield_count") or 0)
            if shield_count >= 2:
                result = apply_xp(user_id, 200, source="redeem.legendary_overflow")
                reward_message = "🟡 Legendary overflow -> +200 XP"
                extra = {"xp": 200, "progression": result["progression"]}
            else:
                updated = _update_inventory(user_id, 2)
                reward_message = "🟡 Legendary Drop: Shield Charges +2"
                extra = {"shield_count": updated["shield_count"]}

    log_event(user_id, "REWARD_CODE_REDEEMED", "reward.redeem", {"code": code, "reward_kind": reward_kind, "extra": extra})
    return {
        "code": code,
        "reward_kind": reward_kind,
        "message": reward_message,
        "extra": extra,
    }


def toggle_daily_row(user_id: int, row_id: int) -> Dict[str, Any]:
    row = get_daily_row_by_id(row_id)
    if not row or int(row.get("user_id") or 0) != int(user_id):
        return {
            "status": "NOT_FOUND",
            "row": row,
            "xp_delta": 0,
            "tier_codes": [],
            "reward_code": None,
        }

    now_iso = _iso(_now())
    new_completed = not bool(row.get("is_completed"))
    update_payload = {
        "is_completed": new_completed,
        "updated_at": now_iso,
    }

    xp_delta = 0
    tier_codes: List[Dict[str, Any]] = []

    if new_completed:
        update_payload["completed_at"] = now_iso
        if not bool(row.get("xp_awarded")):
            xp_delta = int(row.get("xp_value_snapshot") or 0) if not bool(row.get("is_boss")) else 0
            if xp_delta > 0:
                xp_result = apply_xp(user_id, xp_delta, source="habit.daily")
                tier_codes = xp_result.get("tier_up_codes", []) or []
            update_payload["xp_awarded"] = True
            update_payload["xp_awarded_at"] = now_iso
    else:
        update_payload["completed_at"] = None

    updated = _update_one("daily_habit_status", "id", row_id, update_payload) or row
    return {
        "status": "OK",
        "row": updated,
        "xp_delta": xp_delta,
        "tier_codes": tier_codes,
        "reward_code": None,
    }


def unlock_achievement(user_id: int, achievement_key: str, achievement_name: str, badge_icon: str) -> Dict[str, Any]:
    existing = _select_one("user_achievements", user_id=user_id, achievement_key=achievement_key)
    if existing:
        return existing
    payload = {
        "user_id": user_id,
        "achievement_key": achievement_key,
        "achievement_name": achievement_name,
        "badge_icon": badge_icon,
        "unlocked_at": _iso(_now()),
        "permanent": True,
        "meta": {},
    }
    inserted = _insert("user_achievements", payload) or payload
    log_event(user_id, "ACHIEVEMENT_UNLOCKED", "achievement.unlock", inserted)
    return inserted


def unlock_streak_achievements(user_id: int, streak: int) -> List[Dict[str, Any]]:
    unlocked: List[Dict[str, Any]] = []
    for milestone, (name, icon) in ACHIEVEMENT_STREAKS.items():
        if streak >= milestone:
            unlocked.append(unlock_achievement(user_id, f"STREAK_{milestone}", name, icon))
    return unlocked


def update_progress_consistency(user_id: int) -> Dict[str, Any]:
    progression = get_or_create_progression(user_id)
    started_at = progression.get("module_started_at")
    if started_at:
        started_date = date.fromisoformat(str(started_at))
        days_monitored = max(1, (_today() - started_date).days + 1)
    else:
        days_monitored = max(1, int(progression.get("total_days_monitored") or 0) or 1)

    days_completed = int(progression.get("total_days_fully_completed") or 0)
    consistency = round((days_completed / days_monitored) * 100, 2) if days_monitored else 0.0
    consistency_class = classify_consistency(consistency)

    changed = (
        int(progression.get("total_days_monitored") or 0) != days_monitored
        or float(progression.get("consistency_rating") or 0) != consistency
        or str(progression.get("consistency_class") or "") != consistency_class
    )

    if changed:
        updated = _update_one(
            "user_progression",
            "user_id",
            user_id,
            {
                "total_days_monitored": days_monitored,
                "consistency_rating": consistency,
                "consistency_class": consistency_class,
                "updated_at": _iso(_now()),
            },
        ) or progression
    else:
        updated = progression

    updated["total_days_monitored"] = days_monitored
    updated["consistency_rating"] = consistency
    updated["consistency_class"] = consistency_class
    return updated


def _midnight_summary_for_date(user_id: int, target_date: date) -> Dict[str, Any]:
    rows = get_daily_rows(user_id, target_date)
    regular_rows = [row for row in rows if not row.get("is_boss")]
    boss_rows = [row for row in rows if row.get("is_boss")]
    all_completed = bool(rows) and all(bool(row.get("is_completed")) for row in rows)
    return {
        "rows": rows,
        "regular_rows": regular_rows,
        "boss_rows": boss_rows,
        "all_completed": all_completed,
        "required_count": len(rows),
        "completed_count": sum(1 for row in rows if row.get("is_completed")),
    }


def evaluate_previous_day(user_id: int, target_date: date) -> Dict[str, Any]:
    ensure_defaults()
    summary = _midnight_summary_for_date(user_id, target_date)
    progression = get_or_create_progression(user_id)
    inventory = get_or_create_inventory(user_id)

    if summary["required_count"] == 0:
        return {"status": "NO_HABITS", "summary": summary, "progression": progression, "inventory": inventory}

    total_days_fully_completed = int(progression.get("total_days_fully_completed") or 0)
    total_missions_cleared = int(progression.get("total_missions_cleared") or 0)
    current_streak = int(progression.get("current_streak") or 0)
    highest_streak = int(progression.get("highest_streak") or 0)

    reward_code = None
    if summary["all_completed"]:
        current_streak += 1
        highest_streak = max(highest_streak, current_streak)
        total_days_fully_completed += 1
        total_missions_cleared += summary["completed_count"]
        unlock_streak_achievements(user_id, current_streak)
        if current_streak in STREAK_CODE_MILESTONES:
            reward_code = create_reward_code(user_id, "STREAK_MILESTONE", f"streak:{current_streak}")
        result = "SUCCESS"
        note = f"Streak +1 -> {current_streak}"
    else:
        shield_count = int(inventory.get("shield_count") or 0)
        if shield_count >= 1:
            shield_count -= 1
            _update_one("user_inventory", "user_id", user_id, {"shield_count": shield_count, "updated_at": _iso(_now())})
            result = "SHIELD_CONSUMED"
            note = "Shield consumed, streak frozen"
        else:
            current_streak = 0
            result = "STREAK_RESET"
            note = "Streak reset to 0"

    updated = _update_one(
        "user_progression",
        "user_id",
        user_id,
        {
            "current_streak": current_streak,
            "highest_streak": highest_streak,
            "total_days_fully_completed": total_days_fully_completed,
            "total_missions_cleared": total_missions_cleared,
            "last_midnight_processed_date": target_date.isoformat(),
            "updated_at": _iso(_now()),
        },
    ) or progression

    updated = update_progress_consistency(user_id)
    log_event(user_id, "MIDNIGHT_ROLLOVER", "cron.midnight", {"date": target_date.isoformat(), "result": result, "note": note})
    return {
        "status": result,
        "note": note,
        "summary": summary,
        "progression": updated,
        "inventory": get_or_create_inventory(user_id),
        "reward_code": reward_code,
    }


def get_daily_briefing_payload(user_id: int, target_date: Optional[date] = None) -> Dict[str, Any]:
    target_date = target_date or _today()
    rows = ensure_daily_snapshot(user_id, target_date)
    return {"date": target_date, "rows": rows, "count": len(rows)}


def get_final_alert_payload(user_id: int, target_date: Optional[date] = None) -> Dict[str, Any]:
    target_date = target_date or _today()
    rows = ensure_daily_snapshot(user_id, target_date)
    unfinished = [row for row in rows if not row.get("is_completed")]
    return {"date": target_date, "rows": rows, "unfinished": unfinished}


def get_dashboard_snapshot(user_id: int, target_date: Optional[date] = None) -> Dict[str, Any]:
    target_date = target_date or _today()
    progression = get_or_create_progression(user_id)
    inventory = get_or_create_inventory(user_id)
    habits = list_habits(user_id)
    daily_rows = ensure_daily_snapshot(user_id, target_date)
    return {
        "target_date": target_date,
        "progression": progression,
        "inventory": inventory,
        "habits": habits,
        "daily_rows": daily_rows,
        "completed_today": sum(1 for row in daily_rows if row.get("is_completed")),
        "total_today": len(daily_rows),
    }


def get_daily_view_snapshot(user_id: int, target_date: Optional[date] = None) -> Dict[str, Any]:
    target_date = target_date or _today()
    return {
        "target_date": target_date,
        "progression": get_or_create_progression(user_id),
        "inventory": get_or_create_inventory(user_id),
        "rows": ensure_daily_snapshot(user_id, target_date),
    }


def get_list_snapshot(user_id: int) -> Dict[str, Any]:
    return {"habits": list_habits(user_id)}


def get_progress_snapshot(user_id: int) -> Dict[str, Any]:
    progression = update_progress_consistency(user_id)
    return {"progression": progression, "inventory": get_or_create_inventory(user_id)}


def get_achievements(user_id: int) -> List[Dict[str, Any]]:
    return _select_all("user_achievements", "*", user_id=user_id)


def get_active_reward_codes(user_id: int) -> List[Dict[str, Any]]:
    return _rows(
        _db()
        .table("reward_codes")
        .select("*")
        .eq("user_id", user_id)
        .eq("status", "ACTIVE")
        .order("issued_at", desc=True)
        .execute()
    )


def get_recent_events(user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    return _rows(
        _db()
        .table("system_events")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )


def get_settings_snapshot() -> Dict[str, Any]:
    return {
        "daily_brief_time": get_config_value("daily_brief_time", "07:00"),
        "night_alert_time": get_config_value("night_alert_time", "21:00"),
        "notification_channel_id": get_config_value("notification_channel_id", ""),
    }


def get_evaluation_snapshot(user_id: int) -> Dict[str, Any]:
    progression = update_progress_consistency(user_id)
    return {
        "progression": progression,
        "inventory": get_or_create_inventory(user_id),
        "habits": list_habits(user_id),
        "achievements": get_achievements(user_id),
        "active_codes": get_active_reward_codes(user_id),
        "recent_events": get_recent_events(user_id, limit=20),
    }
