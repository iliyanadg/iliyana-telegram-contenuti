import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
MY_CONTACT = os.environ.get("MY_CONTACT", "@iliyanadg")  # metti su Render MY_CONTACT=@iliyanadg

# --- MENU ---
def main_menu():
    keyboard = [
        [InlineKeyboardButton("🟢 ACQUISTA CONTENUTI 🔓", callback_data="buy")],
        [InlineKeyboardButton("🟣 VIP ACCESS 💎", callback_data="vip")],
    ]
    return InlineKeyboardMarkup(keyboard)


# --- START ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Benvenuto 💬\n\nScegli cosa vuoi fare:",
        reply_markup=main_menu(),
    )


# --- BUTTON HANDLER ---
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
            "1) Paga dal bottone qui sotto\n"
            "2) Poi premi **HO PAGATO**\n"
            "3) Riceverai il mio contatto diretto dopo conferma ✅\n",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("💳 PAGA VIP", url="https://www.paypal.com/paypalme/iliyanadg/3")],
                    [InlineKeyboardButton("✅ HO PAGATO", callback_data="vip_paid")],
                    [InlineKeyboardButton("⬅️ Torna al menu", callback_data="back")],
                ]
            ),
        )

    elif query.data == "vip_paid":
        # L'utente segnala di aver pagato: notifichiamo l'admin con chat_id + username
        admin_id = int(os.environ.get("ADMIN_ID"))
        user = query.from_user
        chat_id = query.message.chat_id
        username = f"@{user.username}" if user.username else "(no username)"
        name = f"{user.first_name or ''} {user.last_name or ''}".strip()

        await context.bot.send_message(
            chat_id=admin_id,
            text=(
                "💎 RICHIESTA VIP (utente ha cliccato 'HO PAGATO')\n"
                f"👤 Nome: {name}\n"
                f"🔗 Username: {username}\n"
                f"🆔 Chat ID: {chat_id}\n\n"
                "Se vedi il pagamento su PayPal, conferma con:\n"
                f"/vip_ok {chat_id}"
            ),
        )

        await query.edit_message_text(
            "✅ Perfetto.\n\n"
            "Ho ricevuto la tua richiesta di accesso VIP.\n"
            "Appena la conferma del pagamento è completata, riceverai qui il mio contatto diretto 💎"
        )

    elif query.data == "back":
        await query.edit_message_text("Scegli cosa vuoi fare:", reply_markup=main_menu())


# --- TEXT HANDLER (richiesta contenuti) ---
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_request"):
        text = update.message.text
        context.user_data["awaiting_request"] = False

        admin_id = int(os.environ.get("ADMIN_ID"))

        user = update.effective_user
        chat_id = update.effective_chat.id
        username = f"@{user.username}" if user.username else "(no username)"
        name = f"{user.first_name or ''} {user.last_name or ''}".strip()

        await context.bot.send_message(
            chat_id=admin_id,
            text=(
                "📩 NUOVA RICHIESTA CONTENUTO\n"
                f"👤 Nome: {name}\n"
                f"🔗 Username: {username}\n"
                f"🆔 Chat ID: {chat_id}\n\n"
                f"📝 Testo:\n{text}\n\n"
                "Per rispondere a questo utente usa:\n"
                f"/reply {chat_id} (scrivi qui il messaggio)"
            ),
        )

        await update.message.reply_text(
            "✅ Richiesta inviata.\nRiceverai qui le informazioni per procedere."
        )


# --- ADMIN: rispondi a un utente specifico ---
async def reply_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = int(os.environ.get("ADMIN_ID"))
    if update.effective_user.id != admin_id:
        return

    if len(context.args) < 2:
        await update.message.reply_text("Uso: /reply CHAT_ID messaggio")
        return

    target_chat = int(context.args[0])
    message = " ".join(context.args[1:])

    await context.bot.send_message(chat_id=target_chat, text=message)
    await update.message.reply_text("✅ Messaggio inviato all’utente.")


# --- ADMIN: conferma VIP e invia contatto ---
async def vip_ok_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = int(os.environ.get("ADMIN_ID"))
    if update.effective_user.id != admin_id:
        return

    if len(context.args) < 1:
        await update.message.reply_text("Uso: /vip_ok CHAT_ID")
        return

    target_chat = int(context.args[0])

    await context.bot.send_message(
        chat_id=target_chat,
        text=(
            "💎 Benvenuto nel VIP Access\n\n"
            "Da ora puoi scrivermi direttamente qui:\n"
            f"👉 {MY_CONTACT}\n\n"
            "Accesso valido 30 giorni."
        ),
    )

    await update.message.reply_text("✅ VIP confermato e contatto inviato.")


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reply", reply_cmd))
    app.add_handler(CommandHandler("vip_ok", vip_ok_cmd))

    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    app.run_polling()


if __name__ == "__main__":
    main()
