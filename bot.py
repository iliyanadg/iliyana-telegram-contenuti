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

# ✅ VIP: prezzo 4€
PAYPAL_VIP_URL = "https://www.paypal.com/paypalme/iliyanadg/4"

PRICING_TEXT = (
    "💰 Prezzi\n"
    "• Foto singola: 5€\n"
    "• Set 5 foto: 15€\n"
    "• Video breve (1–2 min): 20€\n"
    "• Video lungo / bundle: da 30€\n\n"
    "📌 Scrivi cosa desideri (o manda direttamente foto/video/audio come riferimento)."
)

VIP_TEXT = (
    "VIP ACCESS 💎\n\n"
    "Il VIP Access è uno spazio più intimo e riservato:\n\n"
    "✔️ contatto diretto con me tramite messaggi e audio\n"
    "✔️ contenuti a pagamento\n"
    "✔️ possibilità di richiedere contenuti personalizzati a pagamento\n"
    "✔️ accesso anche ai contenuti che pubblico su OnlyFans\n\n"
    "Prezzo: €4 / mese\n\n"
    "Dopo il pagamento riceverai il mio contatto diretto\n"
    "e potrai scrivermi privatamente.\n\n"
    "Procedi dal link qui sotto, inserendo la causale \"abbonamento\" 👇"
)

WELCOME_VIP_TEXT = (
    "💎 Benvenuto nel VIP Access\n\n"
    "Da ora puoi scrivermi direttamente qui:\n"
    f"👉 {MY_CONTACT}\n\n"
    "Accesso valido 30 giorni."
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
    # ✅ QUI: bottoni admin (target + conferma/rifiuta pagamento)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 Imposta target", callback_data=f"settarget:{chat_id}")],
        [InlineKeyboardButton("✅ CONFERMA PAGAMENTO", callback_data=f"vip_confirm:{chat_id}")],
        [InlineKeyboardButton("❌ RIFIUTA / NON TROVO PAGAMENTO", callback_data=f"vip_reject:{chat_id}")],
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
    welcome = (
        "╭──────────────╮\n"
        "   ✨  MENU PRIVATO  ✨\n"
        "╰──────────────╯\n\n"
        "Hey… sei arrivato nel posto giusto 😈\n"
        "Adesso scegli bene 😽\n\n"
        "🔒  Vuoi un contenuto?\n"
        "💎  Vuoi il VIP e parlare direttamente con me?\n\n"
        "👇 Scegli qui sotto"
    )

    await update.message.reply_text(
        welcome,
        reply_markup=main_menu()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # -------- USER FLOWS --------
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
            VIP_TEXT,
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
                "Controlla PayPal: se trovi il pagamento premi ✅ CONFERMA PAGAMENTO.\n"
                "Se non lo trovi premi ❌ RIFIUTA."
            ),
            reply_markup=admin_actions_menu(chat_id)
        )

        await query.edit_message_text(
            "✅ Perfetto.\n\nHo ricevuto la tua richiesta VIP.\n"
            "Appena confermo il pagamento, riceverai qui il contatto diretto 💎"
        )

    elif data == "back":
        await query.edit_message_text("Scegli cosa vuoi fare:", reply_markup=main_menu())

    # -------- ADMIN ACTIONS (INLINE) --------
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

    elif data.startswith("vip_confirm:"):
        if query.from_user.id != ADMIN_ID:
            return
        target_chat = int(data.split(":", 1)[1])

        await context.bot.send_message(
            chat_id=target_chat,
            text=WELCOME_VIP_TEXT
        )

        await query.message.reply_text(
            f"✅ Pagamento confermato. Ho inviato il benvenuto VIP a: {target_chat}"
        )

    elif data.startswith("vip_reject:"):
        if query.from_user.id != ADMIN_ID:
            return
        target_chat = int(data.split(":", 1)[1])

        await context.bot.send_message(
            chat_id=target_chat,
            text=(
                "⚠️ Non riesco a trovare il pagamento.\n\n"
                "Per favore ricontrolla di aver pagato correttamente su PayPal con causale \"abbonamento\".\n"
                "Se hai pagato, mandami uno screenshot della ricevuta qui in chat e lo verifico subito ✅"
            )
        )

        await query.message.reply_text(
            f"❌ Ho inviato la richiesta di verifica (pagamento non trovato) a: {target_chat}"
        )

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
app.add_handler(CommandHandler("cancel", cancel_cmd))
app.add_handler(CallbackQueryHandler(button_handler))

# ✅ IMPORTANTISSIMO:
# admin_outgoing SOLO se il messaggio arriva dall'ADMIN (così non blocca gli utenti)
app.add_handler(MessageHandler(filters.User(ADMIN_ID) & ~filters.COMMAND, admin_outgoing_handler), group=0)

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
