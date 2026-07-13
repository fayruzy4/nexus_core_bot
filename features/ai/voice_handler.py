from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from config import AI_MAX_VOICE_DURATION, BTN_BACK
from database.queries import get_or_create_user
from features.ai.chat_ai import handle_ai_message
from features.ai.conversation_manager import session_is_active
from features.ai.keyboard_ai import ai_active_keyboard, ai_main_keyboard
from features.ai.speech_provider import SpeechProviderError, transcribe_audio_bytes


def _extract_media(update: Update):
    message = update.message
    if not message:
        return None, None, None, None

    if message.voice:
        media = message.voice
        file_id = media.file_id
        duration = media.duration or 0
        filename = "voice.ogg"
        mime_type = media.mime_type or "audio/ogg"
        return file_id, duration, filename, mime_type

    if message.audio:
        media = message.audio
        file_id = media.file_id
        duration = media.duration or 0
        filename = media.file_name or "audio.mp3"
        mime_type = media.mime_type or "audio/mpeg"
        return file_id, duration, filename, mime_type

    return None, None, None, None


async def handle_ai_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    db_user = get_or_create_user(user.id, user.username, user.full_name)
    user_id = int(db_user["id"])

    if not session_is_active(user_id):
        await update.message.reply_text(
            "Masuk mode AI dulu.",
            reply_markup=ai_main_keyboard(),
        )
        return True

    file_id, duration, filename, mime_type = _extract_media(update)
    if not file_id:
        return False

    if duration and int(duration) > AI_MAX_VOICE_DURATION:
        await update.message.reply_text(
            f"Voice terlalu panjang. Maksimal {AI_MAX_VOICE_DURATION // 60} menit.",
            reply_markup=ai_active_keyboard(),
        )
        return True

    try:
        telegram_file = await context.bot.get_file(file_id)
        audio_bytes = await telegram_file.download_as_bytearray()
        transcript = await transcribe_audio_bytes(
            audio_bytes=bytes(audio_bytes),
            filename=filename,
            mime_type=mime_type,
        )
    except SpeechProviderError as e:
        await update.message.reply_text(
            f"Gagal membaca suara: {e}",
            reply_markup=ai_active_keyboard(),
        )
        return True
    except Exception as e:
        await update.message.reply_text(
            f"Gagal membaca suara: {e}",
            reply_markup=ai_active_keyboard(),
        )
        return True

    if not transcript.strip():
        await update.message.reply_text(
            "Suara belum terbaca.",
            reply_markup=ai_active_keyboard(),
        )
        return True

    await handle_ai_message(update, context, db_user, transcript, reply_voice=True)
    return True
