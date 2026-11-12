"""
J.A.R.V.I.S. - Telegram bot (Python + Claude API)

Muhit o'zgaruvchilari (kodga YOZMANG, maxfiy saqlang):
    TELEGRAM_TOKEN      - @BotFather'dan olingan token
    ANTHROPIC_API_KEY   - console.anthropic.com'dan API kalit
    ALLOWED_USER_IDS    - (ixtiyoriy) ruxsat etilgan Telegram ID'lar, vergul bilan: 123,456
    CLAUDE_MODEL        - (ixtiyoriy) standart: claude-sonnet-5-5
"""

import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from anthropic import AsyncAnthropic
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO
)
log = logging.getLogger("jarvis")

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")
TZ = ZoneInfo("Asia/Tashkent")
MAX_TURNS = 20  # eslab qolinadigan oxirgi almashinuvlar soni
TG_LIMIT = 4096  # Telegram bitta xabar chegarasi

ALLOWED_IDS = {
    int(x) for x in os.getenv("ALLOWED_USER_IDS", "").split(",") if x.strip()
}

client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """Sen J.A.R.V.I.S.san - Tony Stark yaratgan sun'iy intellekt yordamchisan.

Uslubing:
- Foydalanuvchiga "Janob" deb murojaat qil.
- Xushmuomala, aqlli, ozgina quruq ingliz hazili (dry wit) bilan gapir.
- Qisqa va aniq javob ber, keraksiz uzun gap yozma.
- Foydalanuvchi qaysi tilda yozsa, shu tilda javob ber (asosan o'zbek tilida).
- Bilmagan narsangni to'qima: "Ma'lumotim yetarli emas, Janob" de.
- Hozirgi vaqt: {now}

Imkoniyating chegarasi: sen faqat matnli suhbat qilasan. Kostyum yoki qurilmalarni
boshqara olmaysan - bunday so'ralsa, buni halol ayt va qanday yordam bera olishingni taklif qil."""


def authorized(update: Update) -> bool:
    if not ALLOWED_IDS:
        return True
    user = update.effective_user
    return user is not None and user.id in ALLOWED_IDS


def split_text(text: str, limit: int = TG_LIMIT) -> list[str]:
    """Uzun javobni Telegram chegarasiga mos bo'laklarga bo'ladi."""
    parts = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut <= 0:
            cut = limit
        parts.append(text[:cut])
        text = text[cut:].lstrip("\n")
    if text:
        parts.append(text)
    return parts


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not authorized(update):
        return
    await update.message.reply_text(
        "J.A.R.V.I.S. tizimi ishga tushdi. Xizmatingizdaman, Janob.\n\n"
        "/reset - suhbat xotirasini tozalash\n"
        "/vaqt - hozirgi vaqt"
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not authorized(update):
        return
    context.user_data["history"] = []
    await update.message.reply_text("Xotira tozalandi, Janob. Yangi sahifa.")


async def vaqt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not authorized(update):
        return
    now = datetime.now(TZ).strftime("%d.%m.%Y, %H:%M")
    await update.message.reply_text(f"Hozir {now} (Toshkent), Janob.")


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not authorized(update):
        return
    if update.message is None or not update.message.text:
        return

    history: list[dict] = context.user_data.setdefault("history", [])
    history.append({"role": "user", "content": update.message.text})

    # Xotirani cheklash; ro'yxat doim "user" bilan boshlanishi shart
    del history[:-MAX_TURNS * 2]
    while history and history[0]["role"] != "user":
        history.pop(0)

    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)

    try:
        response = await client.messages.create(
            model=MODEL,
            max_tokens=1000,
            system=SYSTEM_PROMPT.format(
                now=datetime.now(TZ).strftime("%d.%m.%Y, %H:%M")
            ),
            messages=history,
        )
        reply = "".join(b.text for b in response.content if b.type == "text").strip()
        if not reply:
            reply = "Javob shakllantirilmadi, Janob. Qayta urinib ko'ring."
    except Exception:
        log.exception("Claude API xatosi")
        history.pop()  # muvaffaqiyatsiz so'rovni xotiradan olib tashlaymiz
        await update.message.reply_text(
            "Tizimda nosozlik, Janob. Birozdan so'ng qayta urinib ko'ring."
        )
        return

    history.append({"role": "assistant", "content": reply})
    for part in split_text(reply):
        await update.message.reply_text(part)


def main() -> None:
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("vaqt", vaqt))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    log.info("J.A.R.V.I.S. ishga tushdi")
    app.run_polling()


if __name__ == "__main__":
    main()
