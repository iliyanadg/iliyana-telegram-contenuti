import os
import json
import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

# --- VIP sheets/code additions ---
import secrets
import string
from datetime import datetime, timedelta

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

# ---------------- ENV ----------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
MY_CONTACT = os.environ.get("MY_CONTACT", "@iliyanadg")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # es: https://iliyana-telegram-contenuti-1.onrender.com
PORT = int(os.environ.get("PORT", "10000"))

# opzionali per VIP area
VIP_SITE_URL = os.environ.get("VIP_SITE_URL", "https://vip-access.pages.dev/")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN mancante nelle env.")
if ADMIN_ID == 0:
    raise RuntimeError("ADMIN_ID mancante o 0 nelle env.")
if not WEBHOOK_URL:
    raise RuntimeError("WEBHOOK_URL mancante nelle env.")

# PayPal links
PAYPAL_VIP_URL = "https://www.paypal.com/paypalme/iliyanadg/4"
PAYPAL_CONTENT_URL = "https://www.paypal.com/paypalme/iliyanadg"  # importo variabile

# ---------------- GOOGLE SHEETS (VIP) ----------------
# Variabile su Render: GOOGLE_SERVICE_ACCOUNT_JSON
SERVICE_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
SHEET_NAME = os.environ.get("SHEET_NAME", "VIP_ACCESS")
WORKSHEET_NAME = os.environ.get("WORKSHEET_NAME", "VIP_ACCESS")

sheet = None
if SERVICE_JSON:
    try:
        gc = gspread.service_account_from_dict(json.loads(SERVICE_JSON))
        sheet = gc.open(SHEET_NAME).worksheet(WORKSHEET_NAME)
    except Exception as e:
        # Non blocchiamo il bot: se Sheets non è configurato bene, il bot continua a funzionare
        print("⚠️ Errore Google Sheets:", e)
        sheet = None

# ---------------- TESTI (AGGIORNATI) ----------------
WELCOME_TEXT = (
    "Hey… sei arrivato nel posto giusto 😈\n"
    "Adesso scegli bene 😽\n\n"
    "🔒 Vuoi sbloccare contenuti (senza contatto diretto)?\n"
    "💎 Vuoi il VIP e parlarmi direttamente?\n\n"
    "Scegli qui sotto 👇"
)

# 🔒 NON-VIP: pacchetti + regole chiare (NO cam, NO chat)
PRICING_TEXT = (
    "🔒 ACQUISTA CONTENUTI\n\n"
    "📷 PACCHETTI (contenuti registrati)\n"
    "• 10 foto hot — 15€\n"
    "• 10 foto + 1 video breve (1–2 min) — 25€\n"
    "• 15 foto + 2 video (breve + medio) — 40€\n\n"
    "➕ EXTRA (su richiesta)\n"
    "• video medio (3–5 min) — 25–35€\n"
    "• video lungo (6–10 min) — 40–50€\n\n"
    "📌 COME FUNZIONA\n"
    "1) ✍️ Scrivimi cosa vuoi (o dimmi quale pacchetto)\n"
    "2) 💳 Ti dico il totale\n"
    "3) 🧾 Paga con causale: Membership + tuo nome/username\n"
    "4) ✅ Premi “HO PAGATO”\n\n"
    "🚫 Nessuna cam\n"
    "🚫 Nessuna chat privata continua\n"
    "✅ Solo contenuti registrati"
)

# 💎 VIP: contatto diretto; sex chat NON inclusa (extra); cam SOLO VIP (extra)
VIP_TEXT = (
    "💎 VIP ACCESS\n\n"
    "Uno spazio più intimo e riservato:\n"
    "✅ contatto diretto con me (messaggi + audio)\n"
    "✅ chat privata\n"
    "✅ accesso ai contenuti che pubblico su OnlyFans\n"
    "✅ possibilità di acquistare contenuti extra\n\n"
    "📌 EXTRA (su richiesta, a pagamento)\n"
    "• sex chat\n"
    "• contenuti personalizzati\n\n"
    "🎥 CAM LIVE — SOLO VIP (extra)\n"
    "• 5 min — 15€\n"
    "• 10 min — 20€\n"
    "• 15 min — 25€\n\n"
    "💶 Prezzo VIP: 4€ / mese\n\n"
    "📌 Causale obbligatoria:\n"
    "👉 Membership + tuo nome oppure username Telegram\n\n"
    "Procedi dal link qui sotto 👇"
)

VIP_AFTER_PAID_TEXT = (
    "✅ Perfetto.\n\n"
    "Ho ricevuto la tua richiesta VIP.\n"
    "Appena verifico il pagamento, riceverai qui il mio contatto diretto 💎"
)

# aggiornato: include codice + link VIP
def build_welcome_vip_text(vip_code: str) -> str:
    return (
        "💎 Benvenuto nel VIP Access\n\n"
        "Da ora puoi scrivermi direttamente qui:\n"
        f"👉 {MY_CONTACT}\n\n"
        "⏳ Accesso valido 30 giorni.\n\n"
        "🌐 AREA VIP:\n"
        f"{VIP_SITE_URL}\n\n"
        "🔐 CODICE VIP PERSONALE:\n"
        f"{vip_code}\n\n"
        "⚠️ Il codice è personale e non va condiviso.\n"
        "Scrivimi pure non vedo l'ora di conoscerti. 😽"
    )

VIP_REJECT_TEXT = (
    "⚠️ Non riesco a trovare il pagamento.\n\n"
    "Ricontrolla per favore:\n"
    "1) importo corretto (4€)\n"
    "2) pagamento su PayPal risultante *Completato*\n"
    "3) causale: Membership + tuo nome/username\n\n"
    "📎 Premi il bottone qui sotto e inviami la ricevuta (screenshot o PDF) ✅"
)

BUY_AFTER_PAID_TEXT = (
    "✅ Perfetto.\n\n"
    "Ho ricevuto la conferma del pagamento.\n"
    "Appena verifico, ti scrivo qui e procediamo ✅"
)

BUY_REJECT_TEXT = (
    "⚠️ Non riesco a verificare il pagamento.\n\n"
    "📎 Premi il bottone qui sotto e inviami la ricevuta (screenshot o PDF) ✅"
)

BUY_CONFIRM_TEXT = (
    "✅ Pagamento confermato.\n\n"
    "Perfetto, preparo il contenuto e te lo invio qui 💋"
)

PROBLEM_INTRO_TEXT = (
    "⚠️ SEGNALA UN PROBLEMA\n\n"
    "Scrivi qui sotto cosa è successo:\n"
    "• cosa stavi facendo\n"
    "• cosa non funziona\n"
    "• (se puoi) orario + screenshot\n\n"
    "📌 Questo spazio è solo per problemi tecnici, non è una chat personale."
)

PROBLEM_THANKS_TEXT = (
    "✅ Segnalazione inviata.\n"
    "Controllo appena possibile."
)

# ---------------- UI ----------------
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("ACQUISTA CONTENUTI 🔒", callback_data="buy")],
        [InlineKeyboardButton("VIP ACCESS 💎", callback_data="vip")],
        [InlineKeyboardButton("⚠️ SEGNALA UN PROBLEMA", callback_data="problem")],
    ])

def buy_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 PAGA", url=PAYPAL_CONTENT_URL)],
        [InlineKeyboardButton("✅ HO PAGATO", callback_data="buy_paid")],
        [InlineKeyboardButton("⬅️ Menu", callback_data="back")],
    ])

def vip_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 PAGA VIP", url=PAYPAL_VIP_URL)],
        [InlineKeyboardButton("✅ HO PAGATO", callback_data="vip_paid")],
        [InlineKeyboardButton("⬅️ Menu", callback_data="back")],
    ])

def user_after_request_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Aggiungi dettagli", callback_data="add_details")],
        [InlineKeyboardButton("🆕 Nuova richiesta", callback_data="buy")],
        [InlineKeyboardButton("⬅️ Menu", callback_data="back")],
    ])

def admin_vip_actions(chat_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ CONFERMA PAGAMENTO", callback_data=f"vip_confirm:{chat_id}")],
        [InlineKeyboardButton("❌ NON TROVO PAGAMENTO", callback_data=f"vip_reject:{chat_id}")],
        [InlineKeyboardButton("🎯 IMPOSTA TARGET", callback_data=f"settarget:{chat_id}")],
        [InlineKeyboardButton("❌ ANNULLA TARGET", callback_data="unsettarget")],
    ])

def admin_buy_actions(chat_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ PAGAMENTO OK", callback_data=f"buy_confirm:{chat_id}")],
        [InlineKeyboardButton("❌ NON TROVO PAGAMENTO", callback_data=f"buy_reject:{chat_id}")],
        [InlineKeyboardButton("🎯 IMPOSTA TARGET", callback_data=f"settarget:{chat_id}")],
        [InlineKeyboardButton("❌ ANNULLA TARGET", callback_data="unsettarget")],
    ])

def receipt_buttons(kind: str):
    if kind == "vip":
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📎 INVIA RICEVUTA", callback_data="vip_receipt")],
            [InlineKeyboardButton("⬅️ Menu", callback_data="back")],
        ])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📎 INVIA RICEVUTA", callback_data="buy_receipt")],
        [InlineKeyboardButton("⬅️ Menu", callback_data="back")],
    ])

# ---------------- HELPERS ----------------
def format_user_block(user) -> str:
    name = " ".join([x for x in [user.first_name, user.last_name] if x]).strip()
    uname = f"@{user.username}" if user.username else ""
    if uname and name:
        return f"👤 {name}\n🔗 {uname}"
    if uname and not name:
        return f"🔗 {uname}"
    return f"👤 {name}" if name else "👤 (no name)"

def reset_user_state(context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("awaiting_request", None)
    context.user_data.pop("request_mode", None)
    context.user_data.pop("awaiting_vip_receipt", None)
    context.user_data.pop("awaiting_buy_receipt", None)
    context.user_data.pop("awaiting_problem", None)

# --- VIP helpers (new) ---
def generate_vip_code() -> str:
    chars = string.ascii_uppercase + string.digits
    return "VIP-" + "".join(secrets.choice(chars) for _ in range(6))

def save_vip_user(chat_id: int, username: str, vip_code: str):
    """
    Salva l'utente VIP su Google Sheets (se configurato).
    Struttura riga identica al bot attuale.
    """
    if sheet is None:
        return

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

# ---------------- HANDLERS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_user_state(context)
    await update.message.reply_text(WELCOME_TEXT, reply_markup=main_menu())

async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_user_state(context)
    await update.message.reply_text(WELCOME_TEXT, reply_markup=main_menu())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # -------- MENU USER --------
    if data == "buy":
        reset_user_state(context)
        context.user_data["awaiting_request"] = True
        context.user_data["request_mode"] = "new"
        await query.edit_message_text(PRICING_TEXT, reply_markup=buy_menu())

    elif data == "add_details":
        reset_user_state(context)
        context.user_data["awaiting_request"] = True
        context.user_data["request_mode"] = "details"
        await query.edit_message_text(
            "➕ Aggiungi dettagli\n\nScrivi qui ulteriori dettagli (durata, preferenze, urgenza, ecc.)."
        )

    elif data == "vip":
        reset_user_state(context)
        await query.edit_message_text(VIP_TEXT, reply_markup=vip_menu())

    elif data == "problem":
        reset_user_state(context)
        context.user_data["awaiting_problem"] = True
        await query.edit_message_text(
            PROBLEM_INTRO_TEXT,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Menu", callback_data="back")]])
        )

    elif data == "vip_paid":
        user = query.from_user
        chat_id = query.message.chat_id
        reset_user_state(context)

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                "💎 VIP — UTENTE HA PREMUTO “HO PAGATO”\n\n"
                f"{format_user_block(user)}\n"
                f"🆔 Chat ID: {chat_id}\n\n"
                "Controlla PayPal:\n"
                "✅ CONFERMA PAGAMENTO se lo trovi (ATTIVA VIP + salva in Sheets)\n"
                "❌ NON TROVO PAGAMENTO se non lo trovi (in quel caso chiederò ricevuta all’utente)"
            ),
            reply_markup=admin_vip_actions(chat_id)
        )
        await query.edit_message_text(VIP_AFTER_PAID_TEXT)

    elif data == "buy_paid":
        user = query.from_user
        chat_id = query.message.chat_id
        reset_user_state(context)

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                "🔒 CONTENUTI — UTENTE HA PREMUTO “HO PAGATO”\n\n"
                f"{format_user_block(user)}\n"
                f"🆔 Chat ID: {chat_id}\n\n"
                "Controlla PayPal:\n"
                "✅ PAGAMENTO OK se lo trovi\n"
                "❌ NON TROVO PAGAMENTO se non lo trovi (in quel caso chiederò ricevuta all’utente)"
            ),
            reply_markup=admin_buy_actions(chat_id)
        )
        await query.edit_message_text(BUY_AFTER_PAID_TEXT)

    elif data == "vip_receipt":
        reset_user_state(context)
        context.user_data["awaiting_vip_receipt"] = True
        await query.edit_message_text(
            "📎 INVIA RICEVUTA VIP\n\n"
            "Mandami ora uno screenshot o un PDF del pagamento PayPal.\n"
            "Assicurati che si vedano: importo, data e stato *Completato* ✅"
        )

    elif data == "buy_receipt":
        reset_user_state(context)
        context.user_data["awaiting_buy_receipt"] = True
        await query.edit_message_text(
            "📎 INVIA RICEVUTA (CONTENUTI)\n\n"
            "Mandmi ora uno screenshot o un PDF del pagamento.\n"
            "Assicurati che si vedano: importo, data e stato *Completato* ✅"
        )

    elif data == "back":
        reset_user_state(context)
        await query.edit_message_text(WELCOME_TEXT, reply_markup=main_menu())

    # -------- AZIONI ADMIN --------
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

        # NEW: genera codice + salva su Sheets + manda welcome con codice/link
        try:
            chat = await context.bot.get_chat(target_chat)
            username = chat.username or ""
        except Exception:
            username = ""

        vip_code = generate_vip_code()

        await context.bot.send_message(chat_id=target_chat, text=build_welcome_vip_text(vip_code))

        # salva su Sheets (se configurato)
        try:
            save_vip_user(target_chat, username, vip_code)
        except Exception as e:
            # non bloccare: segnala solo in log
            print("⚠️ Errore salvataggio VIP su Sheets:", e)

        await query.message.reply_text(
            f"✅ VIP confermato e benvenuto inviato a: {target_chat}\n"
            f"🔐 Codice: {vip_code}\n"
            f"{'🧾 Salvato su Sheets ✅' if sheet is not None else '🧾 Sheets non configurato (skippato)'}"
        )

    elif data.startswith("vip_reject:"):
        if query.from_user.id != ADMIN_ID:
            return
        target_chat = int(data.split(":", 1)[1])
        await context.bot.send_message(
            chat_id=target_chat,
            text=VIP_REJECT_TEXT,
            reply_markup=receipt_buttons("vip"),
        )
        await query.message.reply_text(f"❌ Ho chiesto la ricevuta VIP a: {target_chat}")

    elif data.startswith("buy_confirm:"):
        if query.from_user.id != ADMIN_ID:
            return
        target_chat = int(data.split(":", 1)[1])
        await context.bot.send_message(chat_id=target_chat, text=BUY_CONFIRM_TEXT)
        await query.message.reply_text(f"✅ Conferma pagamento contenuti inviata a: {target_chat}")

    elif data.startswith("buy_reject:"):
        if query.from_user.id != ADMIN_ID:
            return
        target_chat = int(data.split(":", 1)[1])
        await context.bot.send_message(
            chat_id=target_chat,
            text=BUY_REJECT_TEXT,
            reply_markup=receipt_buttons("buy"),
        )
        await query.message.reply_text(f"❌ Ho chiesto la ricevuta pagamento contenuti a: {target_chat}")

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    context.user_data.pop("admin_target_chat", None)
    await update.message.reply_text("✅ Target annullato.")

# ---------------- ADMIN OUTGOING (target) ----------------
async def admin_outgoing_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    target_chat = context.user_data.get("admin_target_chat")
    if not target_chat:
        await update.message.reply_text("⚠️ Nessun target impostato. Premi 🎯 IMPOSTA TARGET su una richiesta.")
        return

    await context.bot.copy_message(
        chat_id=int(target_chat),
        from_chat_id=update.effective_chat.id,
        message_id=update.message.message_id
    )
    await update.message.reply_text("✅ Inviato all’utente.")

# ---------------- USER TEXT (request/problem) ----------------
async def user_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 1) Segnalazione problema
    if context.user_data.get("awaiting_problem"):
        context.user_data["awaiting_problem"] = False

        user = update.effective_user
        chat_id = update.effective_chat.id

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                "⚠️ SEGNALAZIONE PROBLEMA\n\n"
                f"{format_user_block(user)}\n"
                f"🆔 Chat ID: {chat_id}\n\n"
                f"📝 Testo:\n{update.message.text}"
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎯 IMPOSTA TARGET", callback_data=f"settarget:{chat_id}")],
                [InlineKeyboardButton("❌ ANNULLA TARGET", callback_data="unsettarget")],
            ])
        )

        await update.message.reply_text(PROBLEM_THANKS_TEXT, reply_markup=user_after_request_menu())
        return

    # 2) Richiesta contenuti (testo)
    if context.user_data.get("awaiting_request"):
        context.user_data["awaiting_request"] = False
        mode = context.user_data.get("request_mode", "new")

        user = update.effective_user
        chat_id = update.effective_chat.id
        header = "📩 NUOVA RICHIESTA CONTENUTO" if mode == "new" else "➕ DETTAGLI AGGIUNTIVI"

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"{header}\n\n"
                f"{format_user_block(user)}\n"
                f"🆔 Chat ID: {chat_id}\n\n"
                f"📝 Testo:\n{update.message.text}"
            ),
            reply_markup=admin_buy_actions(chat_id)
        )

        await update.message.reply_text(
            "✅ Richiesta inviata.\nRiceverai qui le info per procedere.",
            reply_markup=user_after_request_menu()
        )
        return

    await update.message.reply_text("👇 Usa il menu per continuare.", reply_markup=main_menu())

# ---------------- USER MEDIA (request/receipt) ----------------
async def user_media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id

    # 1) Ricevuta VIP
    if context.user_data.get("awaiting_vip_receipt"):
        context.user_data["awaiting_vip_receipt"] = False

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                "📎 RICEVUTA VIP RICEVUTA\n\n"
                f"{format_user_block(user)}\n"
                f"🆔 Chat ID: {chat_id}\n\n"
                "Ora puoi:\n"
                "✅ CONFERMA PAGAMENTO / ❌ NON TROVO PAGAMENTO"
            ),
            reply_markup=admin_vip_actions(chat_id)
        )

        await context.bot.copy_message(
            chat_id=ADMIN_ID,
            from_chat_id=update.effective_chat.id,
            message_id=update.message.message_id
        )

        await update.message.reply_text("✅ Ricevuta ricevuta. Sto verificando 💎")
        return

    # 2) Ricevuta contenuti
    if context.user_data.get("awaiting_buy_receipt"):
        context.user_data["awaiting_buy_receipt"] = False

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                "📎 RICEVUTA (CONTENUTI) RICEVUTA\n\n"
                f"{format_user_block(user)}\n"
                f"🆔 Chat ID: {chat_id}"
            ),
            reply_markup=admin_buy_actions(chat_id)
        )

        await context.bot.copy_message(
            chat_id=ADMIN_ID,
            from_chat_id=update.effective_chat.id,
            message_id=update.message.message_id
        )

        await update.message.reply_text("✅ Ricevuta ricevuta. Controllo e ti rispondo 🔒")
        return

    # 3) Media come richiesta contenuto
    if context.user_data.get("awaiting_request"):
        context.user_data["awaiting_request"] = False
        mode = context.user_data.get("request_mode", "new")
        header = "📩 NUOVA RICHIESTA (MEDIA)" if mode == "new" else "➕ DETTAGLI (MEDIA)"

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"{header}\n\n"
                f"{format_user_block(user)}\n"
                f"🆔 Chat ID: {chat_id}\n\n"
                "📎 Media inviato (copiato qui sotto)."
            ),
            reply_markup=admin_buy_actions(chat_id)
        )

        await context.bot.copy_message(
            chat_id=ADMIN_ID,
            from_chat_id=update.effective_chat.id,
            message_id=update.message.message_id
        )

        await update.message.reply_text(
            "✅ Ricevuto.\nTi rispondo qui con i dettagli 🔒",
            reply_markup=user_after_request_menu()
        )
        return

    await update.message.reply_text(
        "📎 Ho ricevuto il file.\n\n"
        "Se è una ricevuta: usa il bottone “📎 INVIA RICEVUTA” solo quando te lo chiedo.\n"
        "Se è una richiesta: premi “ACQUISTA CONTENUTI 🔒” e scrivimi cosa vuoi."
    )

# ---------------- WEBHOOK SERVER (Render) ----------------
app = Application.builder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("menu", menu_cmd))
app.add_handler(CommandHandler("cancel", cancel_cmd))
app.add_handler(CallbackQueryHandler(button_handler))

# Admin outgoing verso target (solo admin)
app.add_handler(MessageHandler(filters.User(ADMIN_ID) & ~filters.COMMAND, admin_outgoing_handler), group=0)

# User testo
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, user_text_handler), group=1)

# User media
app.add_handler(MessageHandler(
    (filters.PHOTO | filters.VIDEO | filters.VOICE | filters.Document.ALL) & ~filters.COMMAND,
    user_media_handler
), group=1)

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
    await app.bot.set_webhook(webhook_full, drop_pending_updates=True)

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
