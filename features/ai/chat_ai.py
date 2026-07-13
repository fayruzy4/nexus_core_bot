from __future__ import annotations

from typing import Any, Dict

from telegram import Update
from telegram.ext import ContextTypes

from config import (
    BTN_BACK,
    BTN_AI,
    BTN_AI_EXIT,
    BTN_AI_GEMINI,
    BTN_AI_GROQ,
    BTN_AI_NO_RESET,
    BTN_AI_RESET,
    BTN_AI_YES_RESET,
)
from features.ai.conversation_manager import (
    activate_provider,
    append_assistant_message,
    append_user_message,
    current_provider,
    deactivate_provider,
    get_history,
    reset_runtime_state,
    reset_user_ai,
    session_is_active,
    store_summary,
)
from features.ai.keyboard_ai import ai_active_keyboard, ai_main_keyboard, ai_reset_confirm_keyboard
from features.ai.memory_manager import build_context_messages, should_summarize
from features.ai.prompt_manager import get_system_prompt
from features.ai.provider_manager import ProviderManagerError, generate_reply
from features.ai.tts_provider import cleanup_audio_file, synthesize_speech
from features.ai.utils_ai import (
    chunk_text,
    normalize_text,
    render_active_notice,
    render_ai_dashboard,
    render_reset_warning,
    summarize_old_messages,
)


def _state(context: ContextTypes.DEFAULT_TYPE) -> Dict[str, Any]:
    if "ai_state" not in context.user_data:
        context.user_data["ai_state"] = {
            "menu_open": False,
            "awaiting_reset_confirm": False,
        }
    return context.user_data["ai_state"]


async def _show_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    st = _state(context)
    st["menu_open"] = True
    session, _, _ = get_history(user_id, limit=20)
    provider = session.get("active_provider")
    active = bool(session.get("is_active") and provider)
    await update.message.reply_text(
        render_ai_dashboard(provider, active),
        reply_markup=ai_active_keyboard() if active else ai_main_keyboard(),
    )


async def _activate(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, provider: str) -> None:
    st = _state(context)
    st["menu_open"] = True
    st["awaiting_reset_confirm"] = False
    activate_provider(user_id, provider)
    await update.message.reply_text(
        render_active_notice(provider),
        reply_markup=ai_active_keyboard(),
    )


async def _exit_ai(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    st = _state(context)
    st["menu_open"] = False
    st["awaiting_reset_confirm"] = False
    deactivate_provider(user_id)
    await update.message.reply_text(
        "Mode AI dimatikan.",
        reply_markup=ai_main_keyboard(),
    )


async def _reset_ai(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    st = _state(context)
    st["menu_open"] = False
    st["awaiting_reset_confirm"] = False
    deactivate_provider(user_id)
    reset_runtime_state()
    reset_user_ai(user_id)
    await update.message.reply_text(
        "Seluruh percakapan, memory, session, dan state AI sudah dihapus.",
        reply_markup=ai_main_keyboard(),
    )


async def _send_voice_reply(update: Update, text: str) -> None:
    audio_path = None
    try:
        audio_path = await synthesize_speech(text)
        with audio_path.open("rb") as audio:
            await update.message.reply_audio(
                audio=audio,
                performer="Nexus",
                title="Nexus",
            )
    except Exception:
        pass
    finally:
        cleanup_audio_file(audio_path)


async def _send_text_reply(update: Update, text: str) -> None:
    for part in chunk_text(text):
        await update.message.reply_text(part, reply_markup=ai_active_keyboard())


async def _chat(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str, reply_voice: bool = False) -> None:
    session, history, summary = get_history(user_id, limit=80)
    provider = session.get("active_provider")
    if not provider:
        await update.message.reply_text(
            "Pilih Groq atau Gemini dulu.",
            reply_markup=ai_main_keyboard(),
        )
        return

    append_user_message(user_id, text)
    session, history, summary = get_history(user_id, limit=80)

    system_prompt = get_system_prompt()
    history_no_system = [msg for msg in history if msg.get("role") != "system"]
    payload = build_context_messages(
        system_prompt=system_prompt,
        summary_text=summary,
        messages=history_no_system,
    )

    try:
        reply = await generate_reply(
            provider=provider,
            messages=payload,
            system_prompt=system_prompt,
            temperature=0.7,
            max_output_tokens=1024,
        )
    except ProviderManagerError as e:
        await update.message.reply_text(str(e), reply_markup=ai_active_keyboard())
        return

    append_assistant_message(user_id, reply, provider)

    if should_summarize(history_no_system):
        old_messages = history_no_system[:-12] if len(history_no_system) > 12 else []
        compact = summarize_old_messages(old_messages, max_turns=min(len(old_messages), 8))
        if compact:
            store_summary(user_id, compact)

    await _send_text_reply(update, reply)

    if reply_voice:
        await _send_voice_reply(update, reply)


async def handle_ai_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_user: Dict[str, Any],
    text: str,
    reply_voice: bool = False,
) -> bool:
    user_id = int(db_user["id"])
    text = normalize_text(text)
    if not text:
        return False

    st = _state(context)
    active = session_is_active(user_id)
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
                reply_markup=ai_active_keyboard() if active else ai_main_keyboard(),
            )
            return True
        await update.message.reply_text(
            render_reset_warning(),
            reply_markup=ai_reset_confirm_keyboard(),
        )
        return True

    if text == BTN_AI_RESET:
        st["menu_open"] = True
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
        await _activate(update, context, user_id, "groq")
        return True

    if text == BTN_AI_GEMINI:
        await _activate(update, context, user_id, "gemini")
        return True

    if text == BTN_BACK:
        if active or st.get("menu_open"):
            await _show_dashboard(update, context, user_id)
            return True
        return False

    if active and provider:
        await _chat(update, context, user_id, text, reply_voice=reply_voice)
        return True

    if st.get("menu_open"):
        await update.message.reply_text(
            "Pilih Groq atau Gemini dulu.",
            reply_markup=ai_main_keyboard(),
        )
        return True

    return False


async def handle_ai_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_user: Dict[str, Any],
    text: str,
) -> bool:
    return await handle_ai_message(update, context, db_user, text, reply_voice=False)
