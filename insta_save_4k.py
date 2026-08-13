import os
import time
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

# ============================================================================
# API TOKEN VA KALITLAR
# ============================================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8387237045:AAE9-vTG79Rn40jU2lk1QY1fBEeWpmGQV5Q")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "behruz700")

DB_FILE = "bot.db"
MAX_FILE_SIZE_MB = 50

pending_downloads = {}

# ============================================================================
# TILLAR (UZ / RU / EN)
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
        "searching_music": "🔍 «{query}» Deezer'dan qidirilmoqda...",
        "music_not_found": "❌ Bu nom bo'yicha musiqa topilmadi.",
        "admin_denied": "❌ Taqiqlangan!",
        "admin_panel": "📊 *Admin Panel*\n\n👥 Jami foydalanuvchilar: *{count}* ta",
        "broadcast_empty": "⚠️ Xabar matnini yozing!",
        "broadcast_done": "✅ Xabar yuborildi.",
        "session_expired": "⚠️ Sessiya eskirgan, havolani qayta yuboring.",
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
        "music_not_found": "❌ Not found.",
        "admin_denied": "❌ Access denied!",
        "admin_panel": "📊 *Admin Panel*\n\n👥 Users: *{count}*",
        "broadcast_empty": "⚠️ Enter message!",
        "broadcast_done": "✅ Sent.",
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
# DATABASE (SQLite)
# ============================================================================
def db_init():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            lang TEXT DEFAULT 'uz',
            joined_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def db_add_user(user_id):
    conn = sqlite3.connect(DB_FILE)
    conn.execute(
        "INSERT OR IGNORE INTO users (user_id, lang, joined_at) VALUES (?, 'uz', datetime('now'))",
        (user_id,)
    )
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
# HEALTH-CHECK SERVER
# ============================================================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Active")

    def log_message(self, format, *args):
        pass


def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(('0.0.0.0', port), HealthCheckHandler).serve_forever()


# ============================================================================
# HELPER: yt-dlp SOZLAMALARI
# ============================================================================
def base_ydl_opts():
    opts = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'user_agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ),
    }
    if os.path.exists("cookies.txt"):
        opts['cookiefile'] = "cookies.txt"
    return opts


# ============================================================================
# DEEZER API ORQALI BEPUL MUSIQA QIDIRUV FUNKSIYASI
# ============================================================================
def search_deezer_music(query: str):
    """
    Deezer API orqali musiqa qidiradi. API Key va ro'yxatdan o'tish shart emas.
    """
    url = f"https://api.deezer.com/search?q={requests.utils.quote(query)}&limit=1"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("data"):
                song = data["data"][0]
                return {
                    "title": song.get("title"),
                    "artist": song.get("artist", {}).get("name"),
                    "audio_url": song.get("preview"),  # Direct audio stream URL
                }
    except Exception as e:
        logger.error(f"Deezer API Error: {e}")
    return None


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
    await update.message.reply_text(
        TEXTS["uz"]["choose_lang"],
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def on_language_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = query.data.split(":")[1]
    db_set_lang(update.effective_user.id, lang)
    await query.edit_message_text(t(lang, "welcome"), parse_mode="Markdown")


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = db_get_lang(update.effective_user.id)
    args = context.args
    if not args or args[0] != ADMIN_PASSWORD:
        await update.message.reply_text(t(lang, "admin_denied"), parse_mode="Markdown")
        return
    await update.message.reply_text(
        t(lang, "admin_panel", count=db_count_users()),
        parse_mode="Markdown"
    )


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = db_get_lang(update.effective_user.id)
    args = context.args
    if not args or args[0] != ADMIN_PASSWORD:
        await update.message.reply_text(t(lang, "admin_denied"), parse_mode="Markdown")
        return

    text = " ".join(args[1:])
    if not text:
        await update.message.reply_text(t(lang, "broadcast_empty"), parse_mode="Markdown")
        return

    count = 0
    for uid in db_all_user_ids():
        try:
            await context.bot.send_message(chat_id=uid, text=text)
            count += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass

    await update.message.reply_text(t(lang, "broadcast_done", count=count), parse_mode="Markdown")


async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, lang: str):
    msg = await update.message.reply_text(t(lang, "analyzing"), parse_mode="Markdown")
    chat_id = update.effective_chat.id

    loop = asyncio.get_running_loop()
    outtmpl = f"dl_{uuid.uuid4().hex[:8]}.%(ext)s"
    file_path = None

    opts = base_ydl_opts()
    opts['outtmpl'] = outtmpl
    opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    opts['max_filesize'] = MAX_FILE_SIZE_MB * 1024 * 1024

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
            file_path = ydl.prepare_filename(info)

        if not os.path.exists(file_path):
            raise FileNotFoundError("Fayl topilmadi")

        try:
            await msg.delete()
        except Exception:
            pass

        with open(file_path, 'rb') as f:
            await context.bot.send_video(
                chat_id=chat_id,
                video=f,
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

    except Exception as e:
        logger.error(f"Yuklash xatoligi: {e}")
        await msg.edit_text(t(lang, "error_generic"), parse_mode="Markdown")
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)


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
        outtmpl = f"audio_{uuid.uuid4().hex[:8]}.%(ext)s"
        file_path = None

        opts = base_ydl_opts()
        opts['outtmpl'] = outtmpl
        opts['format'] = 'bestaudio/best'
        opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(data["url"], download=True))
                file_path = ydl.prepare_filename(info)
                base, _ = os.path.splitext(file_path)
                mp3_path = base + ".mp3"
                if os.path.exists(mp3_path):
                    file_path = mp3_path

            title = info.get('title', 'Audio')
            with open(file_path, 'rb') as f:
                await context.bot.send_audio(
                    chat_id=data["chat_id"],
                    audio=f,
                    title=title,
                    caption=t(lang, "audio_caption", title=title),
                    parse_mode="Markdown"
                )
            await query.delete_message()
        except Exception as e:
            logger.error(f"MP3 yuklash xatosi: {e}")
            await query.edit_message_text(t(lang, "error_generic"), parse_mode="Markdown")
        finally:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
    else:
        try:
            await query.delete_message()
        except Exception:
            pass


async def handle_music_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query_text: str, lang: str):
    msg = await update.message.reply_text(t(lang, "searching_music", query=query_text), parse_mode="Markdown")
    loop = asyncio.get_running_loop()

    # Deezer API orqali musiqa ma'lumotlarini olamiz
    song_info = await loop.run_in_executor(None, lambda: search_deezer_music(query_text))

    if not song_info or not song_info.get("audio_url"):
        await msg.edit_text(t(lang, "music_not_found"), parse_mode="Markdown")
        return

    full_title = f"{song_info['artist']} - {song_info['title']}"

    try:
        # Audioni to'g'ridan-to'g'ri Deezer havolasi orqali yuboramiz
        await update.message.reply_audio(
            audio=song_info["audio_url"],
            title=song_info['title'],
            performer=song_info['artist'],
            caption=t(lang, "audio_caption", title=full_title),
            parse_mode="Markdown"
        )
        await msg.delete()
    except Exception as e:
        logger.error(f"Deezer Audio Send Error: {e}")
        await msg.edit_text(t(lang, "music_not_found"), parse_mode="Markdown")


SUPPORTED_DOMAINS = ["instagram.com", "tiktok.com", "youtube.com", "youtu.be"]


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db_add_user(user_id)
    lang = db_get_lang(user_id)

    text = update.message.text.strip()

    if any(domain in text for domain in SUPPORTED_DOMAINS):
        await handle_link(update, context, text, lang)
    else:
        await handle_music_search(update, context, text, lang)


def main():
    db_init()
    Thread(target=run_health_check_server, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CallbackQueryHandler(on_language_chosen, pattern=r"^lang:"))
    app.add_handler(CallbackQueryHandler(on_music_choice, pattern=r"^music:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot ishga tushdi...")
    app.run_polling()


if __name__ == "__main__":
    main()
