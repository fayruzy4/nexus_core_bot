from __future__ import annotations

import asyncio
from datetime import datetime, time, timedelta

from telegram.ext import Application

from config import OWNER_ID, HABIT_DAILY_BRIEF_TIME, HABIT_NIGHT_ALERT_TIME
from database.queries import get_or_create_user
from features.habit.habit_queries import (
    ensure_daily_snapshot,
    evaluate_previous_day,
    get_config_value,
    log_event,
    set_config_value,
)
from features.habit.render_habit import (
    render_daily_brief_text,
    render_night_alert_text,
    render_reward_code_text,
)
from features.habit.utils_habit import now_local, parse_hhmm, today_local

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
    today_str = today_local().isoformat()
    if get_config_value("last_brief_sent_date", "") == today_str:
        return
    await _send_channel_message(application, render_daily_brief_text(rows))
    set_config_value("last_brief_sent_date", today_str)
    log_event(user_id, "DAILY_BRIEF_SENT", "cron.brief", {"date": today_str, "count": len(rows)})


async def _run_night_alert(application: Application) -> None:
    db_user = get_or_create_user(OWNER_ID, None, None)
    user_id = int(db_user["id"])
    rows = ensure_daily_snapshot(user_id, today_local())
    if not rows:
        return
    today_str = today_local().isoformat()
    if get_config_value("last_alert_sent_date", "") == today_str:
        return

    unfinished = [row for row in rows if not row.get("is_completed")]
    if not unfinished:
        set_config_value("last_alert_sent_date", today_str)
        return

    await _send_channel_message(application, render_night_alert_text(unfinished))
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
        await application.bot.send_message(chat_id=OWNER_ID, text=render_reward_code_text(result["reward_code"]))

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
            else:
                await _run_midnight_rollover(application)

        except asyncio.CancelledError:
            break
        except Exception as exc:
            print(f"[Habit Scheduler] {exc}")
            await asyncio.sleep(30)


async def post_init(application: Application) -> None:
    if application.bot_data.get("habit_scheduler_task"):
        return
    application.bot_data["habit_scheduler_task"] = application.create_task(_scheduler_loop(application))
