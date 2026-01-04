import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = os.environ.get("BOT_TOKEN")

def main_menu():
    keyboard = [
        [InlineKeyboardButton("🟢 ACQUISTA CONTENUTI 🔓", callback_data="buy")],
        [InlineKeyboardButton("🟣 VIP ACCESS 💎", callback_data="vip")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Benvenuto 💬\n\nScegli cosa vuoi fare:",
        reply_markup=main_menu()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "buy":
        await query.edit_message_text(
            "🟢 ACQUISTA CONTENUTI\n\n"
            "Descrivi cosa desideri (foto, video, audio).\n"
            "✍️ Scrivi ora la tua richiesta."
        )
        context.user_data["awaiting_request"] = True

    elif query.data == "vip":
        await query.edit_message_text(
            "🟣 VIP ACCESS 💎\n\n"
            "Abbonamento mensile: €3\n\n"
            "Dopo il pagamento riceverai il mio contatto diretto.\n",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 PAGA VIP", url="https://www.paypal.com/paypalme/iliyanadg/3")],
                [InlineKeyboardButton("⬅️ Torna al menu", callback_data="back")]
            ])
        )

    elif query.data == "back":
        await query.edit_message_text(
            "Scegli cosa vuoi fare:",
            reply_markup=main_menu()
        )

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_request"):
        text = update.message.text
        context.user_data["awaiting_request"] = False

        admin_id = int(os.environ.get("ADMIN_ID"))
        await context.bot.send_message(
            chat_id=admin_id,
            text=f"📩 Nuova richiesta contenuto:\n\n{text}"
        )

        await update.message.reply_text(
            "✅ Richiesta inviata.\nRiceverai qui le informazioni per procedere."
        )

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.run_polling()

if __name__ == "__main__":
    main()
