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
MY_CONTACT = os.environ.get("MY_CONTACT", "@iliyanadg")

# >>> EDITA QUI I PREZZI COME VUOI (TESTO MOSTRATO AGLI UTENTI)
PRICING_TEXT = (
    "💰 Prezzi (indicativi)\n"
    "• Foto singola: 5€\n"
    "• Set 5 foto: 15€\n"
    "• Video breve (1–2 min): 20€\n"
    "• Video lungo / bundle: da 30€\n\n"
    "Scrivi cosa desideri (foto, video, audio) e ti rispondo con il link per procedere."
)

def main_menu():
    keyboard = [
        [InlineKeyboardButton("ACQUISTA CONTENUTI 🔒", callback_data="buy")],
        [InlineKeyboardButton("VIP ACCESS 💎", callback_data="vip")],
    ]
    return InlineKeyboardMarkup(keyboard)

def user_after_request_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Aggiungi dettagli", callback_data="add_details")],
        [InlineKeyboardButton("🆕 Nuova richiesta", callback_data="buy")],
        [InlineKeyboardButton("⬅️ Menu", callback_data="back")],
    ])

def admin_reply_menu(chat_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✉️ Rispondi", callback_data=f"settarget:{chat_id}")],
        [InlineKeyboardButton("📎 Invia media", callback_data=f"settarget:{chat_id}")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Benvenuto 💬\n\nScegli cosa vuoi fare:",
        reply_markup=main_menu()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "buy":
        await query.edit_message_text(
            f"ACQUISTA CONTENUTI 🔒\n\n{PRICING_TEXT}\n\n✍️ Scrivi ora la tua richiesta."
        )
        context.user_data["awaiting_request"] = True
        context.user_data["request_mode"] = "new"

    elif data == "add_details":
        await query.edit_message_text(
            "➕ Aggiungi dettagli\n\nScrivi qui ulteriori dettagli (es. durata, preferenze, urgenza)."
        )
        context.user_data["awaiting_request"] = True
        context.user_data["request_mode"] = "details"

    elif data == "vip":
        await query.edit_message_text(
            "VIP ACCESS 💎\n\n"
            "Abbonamento mensile: €3\n\n"
            "1) Paga dal bottone qui sotto\n"
            "2) Poi premi **HO PAGATO**\n"
            "3) Riceverai il mio contatto diretto dopo conferma ✅",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("💳 PAGA VIP", url="https://www.paypal.com/paypalme/iliyanadg/3")],
                    [InlineKeyboardButton("✅ HO PAGATO", callback_data="vip_paid")],
                    [InlineKeyboardButton("⬅️ Menu", callback_data="back")],
                ]
            ),
        )

    elif data == "vip_paid":
        admin_id = int(os.environ.get("ADMIN_ID"))
        user = query.from_user
        chat_id = query.message.chat_id
        username = f"@{user.username}" if user.username else "(no username)"
        name = f"{user.first_name or ''} {user.last_name or ''}".strip()

        await context.bot.send_message(
            chat_id=admin_id,
            text=(
                "💎 RICHIESTA VIP (utente ha premuto HO PAGATO)\n"
                f"👤 Nome: {name}\n"
                f"🔗 Username: {username}\n"
                f"🆔 Chat ID: {chat_id}\n\n"
                "Se vedi il pagamento su PayPal, conferma con:\n"
                f"/vip_ok {chat_id}\n\n"
                "Oppure premi qui sotto per rispondere/inviare media:"
            ),
            reply_markup=admin_reply_menu(chat_id)
        )

        await query.edit_message_text(
            "✅ Perfetto.\n\nHo ricevuto la tua richiesta VIP.\n"
            "Appena la conferma del pagamento è completata, riceverai qui il mio contatto diretto 💎"
        )

    elif data.startswith("settarget:"):
        # Admin ha cliccato su “Rispondi/Invia media” nella notifica
        admin_id = int(os.environ.get("ADMIN_ID"))
        if query.from_user.id != admin_id:
            return

        target_chat = int(data.split(":", 1)[1])
        context.user_data["admin_target_chat"] = target_chat

        await query.message.reply_text(
            f"✅ Target impostato: {target_chat}\n"
            "Ora manda qui un messaggio o una foto/video e lo inoltro all’utente.\n"
            "Quando vuoi annullare: /cancel"
        )

    elif data == "back":
        await query.edit_message_text("Scegli cosa vuoi fare:", reply_markup=main_menu())

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Gestione invio messaggi da ADMIN verso un target (testo)
    admin_id = int(os.environ.get("ADMIN_ID"))
    if update.effective_user.id == admin_id and context.user_data.get("admin_target_chat"):
        target_chat = int(context.user_data["admin_target_chat"])
        await context.bot.send_message(chat_id=target_chat, text=update.message.text)
        await update.message.reply_text("✅ Inviato all’utente.")
        return

    # Richieste utente
    if context.user_data.get("awaiting_request"):
        text = update.message.text
        context.user_data["awaiting_request"] = False
        mode = context.user_data.get("request_mode", "new")

        admin_id = int(os.environ.get("ADMIN_ID"))

        user = update.effective_user
        chat_id = update.effective_chat.id
        username = f"@{user.username}" if user.username else "(no username)"
        name = f"{user.first_name or ''} {user.last_name or ''}".strip()

        header = "📩 NUOVA RICHIESTA CONTENUTO" if mode == "new" else "➕ DETTAGLI AGGIUNTIVI"
        await context.bot.send_message(
            chat_id=admin_id,
            text=(
                f"{header}\n"
                f"👤 Nome: {name}\n"
                f"🔗 Username: {username}\n"
                f"🆔 Chat ID: {chat_id}\n\n"
                f"📝 Testo:\n{text}\n\n"
                "Rispondi/invia media direttamente premendo i bottoni qui sotto."
            ),
            reply_markup=admin_reply_menu(chat_id)
        )

        await update.message.reply_text(
            "✅ Richiesta inviata.\nRiceverai qui le informazioni per procedere.",
            reply_markup=user_after_request_menu()
        )

async def admin_media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Se l'admin ha impostato un target, inoltra qualsiasi media (foto/video/voice/doc) al target."""
    admin_id = int(os.environ.get("ADMIN_ID"))
    if update.effective_user.id != admin_id:
        return

    target_chat = context.user_data.get("admin_target_chat")
    if not target_chat:
        return

    # Copia il messaggio (funziona con qualsiasi tipo di contenuto)
    await context.bot.copy_message(
        chat_id=int(target_chat),
        from_chat_id=update.effective_chat.id,
        message_id=update.message.message_id
    )
    await update.message.reply_text("✅ Media inoltrato all’utente.")

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = int(os.environ.get("ADMIN_ID"))
    if update.effective_user.id != admin_id:
        return
    context.user_data.pop("admin_target_chat", None)
    await update.message.reply_text("✅ Target annullato. Non inoltro più i tuoi messaggi.")

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
    app.add_handler(CommandHandler("vip_ok", vip_ok_cmd))
    app.add_handler(CommandHandler("cancel", cancel_cmd))

    app.add_handler(CallbackQueryHandler(button_handler))

    # Prima gestiamo media dell'admin (foto/video/audio/doc)
    app.add_handler(MessageHandler(
        (filters.PHOTO | filters.VIDEO | filters.VOICE | filters.Document.ALL) & ~filters.COMMAND,
        admin_media_handler
    ))

    # Poi testo normale (admin o utenti)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    app.run_polling()

if __name__ == "__main__":
    main()



if __name__ == "__main__":
    main()
