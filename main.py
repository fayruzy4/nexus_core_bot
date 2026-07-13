import asyncio
from telegram.ext import Application
from config import BOT_TOKEN
from features.keuangan.catat_keuangan import register
from features.habit.habit import post_init as habit_post_init

def main():
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN belum diisi.")

    app = Application.builder().token(BOT_TOKEN).post_init(habit_post_init).build()

    from telegram.ext import MessageHandler, filters, ApplicationHandlerStop
    from config import OWNER_ID

    async def block_non_owner(update, context):
        if update.effective_user and update.effective_user.id != OWNER_ID:
            raise ApplicationHandlerStop()

    app.add_handler(
        MessageHandler(filters.ALL, block_non_owner),
        group=-1
    )

    register(app)
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
