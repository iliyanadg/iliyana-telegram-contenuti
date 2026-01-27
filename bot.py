import os
import json
import secrets
import string
from datetime import datetime, timedelta

import gspread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ================= ENV =================
BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])
WEBHOOK_URL = os.environ["WEBHOOK_URL"]
PORT = int(os.environ.get("PORT", "10000"))

# opzionali: se non li hai su Render, usa i default qui sotto
MY_CONTACT = os.environ.get("MY_CONTACT", "@iliyanadg")
VIP_SITE_URL = os.environ.get("VIP_SITE_URL", "https://vip-access.pages.dev/")
PAYPAL_VIP_URL = os.environ.get("PAYPAL_VIP_URL", "https://www.paypal.com/paypalme/iliyanadg/4")

# ================= GOOGLE SHEETS =================
# Su Render la tua variabile si chiama GOOGLE_SERVICE_ACCOUNT_JSON (come nel tuo screenshot)
SERVICE_JSON = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
gc = gspread.service_account_from_dict(json.loads(SERVICE_JSON))
sheet = gc.open("VIP_ACCESS").worksheet("VIP_ACCESS")

# ================= UTIL =================
def generate_vip_code() -> str:
    chars = string.ascii_uppercase + string.digits
    return "VIP-" + "".join(secrets.choice(chars) for _ in range(6))

def save_vip_user(chat_id: int, username: str, vip_code: str):
    now = datetime.now()
    expiry = now + timedelta(days=30)

    sheet.append_row([
        f"https://t.me/{username}" if username else "",
        now.strftime("%Y-%m-%d"),
        expiry.strftime("%Y-%m-%d"),
        now.strftime("%H:%M"),
        vip_code,
        "ACTIVE",
        str(chat_id),
        username or "",
        "telegram",
        1
    ])

def vip_welcome_message(vip_code: str) -> str:
    return (
        "💎 **BENVENUTO NEL VIP ACCESS**\n\n"
        "Da ora puoi scrivermi direttamente qui:\n"
        f"👉 {MY_CONTACT}\n\n"
        "⏳ **Accesso valido 30 giorni**\n\n"
        "🌐 **AREA VIP**\n"
        f"{VIP_SITE_URL}\n\n"
        "🔐 **CODICE VIP PERSONALE**\n"
        f"`{vip_code}`\n\n"
        "⚠️ Il codice è personale e non va condiviso.\n"
        "Scrivimi pure 😽"
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

def admin_actions(chat_id: int):
    # callback_data deve essere corta e semplice
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ CONFERMA PAGAMENTO", callback_data=f"vip_confirm:{chat_id}")],
        [InlineKeyboardButton("❌ NON TROVO PAGAMENTO", callback_data=f"vip_reject:{chat_id}")]
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
    data = query.data

    if data == "vip":
        await query.edit_message_text(
            "💎 VIP ACCESS\nPrezzo: 4€/mese\n\nProcedi dal link e poi premi “HO PAGATO”:",
            reply_markup=vip_menu()
        )
        return

    if data == "vip_paid":
        user = query.from_user
        chat_id = query.message.chat_id  # in privato = id utente

        # manda richiesta admin
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                "💎 **RICHIESTA VIP**\n\n"
                f"👤 Nome: {user.first_name}\n"
                f"🔎 Username: @{user.username}" if user.username else f"👤 Nome: {user.first_name}\n🔎 Username: (nessuno)\n"
            ) + f"\n🆔 Chat ID: `{chat_id}`\n\nConfermi il pagamento?",
            parse_mode="Markdown",
            reply_markup=admin_actions(chat_id)
        )

        await query.edit_message_text("✅ Perfetto. Sto verificando il pagamento 💎")
        return

    if data.startswith("vip_confirm:"):
        if query.from_user.id != ADMIN_ID:
            return

        chat_id = int(data.split(":")[1])

        # recupero info chat (username) direttamente da Telegram
        chat = await context.bot.get_chat(chat_id)
        username = chat.username or ""

        vip_code = generate_vip_code()

        await context.bot.send_message(
            chat_id=chat_id,
            text=vip_welcome_message(vip_code),
            parse_mode="Markdown"
        )

        save_vip_user(chat_id, username, vip_code)

        await query.edit_message_text(f"✅ VIP ATTIVATO per `{chat_id}`\nCodice: `{vip_code}`", parse_mode="Markdown")
        return

    if data.startswith("vip_reject:"):
        if query.from_user.id != ADMIN_ID:
            return

        chat_id = int(data.split(":")[1])
        await context.bot.send_message(
            chat_id=chat_id,
            text="⚠️ Non trovo il pagamento. Inviami qui la ricevuta PayPal e controllo subito."
        )
        await query.edit_message_text(f"❌ Segnalato: pagamento non trovato per `{chat_id}`", parse_mode="Markdown")
        return

# ================= MAIN =================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="webhook",
        webhook_url=f"{WEBHOOK_URL}/webhook",
    )

if __name__ == "__main__":
    main()
