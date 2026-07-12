import asyncio
from telegram.ext import Application
from config import BOT_TOKEN
from features.keuangan.catat_keuangan import register

def main():
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN belum diisi.")
    app = Application.builder().token(BOT_TOKEN).build()
    register(app)
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
