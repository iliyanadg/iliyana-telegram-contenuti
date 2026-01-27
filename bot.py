import os
import json
import secrets
import string
from datetime import datetime, timedelta

import gspread
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ================= ENV =================
BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])
WEBHOOK_URL = os.environ["WEBHOOK_URL"]

MY_CONTACT = "@iliyanadg"
VIP_SITE_URL = "https://vip-access.pages.dev/"
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
        "⏳ **Accesso valido 30 giorni**\n\n"
        "🌐 **AREA VIP**\n"
        f"{VIP_SITE_URL}\n\n"
        "🔐 **CODICE VIP PERSONALE**\n"
        f"`{vip_code}`\n\n"
        "Scrivimi quando vuoi 😽"
    )

# ================= UI =================
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 VIP ACCESS", callback_data="vip")]
    ])

def vip_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 PAGA VIP", url=PAYPAL_VIP_URL)],
        [InlineKeyboardButton("✅ HO PAGATO", callback_data="vip_paid")]
    ])

def admin_menu(chat_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ CONFERMA PAGAMENTO", callback_data=f"vip_confirm:{chat_id}")]
    ])

# ================= HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hey 😈 Vuoi entrare nel VIP Access?",
        reply_markup=main_menu()
    )

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "vip":
        await query.edit_message_text(
            "💎 VIP ACCESS\nPrezzo: 4€/mese",
            reply_markup=vip_menu()
        )

    elif query.data == "vip_paid":
        user = query.from_user
        chat_id = query.message.chat_id

        await context.bot.send_message(
            ADMIN_ID,
            f"💎 RICHIESTA VIP\n\n👤 {user.first_name}\n🆔 {chat_id}",
            reply_markup=admin_menu(chat_id)
        )

        await query.edit_message_text("⏳ Verifica pagamento in corso…")

    elif query.data.startswith("vip_confirm:"):
        if query.from_user.id != ADMIN_ID:
            return

        chat_id = int(query.data.split(":")[1])
        vip_code = generate_vip_code()

        await context.bot.send_message(
            chat_id,
            vip_welcome_message(vip_code),
            parse_mode="Markdown"
        )

        save_vip_user(query.from_user, chat_id, vip_code)

# ================= MAIN =================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))

    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        url_path="webhook",
        webhook_url=f"{WEBHOOK_URL}/webhook",
    )

if __name__ == "__main__":
    main()
