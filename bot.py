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

# ---------------- ENV ----------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
MY_CONTACT = os.environ.get("MY_CONTACT", "@iliyanadg")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # es: https://iliyana-telegram-contenuti-1.onrender.com
PORT = int(os.environ.get("PORT", "10000"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN mancante nelle env.")
if ADMIN_ID == 0:
    raise RuntimeError("ADMIN_ID mancante o 0 nelle env.")
if not WEBHOOK_URL:
    raise RuntimeError("WEBHOOK_URL mancante nelle env.")

PAYPAL_VIP_URL = "https://www.paypal.com/paypalme/iliyanadg/3"

PRICING_TEXT = (
    "💰 Prezzi\n"
    "• Foto singola: 5€\n"
    "• Set 5 foto: 15€\n"
    "• Video breve (1–2 min): 20€\n"
    "• Video lungo / bundle: da 30€\n\n"
    "📌 Scrivi cosa desideri (o manda direttamente foto/video/audio come riferimento)."
)

# ---------------- UI ----------------
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

def admin_actions_menu(chat_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 Imposta target", callback_data=f"settarget:{chat_id}")],
        [InlineKeyboardButton("❌ Annulla target", callback_data="unsettarget")],
    ])

# ---------------- HELPERS ----------------
def format_user_line(user) -> str:
    # Niente parentesi antiestetiche: se non c'è username, non lo scriviamo.
    name = " ".join([x for x in [user.first_name, user.last_name] if x]).strip()
    uname = f"@{user.username}" if user.username else ""
    if uname:
        return f"👤 {name}\n🔗 {uname}"
    return f"👤 {name}"

# ---------------- BOT HANDLERS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Nota: per Telegram, l’utente deve premere Start almeno una volta per ricevere messaggi.
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
            "2) Poi premi HO PAGATO\n"
            "3) Ti invio il contatto diretto dopo conferma ✅",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("💳 PAGA VIP", url=PAYPAL_VIP_URL)],
                    [InlineKeyboardButton("✅ HO PAGATO", callback_data="vip_paid")],
                    [InlineKeyboardButton("⬅️ Menu", callback_data="back")],
                ]
            ),
        )

    elif data == "vip_paid":
        user = query.from_user
        chat_id = query.message.chat_id

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                "💎 RICHIESTA VIP (ha premuto HO PAGATO)\n"
                f"{format_user_line(user)}\n"
                f"🆔 Chat ID: {chat_id}\n\n"
                "Se vedi il pagamento su PayPal, conferma con:\n"
                f"/vip_ok {chat_id}"
            ),
            reply_markup=admin_actions_menu(chat_id)
        )

        await query.edit_message_text(
            "✅ Perfetto.\n\nHo ricevuto la tua richiesta VIP.\n"
            "Appena confermo il pagamento, riceverai qui il contatto diretto 💎"
        )

    elif data.startswith("settarget:"):
        if query.from_user.id != ADMIN_ID:
            return
        target_chat = int(data.split(":", 1)[1])
        context.user_data["admin_target_chat"] = target_chat
        await query.message.reply_text(
            f"🎯 Target impostato: {target_chat}\n"
            "Ora manda QUI un messaggio o una foto/video/audio e lo inoltro all’utente.\n"
            "Per annullare: /cancel"
        )

    elif data == "unsettarget":
        if query.from_user.id != ADMIN_ID:
            return
        context.user_data.pop("admin_target_chat", None)
        await query.message.reply_text("✅ Target annullato.")

    elif data == "back":
        await query.edit_message_text("Scegli cosa vuoi fare:", reply_markup=main_menu())

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
    await update.message.reply_text("✅ VIP confermato: contatto inviato all’utente.")

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    context.user_data.pop("admin_target_chat", None)
    await update.message.reply_text("✅ Target annullato.")

async def admin_outgoing_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Se sei ADMIN e hai un target impostato:
    - inoltra testo o media all'utente target
    """
    if update.effective_user.id != ADMIN_ID:
        return
    target_chat = context.user_data.get("admin_target_chat")
    if not target_chat:
        await update.message.reply_text("⚠️ Nessun target impostato. Premi 🎯 Imposta target su una richiesta.")
        return

    # copia qualunque cosa (testo o media) verso il target
    await context.bot.copy_message(
        chat_id=int(target_chat),
        from_chat_id=update.effective_chat.id,
        message_id=update.message.message_id
    )
    await update.message.reply_text("✅ Inviato all’utente.")

async def user_request_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Testo dell'utente quando sta facendo una richiesta.
    """
    if not context.user_data.get("awaiting_request"):
        return

    context.user_data["awaiting_request"] = False
    mode = context.user_data.get("request_mode", "new")

    user = update.effective_user
    chat_id = update.effective_chat.id
    header = "📩 NUOVA RICHIESTA CONTENUTO" if mode == "new" else "➕ DETTAGLI AGGIUNTIVI"

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"{header}\n"
            f"{format_user_line(user)}\n"
            f"🆔 Chat ID: {chat_id}\n\n"
            f"📝 Testo:\n{update.message.text}"
        ),
        reply_markup=admin_actions_menu(chat_id)
    )

    await update.message.reply_text(
        "✅ Richiesta inviata.\nRiceverai qui le informazioni per procedere.",
        reply_markup=user_after_request_menu()
    )

async def user_request_media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Media dell'utente (foto/video/audio/documento) come richiesta.
    La inoltriamo all'admin con chat_id.
    """
    if not context.user_data.get("awaiting_request"):
        return

    context.user_data["awaiting_request"] = False
    mode = context.user_data.get("request_mode", "new")

    user = update.effective_user
    chat_id = update.effective_chat.id
    header = "📩 NUOVA RICHIESTA CONTENUTO (MEDIA)" if mode == "new" else "➕ DETTAGLI AGGIUNTIVI (MEDIA)"

    # prima un messaggio testuale all'admin
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"{header}\n"
            f"{format_user_line(user)}\n"
            f"🆔 Chat ID: {chat_id}\n\n"
            "📎 Ti ha mandato un media (copiato qui sotto)."
        ),
        reply_markup=admin_actions_menu(chat_id)
    )

    # poi copia il media all'admin
    await context.bot.copy_message(
        chat_id=ADMIN_ID,
        from_chat_id=update.effective_chat.id,
        message_id=update.message.message_id
    )

    await update.message.reply_text(
        "✅ Ricevuto.\nTi risponderò qui con i dettagli.",
        reply_markup=user_after_request_menu()
    )

# ---------------- WEBHOOK SERVER (Render) ----------------
app = Application.builder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("vip_ok", vip_ok_cmd))
app.add_handler(CommandHandler("cancel", cancel_cmd))
app.add_handler(CallbackQueryHandler(button_handler))

# Admin: qualunque messaggio/media mentre target impostato
app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, admin_outgoing_handler), group=0)

# User requests: testo e media SOLO quando awaiting_request=True
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, user_request_text_handler), group=1)
app.add_handler(MessageHandler((filters.PHOTO | filters.VIDEO | filters.VOICE | filters.Document.ALL) & ~filters.COMMAND, user_request_media_handler), group=1)

loop = asyncio.new_event_loop()

class Handler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        if self.path in ("/", "/healthz"):
            self.send_response(200)
            self.end_headers()
            return
        self.send_response(404)
        self.end_headers()

    def do_GET(self):
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

async def set_webhook():
    webhook_full = f"{WEBHOOK_URL.rstrip('/')}/webhook"
    await app.bot.set_webhook(webhook_full)

def main():
    asyncio.set_event_loop(loop)

    async def startup():
        await app.initialize()
        await app.start()
        await set_webhook()

    loop.run_until_complete(startup())
    Thread(target=run_server, daemon=True).start()
    loop.run_forever()

if __name__ == "__main__":
    main()
