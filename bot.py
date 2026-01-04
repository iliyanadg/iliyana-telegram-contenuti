import os
import json
import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

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
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))

# Render fornisce PORT
PORT = int(os.environ.get("PORT", "10000"))

# URL pubblico del servizio Render: lo mettiamo come env RENDER_EXTERNAL_URL o WEBHOOK_URL
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # es: https://tuo-servizio.onrender.com

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
        user = query.from_user
        chat_id = query.message.chat_id
        username = f"@{user.username}" if user.username else "(no username)"
        name = f"{user.first_name or ''} {user.last_name or ''}".strip()

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                "💎 RICHIESTA VIP (utente ha premuto HO PAGATO)\n"
                f"👤 Nome: {name}\n"
                f"🔗 Username: {username}\n"
                f"🆔 Chat ID: {chat_id}\n\n"
                "Se vedi il pagamento su PayPal, conferma con:\n"
                f"/vip_ok {chat_id}"
            ),
            reply_markup=admin_reply_menu(chat_id)
        )

        await query.edit_message_text(
            "✅ Perfetto.\n\nHo ricevuto la tua richiesta VIP.\n"
            "Appena la conferma del pagamento è completata, riceverai qui il mio contatto diretto 💎"
        )

    elif data.startswith("settarget:"):
        if query.from_user.id != ADMIN_ID:
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
    # Admin verso target (testo)
    if update.effective_user.id == ADMIN_ID and context.user_data.get("admin_target_chat"):
        target_chat = int(context.user_data["admin_target_chat"])
        await context.bot.send_message(chat_id=target_chat, text=update.message.text)
        await update.message.reply_text("✅ Inviato all’utente.")
        return

    # Richieste utente
    if context.user_data.get("awaiting_request"):
        text = update.message.text
        context.user_data["awaiting_request"] = False
        mode = context.user_data.get("request_mode", "new")

        user = update.effective_user
        chat_id = update.effective_chat.id
        username = f"@{user.username}" if user.username else "(no username)"
        name = f"{user.first_name or ''} {user.last_name or ''}".strip()

        header = "📩 NUOVA RICHIESTA CONTENUTO" if mode == "new" else "➕ DETTAGLI AGGIUNTIVI"
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"{header}\n"
                f"👤 Nome: {name}\n"
                f"🔗 Username: {username}\n"
                f"🆔 Chat ID: {chat_id}\n\n"
                f"📝 Testo:\n{text}\n\n"
                "Rispondi/invia media premendo i bottoni qui sotto."
            ),
            reply_markup=admin_reply_menu(chat_id)
        )

        await update.message.reply_text(
            "✅ Richiesta inviata.\nRiceverai qui le informazioni per procedere.",
            reply_markup=user_after_request_menu()
        )

async def admin_media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # inoltra media dall'admin al target
    if update.effective_user.id != ADMIN_ID:
        return
    target_chat = context.user_data.get("admin_target_chat")
    if not target_chat:
        return

    await context.bot.copy_message(
        chat_id=int(target_chat),
        from_chat_id=update.effective_chat.id,
        message_id=update.message.message_id
    )
    await update.message.reply_text("✅ Media inoltrato all’utente.")

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    context.user_data.pop("admin_target_chat", None)
    await update.message.reply_text("✅ Target annullato.")

async def vip_ok_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
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


# ---------------- WEBHOOK SERVER ----------------
app = Application.builder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("vip_ok", vip_ok_cmd))
app.add_handler(CommandHandler("cancel", cancel_cmd))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(
    (filters.PHOTO | filters.VIDEO | filters.VOICE | filters.Document.ALL) & ~filters.COMMAND,
    admin_media_handler
))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

# Event loop condiviso
loop = asyncio.new_event_loop()

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # health check per Render
        if self.path in ("/", "/healthz"):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if self.path != "/webhook":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        try:
            data = json.loads(body.decode("utf-8"))
        except Exception:
            self.send_response(400)
            self.end_headers()
            return

        # passa update a telegram bot
        async def process():
            update = Update.de_json(data, app.bot)
            await app.process_update(update)

        asyncio.run_coroutine_threadsafe(process(), loop)

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

def run_server():
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    server.serve_forever()

async def post_init(application: Application):
    # set webhook
    if not WEBHOOK_URL:
        raise RuntimeError("WEBHOOK_URL non impostato. Mettilo nelle env su Render.")
    await application.bot.set_webhook(f"{WEBHOOK_URL.rstrip('/')}/webhook")

def main():
    # avvia loop + app in background
    asyncio.set_event_loop(loop)

    async def startup():
        await app.initialize()
        await app.start()
        await post_init(app)

    loop.run_until_complete(startup())

    # avvia HTTP server in un thread
    Thread(target=run_server, daemon=True).start()

    # tieni vivo il loop
    loop.run_forever()

if __name__ == "__main__":
    main()

