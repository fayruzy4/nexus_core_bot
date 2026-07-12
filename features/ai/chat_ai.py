from __future__ import annotations

from typing import Any, Dict, Optional

from telegram import Update
from telegram.ext import ContextTypes

from features.ai.conversation_manager import (
    activate_provider,
    append_assistant_message,
    append_system_message,
    append_user_message,
    deactivate_provider,
    get_history,
    reset_user_ai,
    session_is_active,
    current_provider,
)
from features.ai.keyboard_ai import (
    BTN_AI,
    BTN_AI_EXIT,
    BTN_AI_GEMINI,
    BTN_AI_GROQ,
    BTN_AI_NO_RESET,
    BTN_AI_RESET,
    BTN_AI_YES_RESET,
    ai_active_keyboard,
    ai_main_keyboard,
    ai_reset_confirm_keyboard,
)
from features.ai.memory_manager import build_context_messages
from features.ai.prompt_manager import get_system_prompt
from features.ai.provider_manager import ProviderManagerError, generate_reply
from features.ai.utils_ai import normalize_text, render_active_notice, render_ai_dashboard, render_reset_warning, is_button


def _state(context: ContextTypes.DEFAULT_TYPE) -> Dict[str, Any]:
    if "ai_state" not in context.user_data:
        context.user_data["ai_state"] = {
            "awaiting_reset_confirm": False,
        }
    return context.user_data["ai_state"]


async def _show_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    session = get_history(user_id, limit=40)[0]
    provider = session.get("active_provider")
    active = bool(session.get("is_active") and provider)
    text = render_ai_dashboard(provider, active)
    markup = ai_active_keyboard() if active else ai_main_keyboard()
    await update.message.reply_text(text, reply_markup=markup)


async def _enter_provider(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, provider: str) -> None:
    activate_provider(user_id, provider)
    await update.message.reply_text(
        render_active_notice(provider),
        reply_markup=ai_active_keyboard(),
    )


async def _exit_ai(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    deactivate_provider(user_id)
    _state(context)["awaiting_reset_confirm"] = False
    await update.message.reply_text(
        "Mode AI dimatikan.",
        reply_markup=ai_main_keyboard(),
    )


async def _reset_ai(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    reset_user_ai(user_id)
    _state(context)["awaiting_reset_confirm"] = False
    await update.message.reply_text(
        "Seluruh percakapan dan memory AI sudah dihapus.",
        reply_markup=ai_main_keyboard(),
    )


async def _continue_chat(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str) -> None:
    session, history, summary = get_history(user_id, limit=60)
    provider = session.get("active_provider")
    if not provider:
        await update.message.reply_text(
            "Pilih Groq atau Gemini dulu.",
            reply_markup=ai_main_keyboard(),
        )
        return

    append_user_message(user_id, text)

    system_prompt = get_system_prompt()
    payload = build_context_messages(
        system_prompt=system_prompt,
        summary_text=summary,
        messages=history + [{"role": "user", "content": text}],
    )

    try:
        reply = await generate_reply(provider=provider, messages=payload, system_prompt=system_prompt)
    except ProviderManagerError as e:
        await update.message.reply_text(str(e), reply_markup=ai_active_keyboard())
        return

    append_assistant_message(user_id, reply, provider)
    await update.message.reply_text(reply, reply_markup=ai_active_keyboard())


async def handle_ai_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_user: Dict[str, Any],
    text: str,
) -> bool:
    user_id = int(db_user["id"])
    text = normalize_text(text)

    if not text:
        return False

    st = _state(context)
    session_active = session_is_active(user_id)
    provider = current_provider(user_id)

    if text == BTN_AI:
        await _show_dashboard(update, context, user_id)
        return True

    if st.get("awaiting_reset_confirm"):
        if text == BTN_AI_YES_RESET:
            await _reset_ai(update, context, user_id)
            return True
        if text in {BTN_AI_NO_RESET, BTN_BACK}:
            st["awaiting_reset_confirm"] = False
            await update.message.reply_text(
                "Reset dibatalkan.",
                reply_markup=ai_active_keyboard() if session_active else ai_main_keyboard(),
            )
            return True

    if text == BTN_AI_RESET:
        st["awaiting_reset_confirm"] = True
        await update.message.reply_text(
            render_reset_warning(),
            reply_markup=ai_reset_confirm_keyboard(),
        )
        return True

    if text == BTN_AI_EXIT:
        await _exit_ai(update, context, user_id)
        return True

    if text == BTN_AI_GROQ:
        await _enter_provider(update, context, user_id, "groq")
        return True

    if text == BTN_AI_GEMINI:
        await _enter_provider(update, context, user_id, "gemini")
        return True

    if text == BTN_BACK and not session_active:
        return False

    if session_active and provider:
        await _continue_chat(update, context, user_id, text)
        return True

    return False
