import os
import uuid
import asyncio
import logging
import sqlite3
import requests
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
import yt_dlp

# ============================================================================
# LOG SOZLAMALARI
# ============================================================================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("InstaSaveBot")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8387237045:AAE9-vTG79Rn40jU2lk1QY1fBEeWpmGQV5Q")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "behruz700")

DB_FILE = "bot.db"
pending_downloads = {}
music_search_cache = {}

# ============================================================================
# TILLAR
# ============================================================================
TEXTS = {
    "uz": {
        "choose_lang": "🌐 Tilni tanlang / Choose language / Выберите язык",
        "welcome": (
            "✨ *InstaSave Botiga xush kelibsiz!* ✨\n\n"
            "Men sizga sevimli medialaringizni bir necha soniyada yuklab beraman 🚀\n\n"
            "📌 *Imkoniyatlarim:*\n"
            "🎬 Instagram / TikTok / YouTube — link yuboring\n"
            "🎵 Qo'shiq nomini yozing — men qidirib topaman\n\n"
            "👇 Boshlash uchun havola yoki qo'shiq nomini yozing!"
        ),
        "analyzing": "🔎 Video yuklanmoqda...",
        "video_caption": "✅ *Video tayyor!*\n\n🤖 @InstaSaveBot",
        "audio_caption": "🎧 *{title}*\n\n🤖 @InstaSaveBot",
        "error_generic": "❌ Yuklab bo'lmadi. Havolani tekshiring yoki media yopiq bo'lishi mumkin.",
        "searching_music": "🔍 «{query}» bo'yicha musiqa qidirilmoqda...",
        "music_select": "🎵 Kerakli musiqani tanlang:",
        "music_not_found": "❌ Bu nom bo'yicha musiqa topilmadi.",
        "admin_denied": "❌ Taqiqlangan!",
        "admin_panel": "📊 *Admin Panel*\n\n👥 Jami foydalanuvchilar: *{count}* ta",
        "broadcast_empty": "⚠️ Xabar matnini yozing!",
        "broadcast_done": "✅ Xabar yuborildi.",
        "session_expired": "⚠️ Sessiya eskirgan, qaytadan qidirib ko'ring.",
        "ask_music": "🎵 Ushbu videoning musiqasi (MP3) kerakmi?",
        "btn_yes": "✅ Ha, MP3 kerak",
        "btn_no": "❌ Yo'q",
    },
    "ru": {
        "choose_lang": "🌐 Tilni tanlang / Choose language / Выберите язык",
        "welcome": "✨ *Добро пожаловать в InstaSave Bot!* ✨\n\nОтправьте ссылку или название песни!",
        "analyzing": "🔎 Скачиваю видео...",
        "video_caption": "✅ *Видео готово!*\n\n🤖 @InstaSaveBot",
        "audio_caption": "🎧 *{title}*\n\n🤖 @InstaSaveBot",
        "error_generic": "❌ Не удалось скачать.",
        "searching_music": "🔍 Ищу «{query}»...",
        "music_select": "🎵 Выберите нужный трек:",
        "music_not_found": "❌ Музыка не найдена.",
        "admin_denied": "❌ Доступ запрещён!",
        "admin_panel": "📊 *Админ-панель*\n\n👥 Всего: *{count}*",
        "broadcast_empty": "⚠️ Введите текст!",
        "broadcast_done": "✅ Отправлено.",
        "session_expired": "⚠️ Сессия устарела.",
        "ask_music": "🎵 Нужна музыка (MP3) из этого видео?",
        "btn_yes": "✅ Да, нужен MP3",
        "btn_no": "❌ Нет",
    },
    "en": {
        "choose_lang": "🌐 Tilni tanlang / Choose language / Выберите язык",
        "welcome": "✨ *Welcome to InstaSave Bot!* ✨",
        "analyzing": "🔎 Downloading video...",
        "video_caption": "✅ *Video ready!*\n\n🤖 @InstaSaveBot",
        "audio_caption": "🎧 *{title}*\n\n🤖 @InstaSaveBot",
        "error_generic": "❌ Couldn't download.",
        "searching_music": "🔍 Searching...",
        "music_select": "🎵 Select the music:",
        "music_not_found": "❌ Not found.",
        "admin_denied": "❌ Access denied!",
        "admin_panel": "📊 *Admin Panel*\n\n👥 Users: *{count}*",
        "broadcast_empty": "⚠️ Enter message!",
        "broadcast_done": "⚠️ Sent.",
        "session_expired": "⚠️ Session expired.",
        "ask_music": "🎵 Do you need the music (MP3) from this video?",
        "btn_yes": "✅ Yes, send MP3",
        "btn_no": "❌ No",
    }
}

def t(lang, key, **kwargs):
    text = TEXTS.get(lang, TEXTS["uz"]).get(key, key)
    return text.format(**kwargs) if kwargs else text

# ============================================================================
# DATABASE
# ============================================================================
def db_init():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, lang TEXT DEFAULT 'uz', joined_at TEXT)")
    conn.commit()
    conn.close()

def db_add_user(user_id):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("INSERT OR IGNORE INTO users (user_id, lang, joined_at) VALUES (?, 'uz', datetime('now'))", (user_id,))
    conn.commit()
    conn.close()

def db_set_lang(user_id, lang):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, user_id))
    conn.commit()
    conn.close()

def db_get_lang(user_id):
    conn = sqlite3.connect(DB_FILE)
    row = conn.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row[0] if row else "uz"

def db_all_user_ids():
    conn = sqlite3.connect(DB_FILE)
    rows = conn.execute("SELECT user_id FROM users").fetchall()
    conn.close()
    return [r[0] for r in rows]

def db_count_users():
    conn = sqlite3.connect(DB_FILE)
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    return count

# ============================================================================
# HEALTH-CHECK SERVER (Render o'chib qolmasligi uchun)
# ============================================================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass

def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# ============================================================================
# MULTI-API VIDEO DOWNLOADER (Cobalt + Fallback APIs)
# ============================================================================
def fetch_video_url(url: str):
    # 1. Cobalt API
    try:
        res = requests.post(
            "https://api.cobalt.tools/api/json",
            json={"url": url},
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=10
        )
        if res.status_code == 200:
            data = res.json()
            if data.get("status") in ["stream", "redirect"]:
                return data.get("url")
    except Exception as e:
        logger.error(f"Cobalt API failed: {e}")

    # 2. Rapid API Fallback
    try:
        res = requests.get(f"https://api.vkrnot.com/v2/download?url={url}", timeout=10)
        if res.status_code == 200:
            data = res.json()
            if data.get("data") and data["data"].get("url"):
                return data["data"]["url"]
    except Exception as e:
        logger.error(f"Secondary API failed: {e}")

    return None

def download_yt_audio(url: str):
    outtmpl = f"dl_audio_{uuid.uuid4().hex[:8]}.%(ext)s"
    opts = {
        'quiet': True,
        'no_warnings': True,
        'format': 'bestaudio/best',
        'outtmpl': outtmpl,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        file_path = ydl.prepare_filename(info)
        base, _ = os.path.splitext(file_path)
        mp3_path = base + ".mp3"
        return mp3_path if os.path.exists(mp3_path) else file_path

# ============================================================================
# HANDLERS
# ============================================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db_add_user(update.effective_user.id)
    keyboard = [[
        InlineKeyboardButton("🇺🇿 O'zbek", callback_data="lang:uz"),
        InlineKeyboardButton("🇷🇺 Русский", callback_data="lang:ru"),
        InlineKeyboardButton("🇬🇧 English", callback_data="lang:en"),
    ]]
    await update.message.reply_text(TEXTS["uz"]["choose_lang"], reply_markup=InlineKeyboardMarkup(keyboard))

async def on_language_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = query.data.split(":")[1]
    db_set_lang(update.effective_user.id, lang)
    await query.edit_message_text(t(lang, "welcome"), parse_mode="Markdown")

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, lang: str):
    msg = await update.message.reply_text(t(lang, "analyzing"), parse_mode="Markdown")
    chat_id = update.effective_chat.id

    loop = asyncio.get_running_loop()
    video_url = await loop.run_in_executor(None, lambda: fetch_video_url(url))

    if video_url:
        try:
            await msg.delete()
        except Exception:
            pass

        await context.bot.send_video(
            chat_id=chat_id,
            video=video_url,
            caption=t(lang, "video_caption"),
            parse_mode="Markdown"
        )

        token = uuid.uuid4().hex[:10]
        pending_downloads[token] = {"url": url, "chat_id": chat_id}

        keyboard = [[
            InlineKeyboardButton(t(lang, "btn_yes"), callback_data=f"music:{token}:yes"),
            InlineKeyboardButton(t(lang, "btn_no"), callback_data=f"music:{token}:no"),
        ]]
        await context.bot.send_message(
            chat_id=chat_id,
            text=t(lang, "ask_music"),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await msg.edit_text(t(lang, "error_generic"), parse_mode="Markdown")

async def on_music_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = db_get_lang(update.effective_user.id)

    _, token, choice = query.data.split(":")
    data = pending_downloads.pop(token, None)

    if not data:
        await query.edit_message_text(t(lang, "session_expired"), parse_mode="Markdown")
        return

    if choice == "yes":
        await query.edit_message_text("⏳ MP3 audio yuklanmoqda...", parse_mode="Markdown")
        loop = asyncio.get_running_loop()
        file_path = None
        try:
            file_path = await loop.run_in_executor(None, lambda: download_yt_audio(data["url"]))
            with open(file_path, 'rb') as f:
                await context.bot.send_audio(
                    chat_id=data["chat_id"],
                    audio=f,
                    title="Audio",
                    caption=t(lang, "audio_caption", title="Audio"),
                    parse_mode="Markdown"
                )
            await query.delete_message()
        except Exception as e:
            logger.error(f"MP3 xatosi: {e}")
            await query.edit_message_text(t(lang, "error_generic"), parse_mode="Markdown")
        finally:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
    else:
        try:
            await query.delete_message()
        except Exception:
            pass

SUPPORTED_DOMAINS = ["instagram.com", "tiktok.com", "youtube.com", "youtu.be"]

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db_add_user(user_id)
    lang = db_get_lang(user_id)
    text = update.message.text.strip()

    if any(domain in text for domain in SUPPORTED_DOMAINS):
        await handle_link(update, context, text, lang)
    else:
        await update.message.reply_text("🎵 Qo'shiq qidirish uchun qo'shiq nomini yuboring.")

def main():
    db_init()
    Thread(target=run_health_check_server, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(on_language_chosen, pattern=r"^lang:"))
    app.add_handler(CallbackQueryHandler(on_music_choice, pattern=r"^music:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()
