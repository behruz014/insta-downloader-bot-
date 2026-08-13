import os
import time
import uuid
import asyncio
import logging
import sqlite3
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
# API TOKEN VA PAROL
# ============================================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8387237045:AAE9-vTG79Rn40jU2lk1QY1fBEeWpmGQV5Q")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "behruz700")

DB_FILE = "bot.db"
MAX_FILE_SIZE_MB = 50
PLAYLIST_LIMIT = 5
PROGRESS_UPDATE_INTERVAL = 3

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
        "analyzing": "🔎 Havola tekshirilmoqda...",
        "choose_quality": "🎯 *{title}*\n\nQaysi formatda yuklab beray?",
        "btn_video_best": "🎥 Video (yaxshi sifat)",
        "btn_audio_only": "🎵 Faqat audio (MP3)",
        "btn_cancel": "❌ Bekor qilish",
        "cancelled": "❌ Bekor qilindi.",
        "downloading": "⏳ Yuklanmoqda... {percent}",
        "converting": "🔄 Fayl tayyorlanmoqda...",
        "video_caption": "✅ *Video tayyor!*\n\n🤖 @InstaSaveBot",
        "audio_caption": "🎧 *{title}*\n\n🤖 @InstaSaveBot",
        "error_generic": "❌ Yuklab bo'lmadi. Havolani tekshiring yoki media yopiq/bloklangan bo'lishi mumkin.",
        "error_toolarge": "❌ Fayl juda katta (limit: {limit}MB).",
        "searching_music": "🔍 «{query}» qidirilmoqda...",
        "music_not_found": "❌ Bu nom bo'yicha musiqa topilmadi.",
        "playlist_found": "📃 Playlist topildi: *{count} ta* video.\nBirinchi *{limit} ta* videoni yuklaymi?",
        "btn_playlist_yes": "✅ Ha, yuklash",
        "btn_playlist_no": "❌ Yo'q",
        "playlist_progress": "⏳ Playlist yuklanmoqda: {done}/{total}",
        "playlist_done": "✅ Playlist tugadi!",
        "admin_denied": "❌ Taqiqlangan!",
        "admin_panel": "📊 *Admin Panel*\n\n👥 Jami foydalanuvchilar: *{count}* ta",
        "broadcast_empty": "⚠️ Xabar matnini yozing!",
        "broadcast_done": "✅ Xabar yuborildi.",
        "session_expired": "⚠️ Sessiya eskirgan, havolani qayta yuboring.",
        "ask_music": "🎵 Videoning musiqasini alohida (MP3) yuboraymi?",
        "ask_description": "📝 Video tavsifini (opisaniyasini) ham yuboraymi?",
        "btn_yes": "✅ Ha",
        "btn_no": "❌ Yo'q",
        "no_description": "ℹ️ Bu video uchun tavsif topilmadi.",
    },
    "ru": {
        "choose_lang": "🌐 Tilni tanlang / Choose language / Выберите язык",
        "welcome": (
            "✨ *Добро пожаловать в InstaSave Bot!* ✨\n\n"
            "Я скачаю ваши любимые медиа за пару секунд 🚀\n\n"
            "👇 Отправьте ссылку или название песни!"
        ),
        "analyzing": "🔎 Проверяю ссылку...",
        "choose_quality": "🎯 *{title}*\n\nВ каком формате скачать?",
        "btn_video_best": "🎥 Видео (хорошее качество)",
        "btn_audio_only": "🎵 Только аудио (MP3)",
        "btn_cancel": "❌ Отмена",
        "cancelled": "❌ Отменено.",
        "downloading": "⏳ Загрузка... {percent}",
        "converting": "🔄 Подготовка файла...",
        "video_caption": "✅ *Видео готово!*\n\n🤖 @InstaSaveBot",
        "audio_caption": "🎧 *{title}*\n\n🤖 @InstaSaveBot",
        "error_generic": "❌ Не удалось скачать.",
        "error_toolarge": "❌ Файл слишком большой.",
        "searching_music": "🔍 Ищу «{query}»...",
        "music_not_found": "❌ Музыка не найдена.",
        "playlist_found": "📃 Найден плейлист.",
        "btn_playlist_yes": "✅ Да",
        "btn_playlist_no": "❌ Нет",
        "playlist_progress": "⏳ Загрузка: {done}/{total}",
        "playlist_done": "✅ Готово!",
        "admin_denied": "❌ Доступ запрещён!",
        "admin_panel": "📊 *Админ-панель*\n\n👥 Всего: *{count}*",
        "broadcast_empty": "⚠️ Введите текст!",
        "broadcast_done": "✅ Отправлено.",
        "session_expired": "⚠️ Сессия устарела, отправьте ссылку заново.",
        "ask_music": "🎵 Отправить музыку из видео отдельно (MP3)?",
        "ask_description": "📝 Отправить описание видео?",
        "btn_yes": "✅ Да",
        "btn_no": "❌ Нет",
        "no_description": "ℹ️ Описание не найдено.",
    },
    "en": {
        "choose_lang": "🌐 Tilni tanlang / Choose language / Выберите язык",
        "welcome": "✨ *Welcome to InstaSave Bot!* ✨\n\nSend a link or a song name to start!",
        "analyzing": "🔎 Checking the link...",
        "choose_quality": "🎯 *{title}*\n\nWhich format?",
        "btn_video_best": "🎥 Video",
        "btn_audio_only": "🎵 Audio only (MP3)",
        "btn_cancel": "❌ Cancel",
        "cancelled": "❌ Cancelled.",
        "downloading": "⏳ Downloading... {percent}",
        "converting": "🔄 Preparing...",
        "video_caption": "✅ *Video ready!*\n\n🤖 @InstaSaveBot",
        "audio_caption": "🎧 *{title}*\n\n🤖 @InstaSaveBot",
        "error_generic": "❌ Couldn't download.",
        "error_toolarge": "❌ File too large.",
        "searching_music": "🔍 Searching...",
        "music_not_found": "❌ Not found.",
        "playlist_found": "📃 Playlist found.",
        "btn_playlist_yes": "✅ Yes",
        "btn_playlist_no": "❌ No",
        "playlist_progress": "⏳ Downloading: {done}/{total}",
        "playlist_done": "✅ Done!",
        "admin_denied": "❌ Access denied!",
        "admin_panel": "📊 *Admin Panel*\n\n👥 Users: *{count}*",
        "broadcast_empty": "⚠️ Enter message!",
        "broadcast_done": "✅ Sent.",
        "session_expired": "⚠️ Session expired.",
        "ask_music": "🎵 Send video's music separately (MP3)?",
        "ask_description": "📝 Send video description?",
        "btn_yes": "✅ Yes",
        "btn_no": "❌ No",
        "no_description": "ℹ️ No description.",
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
# HELPER: yt-dlp
# ============================================================================
def base_ydl_opts():
    opts = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': False,
        'user_agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        ),
    }
    if os.path.exists("cookies.txt"):
        opts['cookiefile'] = "cookies.txt"
    return opts


def make_progress_hook(loop, bot, chat_id, message_id, lang):
    last_edit = {"time": 0}

    def hook(d):
        if d.get('status') != 'downloading':
            return
        now = time.time()
        if now - last_edit["time"] < PROGRESS_UPDATE_INTERVAL:
            return
        last_edit["time"] = now
        percent = d.get('_percent_str', '').strip()

        async def edit():
            try:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=t(lang, "downloading", percent=percent),
                    parse_mode="Markdown"
                )
            except Exception:
                pass

        asyncio.run_coroutine_threadsafe(edit(), loop)

    return hook


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

    try:
        opts = base_ydl_opts()
        loop = asyncio.get_running_loop()
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))
    except Exception as e:
        logger.error(f"Tahlil xatoligi: {e}")
        await msg.edit_text(t(lang, "error_generic"), parse_mode="Markdown")
        return

    title = info.get('title', 'Media')
    token = uuid.uuid4().hex[:10]
    pending_downloads[token] = {"url": url, "chat_id": update.effective_chat.id, "title": title}

    keyboard = [
        [InlineKeyboardButton(t(lang, "btn_video_best"), callback_data=f"q:{token}:video")],
        [InlineKeyboardButton(t(lang, "btn_audio_only"), callback_data=f"q:{token}:audio")],
        [InlineKeyboardButton(t(lang, "btn_cancel"), callback_data=f"q:{token}:cancel")],
    ]
    await msg.edit_text(
        t(lang, "choose_quality", title=title),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def on_quality_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = db_get_lang(update.effective_user.id)

    _, token, choice = query.data.split(":")
    data = pending_downloads.pop(token, None)
    if not data:
        await query.edit_message_text(t(lang, "session_expired"), parse_mode="Markdown")
        return

    if choice == "cancel":
        await query.edit_message_text(t(lang, "cancelled"), parse_mode="Markdown")
        return

    url = data["url"]
    await query.edit_message_text(t(lang, "downloading", percent=""), parse_mode="Markdown")
    try:
        await download_and_send(
            context=context,
            chat_id=data["chat_id"],
            status_message_id=query.message.message_id,
            url=url,
            lang=lang,
            as_audio=(choice == "audio"),
            offer_extras=(choice == "video"),
        )
    except Exception:
        pass


async def download_and_send(context, chat_id, status_message_id, url, lang, as_audio, offer_extras=False):
    loop = asyncio.get_running_loop()
    file_path = None
    outtmpl = f"dl_{uuid.uuid4().hex[:8]}.%(ext)s"

    opts = base_ydl_opts()
    opts['outtmpl'] = outtmpl
    opts['max_filesize'] = MAX_FILE_SIZE_MB * 1024 * 1024

    if status_message_id:
        opts['progress_hooks'] = [
            make_progress_hook(loop, context.bot, chat_id, status_message_id, lang)
        ]

    if as_audio:
        opts['format'] = 'bestaudio/best'
        opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else:
        opts['format'] = 'best'

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
            file_path = ydl.prepare_filename(info)
            if as_audio:
                base, _ = os.path.splitext(file_path)
                mp3_path = base + ".mp3"
                if os.path.exists(mp3_path):
                    file_path = mp3_path

        if not os.path.exists(file_path):
            raise FileNotFoundError("Fayl topilmadi")

        if status_message_id:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=status_message_id)
            except Exception:
                pass

        title = info.get('title', 'Media')
        with open(file_path, 'rb') as f:
            if as_audio:
                await context.bot.send_audio(
                    chat_id=chat_id, audio=f, title=title,
                    caption=t(lang, "audio_caption", title=title), parse_mode="Markdown"
                )
            else:
                await context.bot.send_video(
                    chat_id=chat_id, video=f,
                    caption=t(lang, "video_caption"), parse_mode="Markdown"
                )

        # FAQAT Video yuborilgach MP3 SO'RALADI:
        if offer_extras and not as_audio:
            token = uuid.uuid4().hex[:10]
            pending_downloads[token] = {
                "url": url,
                "chat_id": chat_id,
                "description": (info.get('description') or '').strip(),
            }
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
        err_text = t(lang, "error_generic")
        await context.bot.send_message(chat_id, err_text, parse_mode="Markdown")
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)


async def on_music_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = db_get_lang(update.effective_user.id)

    _, token, choice = query.data.split(":")
    data = pending_downloads.get(token)
    if not data:
        await query.edit_message_text(t(lang, "session_expired"), parse_mode="Markdown")
        return

    if choice == "yes":
        await query.edit_message_text(t(lang, "downloading", percent=""), parse_mode="Markdown")
        await download_and_send(
            context=context,
            chat_id=data["chat_id"],
            status_message_id=query.message.message_id,
            url=data["url"],
            lang=lang,
            as_audio=True,
            offer_extras=False,
        )
    else:
        try:
            await query.delete_message()
        except Exception:
            pass

    # MP3 ga javob berilgach, Tavsif haqida so'raymiz:
    keyboard = [[
        InlineKeyboardButton(t(lang, "btn_yes"), callback_data=f"desc:{token}:yes"),
        InlineKeyboardButton(t(lang, "btn_no"), callback_data=f"desc:{token}:no"),
    ]]
    await context.bot.send_message(
        chat_id=data["chat_id"],
        text=t(lang, "ask_description"),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def on_description_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = db_get_lang(update.effective_user.id)

    _, token, choice = query.data.split(":")
    data = pending_downloads.pop(token, None)
    if not data:
        await query.edit_message_text(t(lang, "session_expired"), parse_mode="Markdown")
        return

    if choice == "yes":
        description = data.get("description") or ""
        if description:
            description = description[:4000]
            header = {"uz": "📝 Tavsif:", "ru": "📝 Описание:", "en": "📝 Description:"}.get(lang, "📝 Tavsif:")
            await query.edit_message_text(f"{header}\n\n{description}")
        else:
            await query.edit_message_text(t(lang, "no_description"), parse_mode="Markdown")
    else:
        try:
            await query.delete_message()
        except Exception:
            pass


async def handle_music_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query_text: str, lang: str):
    msg = await update.message.reply_text(t(lang, "searching_music", query=query_text), parse_mode="Markdown")
    loop = asyncio.get_running_loop()

    opts = base_ydl_opts()
    opts['format'] = 'bestaudio/best'
    opts['postprocessors'] = [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }]

    try:
        with yt_dlp.YoutubeDL({**opts, 'quiet': True}) as ydl_search:
            search_info = await loop.run_in_executor(
                None, lambda: ydl_search.extract_info(f"ytsearch5:{query_text}", download=False)
            )
        candidates = search_info.get('entries', []) if search_info else []
    except Exception:
        candidates = []

    if not candidates:
        await msg.edit_text(t(lang, "music_not_found"), parse_mode="Markdown")
        return

    for entry in candidates:
        if not entry:
            continue
        video_url = entry.get('webpage_url') or entry.get('url') or entry.get('id')
        outtmpl = f"song_{uuid.uuid4().hex[:8]}.%(ext)s"
        file_path = None
        try:
            song_opts = {**opts, 'outtmpl': outtmpl, 'max_filesize': MAX_FILE_SIZE_MB * 1024 * 1024}
            with yt_dlp.YoutubeDL(song_opts) as ydl:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(video_url, download=True))
                file_path = ydl.prepare_filename(info)
                base, _ = os.path.splitext(file_path)
                mp3_path = base + ".mp3"
                if os.path.exists(mp3_path):
                    file_path = mp3_path

            if not os.path.exists(file_path):
                raise FileNotFoundError("Fayl topilmadi")

            title = info.get('title', query_text)
            with open(file_path, 'rb') as f:
                await update.message.reply_audio(
                    audio=f, title=title,
                    caption=t(lang, "audio_caption", title=title), parse_mode="Markdown"
                )
            await msg.delete()
            return
        except Exception:
            continue
        finally:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)

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
    app.add_handler(CallbackQueryHandler(on_quality_chosen, pattern=r"^q:"))
    app.add_handler(CallbackQueryHandler(on_music_choice, pattern=r"^music:"))
    app.add_handler(CallbackQueryHandler(on_description_choice, pattern=r"^desc:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot ishga tushdi...")
    app.run_polling()


if __name__ == "__main__":
    main()
