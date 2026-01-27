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
    MessageHandler,
    ContextTypes,
    filters,
)

# ================= ENV =================
BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])
WEBHOOK_URL = os.environ["WEBHOOK_URL"]
PORT = int(os.environ.get("PORT", "10000"))

MY_CONTACT = "@iliyanadg"
VIP_SITE_URL = "https://tuosito.com/vip-login"

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

def save_vip_user(user, chat_id, vip_code):
    now = datetime.now()
    expiry = now + timedelta(days=30)

    sheet.append_row([
        f"https://t.me/{user.username}" if user.username else "",
        now.strftime("%Y-%m-%d"),
        expiry.strftime("%Y-%m-%d"),
        now.strftime("%H:%M"),
        vip_code,
        "ACTIVE",
        chat_id,
        user.username or "",
        "telegram",
        1
    ])

def vip_welcome_message(vip_code):
    return (
        "💎 **BENVENUTO NEL VIP ACCESS**\n\n"
        "Ora puoi scrivermi direttamente:\n"
        f"👉 {MY_CONTACT}\n\n"
        "⏳ **Durata accesso:** 30 giorni\n\n"
        "🌐 **AREA VIP**\n"
        f"Accedi qui: {VIP_SITE_URL}\n\n"
        "🔐 **IL TUO CODICE VIP PERSONALE**\n"
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
    ])

def admin_vip_actions(chat_id):
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

    elif data == "vip_paid":
        user = query.from_user
        chat_id = query.message.chat_id

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                "💎 RICHIESTA VIP\n\n"
                f"👤 {user.first_name}\n"
                f"🆔 Chat ID: {chat_id}\n\n"
                "Premi CONFERMA PAGAMENTO quando verificato."
            ),
            reply_markup=admin_vip_actions(chat_id)
        )

        await query.edit_message_text(
            "✅ Perfetto.\nSto verificando il pagamento 💎"
        )

    elif data.startswith("vip_confirm:"):
        if query.from_user.id != ADMIN_ID:
            return

        chat_id = int(data.split(":")[1])
        vip_code = generate_vip_code()

        user = query.message.reply_to_message.from_user

        await context.bot.send_message(
            chat_id=chat_id,
            text=vip_welcome_message(vip_code),
            parse_mode="Markdown"
        )

        save_vip_user(user, chat_id, vip_code)

        await query.message.reply_text(
            f"✅ VIP ATTIVATO\nCodice: {vip_code}"
        )

    elif data.startswith("vip_reject:"):
        chat_id = int(data.split(":")[1])
        await context.bot.send_message(
            chat_id=chat_id,
            text="⚠️ Non trovo il pagamento. Inviami la ricevuta PayPal."
        )

# ================= WEBHOOK =================
app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(buttons))

loop = asyncio.new_event_loop()

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/webhook":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers["Content-Length"])
        data = json.loads(self.rfile.read(length))

        async def process():
            update = Update.de_json(data, app.bot)
            await app.process_update(update)

        asyncio.run_coroutine_threadsafe(process(), loop)
        self.send_response(200)
        self.end_headers()

def run_server():
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

async def set_webhook():
    await app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")

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
