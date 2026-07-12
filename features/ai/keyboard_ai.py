from __future__ import annotations

from telegram import KeyboardButton, ReplyKeyboardMarkup

BTN_AI = "🤖 Ngobrol dengan AI"
BTN_AI_GROQ = "🟢 Groq"
BTN_AI_GEMINI = "🔵 Gemini"
BTN_AI_RESET = "🗑 Reset Mode"
BTN_AI_EXIT = "❌ Keluar AI"
BTN_AI_YES_RESET = "✅ Ya, Reset"
BTN_AI_NO_RESET = "❌ Batal"
BTN_BACK = "⬅️ Kembali"


def _kb(rows):
    return ReplyKeyboardMarkup(
        [[KeyboardButton(text=item) for item in row] for row in rows],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def ai_main_keyboard():
    return _kb(
        [
            [BTN_AI_GROQ, BTN_AI_GEMINI],
            [BTN_AI_RESET],
            [BTN_BACK],
        ]
    )


def ai_active_keyboard():
    return _kb(
        [
            [BTN_AI_GROQ, BTN_AI_GEMINI],
            [BTN_AI_RESET, BTN_AI_EXIT],
            [BTN_BACK],
        ]
    )


def ai_reset_confirm_keyboard():
    return _kb(
        [
            [BTN_AI_YES_RESET],
            [BTN_AI_NO_RESET, BTN_BACK],
        ]
    )
