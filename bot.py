import os
import json
import asyncio
import secrets
import string
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import gspread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ================= ENV =================
BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])
WEBHOOK_URL = os.environ["WEBHOOK_URL"].rstrip("/")  # importante
PORT = int(os.environ.get("PORT", "10000"))

MY_CONTACT = os.environ.get("MY_CONTACT", "@iliyanadg")
VIP_SITE_URL = os.environ.get("VIP_SITE_URL", "https://vip-access.pages.dev/")

PAYPAL_VIP_URL = "https://www.paypal.com/paypalme/iliyanadg/4"

# ================= GOOGLE SHEETS =================
gc = gspread.service_account_from_dict(
    json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
)
sheet = gc.open("VIP_ACCESS").worksheet("VIP_ACCESS")

# ================= UTIL =================
def generate_vip_code():
    chars = string.ascii_uppercase + string.digits
    return "VIP-" + "".join(secrets.choice(chars) for _ in range(6))

def save_vip_user(user_data: dict, chat_id: int, vip_code: str):
    now = datetime.now()
    expiry = now + timedelta(days=30)

    username = user_data.get("username") or ""
    tg_link = f"https://t.me/{username}" if username else ""

    sheet.append_row([
        tg_link,                          # UTENTE (link)
        now.strftime("%Y-%m-%d"),         # DATA_ABBONAMENTO
        expiry.strftime("%Y-%m-%d"),      # DATA_SCADENZA
        now.strftime("%H:%M"),            # ORARIO
        vip_code,                         # VIP_CODE
        "ACTIVE",                         # STATUS
        chat_id,                          # telegram_id
        username,                         # telegram_username
        "telegram",                       # source
        1                                 # renew_count
    ])

def vip_welcome_message(vip_code: str) -> str:
    return (
        "💎 *BENVENUTO NEL VIP ACCESS*\n\n"
        "Ora puoi scrivermi direttamente:\n"
        f"👉 {MY_CONTACT}\n\n"
        "⏳ *Durata accesso:* 30 giorni\n\n"
        "🌐 *AREA VIP*\n"
        f"Accedi qui: {VIP_SITE_URL}\n\n"
        "🔐 *IL TUO CODICE VIP PERSONALE*\n"
        f"`{vip_code}`\n\n"
        "Usa questo codice per fare login sul sito e vedere i contenuti riservati.\n"
        "⚠️ Il codice è personale e non va condiviso.\n\n"
        "Scrivimi quando vuoi 😽"
    )

# ================= UI =================
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("VIP ACCESS 💎", callback_data="vip")],
    ])

def vip_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 PAGA VIP", url=PAYPAL_VIP_URL)],
        [InlineKeyboardButton("✅ HO PAGATO", callback_data="vip_paid")],
        [InlineKeyboardButton("⬅️ Menu", callback_data="back")],
    ])

def admin_vip_actions(chat_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ CONFERMA PAGAMENTO", callback_data=f"vip_confirm:{chat_id}")],
        [InlineKeyboardButton("❌ NON TROVO PAGAMENTO", callback_data=f"vip_reject:{chat_id}")],
    ])

# ================= HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hey 😈\nVuoi entrare nel VIP Access?",
        reply_markup=main_menu()
    )

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "vip":
        await query.edit_message_text(
            "💎 VIP ACCESS\nPrezzo: 4€/mese\n\nProcedi dal link:",
            reply_markup=vip_menu()
        )

    elif data == "back":
        await query.edit_message_text(
            "Hey 😈\nVuoi entrare nel VIP Access?",
            reply_markup=main_menu()
        )

    elif data == "vip_paid":
        user = query.from_user
        chat_id = query.message.chat_id

        # ✅ Salviamo i dati dell'utente in pending (così l'admin li recupera dopo)
        pending = context.application.bot_data.setdefault("vip_pending", {})
        pending[chat_id] = {
            "id": user.id,
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "username": user.username or "",
        }

        display_name = (user.first_name or "") + (f" {user.last_name}" if user.last_name else "")
        uname = f"@{user.username}" if user.username else "(no username)"

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                "💎 RICHIESTA VIP — UTENTE HA PREMUTO “HO PAGATO”\n\n"
                f"👤 {display_name}\n"
                f"🔗 {uname}\n"
                f"🆔 Chat ID: {chat_id}\n\n"
                "Quando hai verificato PayPal, premi CONFERMA PAGAMENTO."
            ),
            reply_markup=admin_vip_actions(chat_id)
        )

        await query.edit_message_text("✅ Perfetto.\nSto verificando il pagamento 💎")

    elif data.startswith("vip_confirm:"):
        if query.from_user.id != ADMIN_ID:
            return

        target_chat = int(data.split(":")[1])

        pending = context.application.bot_data.get("vip_pending", {})
        user_data = pending.get(target_chat)

        if not user_data:
            await query.message.reply_text(
                "⚠️ Non trovo i dati dell’utente in pending.\n"
                "Fagli ripremere “HO PAGATO” così mi arriva di nuovo la richiesta."
            )
            return

        vip_code = generate_vip_code()

        # 1) invio messaggio VIP all'utente
        await context.bot.send_message(
            chat_id=target_chat,
            text=vip_welcome_message(vip_code),
            parse_mode="Markdown"
        )

        # 2) salvo su Google Sheet
        save_vip_user(user_data, target_chat, vip_code)

        # 3) conferma all'admin
        await query.message.reply_text(f"✅ VIP ATTIVATO\nCodice: {vip_code}\nChat: {target_chat}")

        # 4) rimuovo pending
        pending.pop(target_chat, None)

    elif data.startswith("vip_reject:"):
        if query.from_user.id != ADMIN_ID:
            return
        target_chat = int(data.split(":")[1])
        await context.bot.send_message(
            chat_id=target_chat,
            text="⚠️ Non trovo il pagamento.\nMandami la ricevuta PayPal (screenshot o PDF) qui in chat ✅"
        )
        await query.message.reply_text(f"❌ Ho chiesto la ricevuta a: {target_chat}")

# ================= WEBHOOK =================
app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(buttons))

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

        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)

        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            self.send_response(400)
            self.end_headers()
            return

        async def process():
            update = Update.de_json(payload, app.bot)
            await app.process_update(update)

        asyncio.run_coroutine_threadsafe(process(), loop)

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

def run_server():
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

async def set_webhook():
    await app.bot.set_webhook(f"{WEBHOOK_URL}/webhook", drop_pending_updates=True)

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
