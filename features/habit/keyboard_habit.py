from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from config import (
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
    BTN_HABIT_CANCEL,
    BTN_HABIT_SAVE,
    BTN_HABIT_SET_CHANNEL,
    BTN_HABIT_SET_BRIEF,
    BTN_HABIT_SET_ALERT,
    BTN_HABIT_CATEGORY_CUSTOM,
    BTN_HABIT_DIFF_VERY_EASY,
    BTN_HABIT_DIFF_EASY,
    BTN_HABIT_DIFF_HARD,
    BTN_HABIT_DIFF_VERY_HARD,
)
from features.habit.utils_habit import CATEGORY_PRESETS


def _kb(rows):
    return ReplyKeyboardMarkup(
        [[KeyboardButton(text=item) for item in row] for row in rows],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def habit_main_keyboard():
    return _kb(
        [
            [BTN_HABIT_DAILY],
            [BTN_HABIT_ADD],
            [BTN_HABIT_LIST],
            [BTN_HABIT_PROGRESS],
            [BTN_HABIT_INVENTORY],
            [BTN_HABIT_CACHE],
            [BTN_HABIT_ACHIEVEMENT],
            [BTN_HABIT_EVALUATION],
            [BTN_HABIT_SETTINGS],
            [BTN_BACK],
        ]
    )


def habit_add_category_keyboard():
    rows = []
    row = []
    for name, emoji in CATEGORY_PRESETS:
        if name == "Other":
            continue
        row.append(f"{emoji} {name}".strip())
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([BTN_HABIT_CATEGORY_CUSTOM])
    rows.append([BTN_BACK])
    return _kb(rows)


def habit_add_difficulty_keyboard():
    return _kb(
        [
            [BTN_HABIT_DIFF_VERY_EASY, BTN_HABIT_DIFF_EASY],
            [BTN_HABIT_DIFF_HARD, BTN_HABIT_DIFF_VERY_HARD],
            [BTN_BACK],
        ]
    )


def habit_confirm_keyboard():
    return _kb(
        [
            [BTN_HABIT_SAVE],
            [BTN_HABIT_CANCEL, BTN_BACK],
        ]
    )


def habit_settings_keyboard():
    return _kb(
        [
            [BTN_HABIT_SET_CHANNEL],
            [BTN_HABIT_SET_BRIEF, BTN_HABIT_SET_ALERT],
            [BTN_BACK],
        ]
    )


def habit_input_keyboard():
    return _kb([[BTN_BACK], [BTN_HABIT_CANCEL]])


def habit_daily_inline_keyboard(rows):
    buttons = []
    for row in rows:
        title = row.get("boss_title") if row.get("is_boss") else row.get("habit_title_snapshot")
        mark = "☑" if row.get("is_completed") else "☐"
        prefix = "⚔️ " if row.get("is_boss") else ""
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{prefix}[{mark}] {title}",
                    callback_data=f"habit:toggle:{row['id']}",
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="habit:refresh_daily"),
            InlineKeyboardButton("⬅️ Back", callback_data="habit:dashboard"),
        ]
    )
    return InlineKeyboardMarkup(buttons)


def habit_list_inline_keyboard(rows):
    buttons = []
    for habit in rows:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"🗑 {habit.get('title')}",
                    callback_data=f"habit:delete:{habit['id']}",
                )
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="habit:refresh_list"),
            InlineKeyboardButton("⬅️ Back", callback_data="habit:dashboard"),
        ]
    )
    return InlineKeyboardMarkup(buttons)


def habit_delete_confirm_inline(habit_id: int):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Ya, Hapus", callback_data=f"habit:confirm_delete:{habit_id}"),
                InlineKeyboardButton("❌ Batal", callback_data="habit:cancel_delete"),
            ],
            [
                InlineKeyboardButton("⬅️ Back", callback_data="habit:list"),
                InlineKeyboardButton("🏠 Dashboard", callback_data="habit:dashboard"),
            ],
        ]
    )
