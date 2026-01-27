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
WEBHOOK_URL = os.environ["WEBHOOK_URL"].rstrip("/")
PORT = int(os.environ.get("PORT", "10000"))

MY_CONTACT = os.environ.get("MY_CONTACT", "@iliyanadg")
VIP_SITE_URL = os.environ.get("VIP_SITE_URL", "https://vip-access.pages.dev/")

PAYPAL_VIP_URL = os.environ.get("PAYPAL_VIP_URL", "https://www.paypal.com/paypalme/iliyanadg/4")

# ================= GOOGLE SHEETS =================
gc = gspread.service_account_from_dict(
    json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
)
sheet = gc.open("VIP_ACCESS").worksheet("VIP_ACCESS")

# ================= IN-MEMORY STORE (pending VIP requests) =================
# chiave: chat_id utente, valore: dict con info utente
PENDING_VIP = {}

# ================= UTIL =================
def generate_vip_code() -> str:
    chars = string.ascii_uppercase + string.digits
    return "VIP-" + "".join(secrets.choice(chars) for _ in range(6))

def save_vip_user(user_info: dict, chat_id: int, vip_code: str):
    now = datetime.now()
    expiry = now + timedelta(days=30)

    username = user_info.get("username") or ""
    tme = f"https://t.me/{username}" if username else ""

    sheet.append_row([
        tme,                             # UTENTE
        now.strftime("%Y-%m-%d"),        # DATA_ABBONAMENTO
        expiry.strftime("%Y-%m-%d"),     # DATA_SCADENZA
        now.strftime("%H:%M"),           # ORARIO
        vip_code,                        # VIP_CODE
        "ACTIVE",                        # STATUS
        str(chat_id),                    # telegram_id
        username,                        # telegram_username
        "telegram",                      # source
        1                                # renew_count
    ])

def vip_welcome_message(vip_code: str) -> str:
    return (
        "💎 *BENVENUTO NEL VIP ACCESS*\n\n"
        "Da ora puoi scrivermi direttamente qui:\n"
        f"👉 {MY_CONTACT}\n\n"
        "⏳ *Accesso valido 30 giorni*\n\n"
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

    # USER
    if data == "vip":
        await query.edit_message_text(
            "💎 *VIP ACCESS*\nPrezzo: 4€/mese\n\nProcedi dal link qui sotto 👇",
            reply_markup=vip_menu(),
            parse_mode="Markdown"
        )

    elif data == "back":
        await query.edit_message_text(
            "Hey 😈\nVuoi entrare nel VIP Access?",
            reply_markup=main_menu()
        )

    elif data == "vip_paid":
        user = query.from_user
        chat_id = query.message.chat_id

        # Salvo info utente in memoria (così l’admin può confermare dopo)
        PENDING_VIP[chat_id] = {
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "username": user.username or "",
        }

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                "💎 *RICHIESTA VIP*\n\n"
                f"👤 {user.first_name or ''} {user.last_name or ''}\n"
                f"🔗 @{user.username}\n" if user.username else ""
                f"🆔 Chat ID: {chat_id}\n\n"
                "Premi *CONFERMA PAGAMENTO* quando hai verificato PayPal."
            ),
            reply_markup=admin_vip_actions(chat_id),
            parse_mode="Markdown"
        )

        await query.edit_message_text(
            "✅ Perfetto.\nSto verificando il pagamento 💎"
        )

    # ADMIN
    elif data.startswith("vip_confirm:"):
        if query.from_user.id != ADMIN_ID:
            return

        target_chat_id = int(data.split(":", 1)[1])
        user_info = PENDING_VIP.get(target_chat_id, {"username": ""})

        vip_code = generate_vip_code()

        await context.bot.send_message(
            chat_id=target_chat_id,
            text=vip_welcome_message(vip_code),
            parse_mode="Markdown"
        )

        save_vip_user(user_info, target_chat_id, vip_code)

        await query.message.reply_text(
            f"✅ VIP ATTIVATO per {target_chat_id}\nCodice: {vip_code}"
        )

    elif data.startswith("vip_reject:"):
        if query.from_user.id != ADMIN_ID:
            return

        target_chat_id = int(data.split(":", 1)[1])
        await context.bot.send_message(
            chat_id=target_chat_id,
            text="⚠️ Non trovo il pagamento. Inviami la ricevuta PayPal (screenshot o PDF) ✅"
        )
        await query.message.reply_text(f"❌ Ho chiesto ricevuta a: {target_chat_id}")

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
