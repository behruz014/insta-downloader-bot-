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
# XAVFSIZLIK: Token va parol kodda emas, environment variable'dan olinadi.
# Render.com -> Dashboard -> Environment -> qo'shing:
#   BOT_TOKEN = <8387237045:AAFbN2d1JkZhj3Cak2SsQF5ob7paRbb2iDs>
#   ADMIN_PASSWORD = <behruz700>
# ============================================================================
BOT_TOKEN = os.environ.get("8387237045:AAFbN2d1JkZhj3Cak2SsQF5ob7paRbb2iDs")
ADMIN_PASSWORD = os.environ.get("behruz700")

if not BOT_TOKEN or not ADMIN_PASSWORD:
    raise RuntimeError(
        "BOT_TOKEN yoki ADMIN_PASSWORD environment variable topilmadi. "
        "Render Dashboard -> Environment bo'limida sozlang."
    )

DB_FILE = "bot.db"
MAX_FILE_SIZE_MB = 50          # Render bepul tarifida disk cheklangan
PLAYLIST_LIMIT = 5             # Playlistdan bir martada yuklanadigan max video soni
PROGRESS_UPDATE_INTERVAL = 3   # sekund - progress xabari qancha tez-tez yangilanadi

# Har bir foydalanuvchi uchun "hozir nima yuklayapti" ma'lumotini vaqtincha saqlash
# token -> {"url": str, "info": dict, "chat_id": int}
pending_downloads = {}


# ============================================================================
# TILLAR (UZ / RU / EN) - chiroyli va izchil matnlar
# ============================================================================
TEXTS = {
    "uz": {
        "choose_lang": "🌐 Tilni tanlang / Choose language / Выберите язык",
        "welcome": (
            "✨ *InstaSave Botiga xush kelibsiz!* ✨\n\n"
            "Men sizga sevimli medialaringizni bir necha soniyada yuklab beraman 🚀\n\n"
            "📌 *Imkoniyatlarim:*\n"
            "🎬 Instagram / TikTok / YouTube — link yuboring\n"
            "🎵 Qo'shiq nomini yozing — men qidirib topaman\n"
            "📃 YouTube playlist ham qo'llab-quvvatlanadi\n\n"
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
        "error_toolarge": "❌ Fayl juda katta (limit: {limit}MB). Boshqa media sinab ko'ring.",
        "searching_music": "🔍 «{query}» qidirilmoqda...",
        "music_not_found": "❌ Bu nom bo'yicha musiqa topilmadi. Boshqacha nom bilan qayta urinib ko'ring.",
        "playlist_found": "📃 Playlist topildi: *{count} ta* video.\nBirinchi *{limit} ta* videoni yuklaymi?",
        "btn_playlist_yes": "✅ Ha, yuklash",
        "btn_playlist_no": "❌ Yo'q",
        "playlist_progress": "⏳ Playlist yuklanmoqda: {done}/{total}",
        "playlist_done": "✅ Playlist tugadi! {done}/{total} video yuborildi.",
        "admin_denied": "❌ Siz uchun bu bo'lim taqiqlangan!",
        "admin_panel": "📊 *Admin Panel*\n\n👥 Jami foydalanuvchilar: *{count}* ta\n\n📢 Xabar: `/broadcast <parol> Xabar matni`",
        "broadcast_empty": "⚠️ Xabar matnini yozing!",
        "broadcast_done": "✅ Xabar *{count}* ta foydalanuvchiga yuborildi.",
        "session_expired": "⚠️ Sessiya eskirgan, havolani qayta yuboring.",
        "ask_music": "🎵 Videoning musiqasini alohida (MP3) yuboraymi?",
        "ask_description": "📝 Video tavsifini (opisaniyasini) ham yuboraymi?",
        "btn_yes": "✅ Ha",
        "btn_no": "❌ Yo'q",
        "no_description": "ℹ️ Bu video uchun tavsif topilmadi.",
        "description_caption": "📝 *Tavsif:*\n\n{description}",
        "extra_error": "❌ Bu qismini yuklab bo'lmadi.",
        "no_thanks": "👍 Yaxshi, davom eting!",
    },
    "ru": {
        "choose_lang": "🌐 Tilni tanlang / Choose language / Выберите язык",
        "welcome": (
            "✨ *Добро пожаловать в InstaSave Bot!* ✨\n\n"
            "Я скачаю ваши любимые медиа за пару секунд 🚀\n\n"
            "📌 *Возможности:*\n"
            "🎬 Instagram / TikTok / YouTube — отправьте ссылку\n"
            "🎵 Название песни — я найду её сам\n"
            "📃 Поддержка YouTube-плейлистов\n\n"
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
        "error_generic": "❌ Не удалось скачать. Проверьте ссылку или медиа закрыто/заблокировано.",
        "error_toolarge": "❌ Файл слишком большой (лимит: {limit}MB). Попробуйте другой.",
        "searching_music": "🔍 Ищу «{query}»...",
        "music_not_found": "❌ Музыка не найдена. Попробуйте другое название.",
        "playlist_found": "📃 Найден плейлист: *{count}* видео.\nСкачать первые *{limit}*?",
        "btn_playlist_yes": "✅ Да, скачать",
        "btn_playlist_no": "❌ Нет",
        "playlist_progress": "⏳ Загрузка плейлиста: {done}/{total}",
        "playlist_done": "✅ Готово! Отправлено {done}/{total} видео.",
        "admin_denied": "❌ Доступ запрещён!",
        "admin_panel": "📊 *Админ-панель*\n\n👥 Всего пользователей: *{count}*\n\n📢 Рассылка: `/broadcast <пароль> текст`",
        "broadcast_empty": "⚠️ Введите текст сообщения!",
        "broadcast_done": "✅ Сообщение отправлено *{count}* пользователям.",
        "session_expired": "⚠️ Сессия устарела, отправьте ссылку заново.",
        "ask_music": "🎵 Отправить музыку из видео отдельно (MP3)?",
        "ask_description": "📝 Отправить описание видео?",
        "btn_yes": "✅ Да",
        "btn_no": "❌ Нет",
        "no_description": "ℹ️ Описание для этого видео не найдено.",
        "description_caption": "📝 *Описание:*\n\n{description}",
        "extra_error": "❌ Не удалось загрузить эту часть.",
        "no_thanks": "👍 Хорошо, продолжаем!",
    },
    "en": {
        "choose_lang": "🌐 Tilni tanlang / Choose language / Выберите язык",
        "welcome": (
            "✨ *Welcome to InstaSave Bot!* ✨\n\n"
            "I'll download your favorite media in seconds 🚀\n\n"
            "📌 *What I can do:*\n"
            "🎬 Instagram / TikTok / YouTube — send a link\n"
            "🎵 Song name — I'll find and send it\n"
            "📃 YouTube playlists supported\n\n"
            "👇 Send a link or a song name to start!"
        ),
        "analyzing": "🔎 Checking the link...",
        "choose_quality": "🎯 *{title}*\n\nWhich format would you like?",
        "btn_video_best": "🎥 Video (best quality)",
        "btn_audio_only": "🎵 Audio only (MP3)",
        "btn_cancel": "❌ Cancel",
        "cancelled": "❌ Cancelled.",
        "downloading": "⏳ Downloading... {percent}",
        "converting": "🔄 Preparing file...",
        "video_caption": "✅ *Video ready!*\n\n🤖 @InstaSaveBot",
        "audio_caption": "🎧 *{title}*\n\n🤖 @InstaSaveBot",
        "error_generic": "❌ Couldn't download. Check the link or the media may be private/blocked.",
        "error_toolarge": "❌ File too large (limit: {limit}MB). Try something else.",
        "searching_music": "🔍 Searching for «{query}»...",
        "music_not_found": "❌ No music found for that name. Try a different search.",
        "playlist_found": "📃 Playlist found: *{count}* videos.\nDownload the first *{limit}*?",
        "btn_playlist_yes": "✅ Yes, download",
        "btn_playlist_no": "❌ No",
        "playlist_progress": "⏳ Downloading playlist: {done}/{total}",
        "playlist_done": "✅ Done! Sent {done}/{total} videos.",
        "admin_denied": "❌ Access denied!",
        "admin_panel": "📊 *Admin Panel*\n\n👥 Total users: *{count}*\n\n📢 Broadcast: `/broadcast <password> message`",
        "broadcast_empty": "⚠️ Enter a message!",
        "broadcast_done": "✅ Message sent to *{count}* users.",
        "session_expired": "⚠️ Session expired, please send the link again.",
        "ask_music": "🎵 Send the video's music separately (MP3)?",
        "ask_description": "📝 Send the video description too?",
        "btn_yes": "✅ Yes",
        "btn_no": "❌ No",
        "no_description": "ℹ️ No description found for this video.",
        "description_caption": "📝 *Description:*\n\n{description}",
        "extra_error": "❌ Couldn't fetch that part.",
        "no_thanks": "👍 Great, carry on!",
    },
}


def t(lang, key, **kwargs):
    text = TEXTS.get(lang, TEXTS["uz"]).get(key, key)
    return text.format(**kwargs) if kwargs else text


# ============================================================================
# MA'LUMOTLAR BAZASI (SQLite) - users.json o'rniga
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
# RENDER "SLEEP" REJIMIGA O'TIB QOLMASLIGI UCHUN HEALTH-CHECK SERVER
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
# YORDAMCHI: yt-dlp sozlamalari
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
    # Instagram/TikTok bloklay boshlasa, brauzerdan eksport qilingan
    # cookies.txt faylini shu papkaga qo'ying - avtomatik ishlatiladi.
    if os.path.exists("cookies.txt"):
        opts['cookiefile'] = "cookies.txt"
    return opts


def make_progress_hook(loop, bot, chat_id, message_id, lang):
    """Yuklash jarayonini foydalanuvchiga real vaqtda ko'rsatish uchun hook."""
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
                pass  # xabar o'zgarmagan yoki eskirgan bo'lsa e'tibor bermaymiz

        asyncio.run_coroutine_threadsafe(edit(), loop)

    return hook


# ============================================================================
# /start - TIL TANLASH
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


# ============================================================================
# ADMIN PANEL
# ============================================================================
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
            await asyncio.sleep(0.05)  # Telegram flood-limit'ga tushmaslik uchun
        except Exception:
            pass

    await update.message.reply_text(t(lang, "broadcast_done", count=count), parse_mode="Markdown")


# ============================================================================
# LINK YUBORILGANDA: avval tahlil, keyin format tanlash tugmalari
# ============================================================================
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

    # Playlist bo'lsa - tasdiq so'raymiz
    if info.get('_type') == 'playlist' or (info.get('entries') and len(list(info.get('entries', []))) > 1):
        entries = list(info.get('entries', []))
        token = uuid.uuid4().hex[:10]
        pending_downloads[token] = {"url": url, "chat_id": update.effective_chat.id, "entries": entries}
        keyboard = [[
            InlineKeyboardButton(t(lang, "btn_playlist_yes"), callback_data=f"pl:{token}:yes"),
            InlineKeyboardButton(t(lang, "btn_playlist_no"), callback_data=f"pl:{token}:no"),
        ]]
        await msg.edit_text(
            t(lang, "playlist_found", count=len(entries), limit=PLAYLIST_LIMIT),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Oddiy video - format tanlash tugmalari
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
        pass  # xato xabari download_and_send ichida allaqachon yuborilgan


async def on_playlist_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = db_get_lang(update.effective_user.id)

    _, token, choice = query.data.split(":")
    data = pending_downloads.pop(token, None)
    if not data:
        await query.edit_message_text(t(lang, "session_expired"), parse_mode="Markdown")
        return

    if choice == "no":
        await query.edit_message_text(t(lang, "cancelled"), parse_mode="Markdown")
        return

    entries = data["entries"][:PLAYLIST_LIMIT]
    chat_id = data["chat_id"]
    total = len(entries)
    done = 0

    await query.edit_message_text(t(lang, "playlist_progress", done=0, total=total), parse_mode="Markdown")

    for entry in entries:
        video_url = entry.get('webpage_url') or entry.get('url')
        if not video_url:
            continue
        try:
            await download_and_send(
                context=context,
                chat_id=chat_id,
                status_message_id=None,
                url=video_url,
                lang=lang,
                as_audio=False,
            )
            done += 1
        except Exception as e:
            logger.error(f"Playlist elementi xatoligi: {e}")
        try:
            await query.edit_message_text(
                t(lang, "playlist_progress", done=done, total=total), parse_mode="Markdown"
            )
        except Exception:
            pass

    await context.bot.send_message(chat_id, t(lang, "playlist_done", done=done, total=total), parse_mode="Markdown")


async def on_music_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Video yuborilgandan keyin: 'musiqasini alohida yuboraymi?' javobi."""
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
        try:
            await download_and_send(
                context=context,
                chat_id=data["chat_id"],
                status_message_id=query.message.message_id,
                url=data["url"],
                lang=lang,
                as_audio=True,
                offer_extras=False,
            )
        except Exception:
            pass  # xato xabari download_and_send ichida allaqachon yuborilgan
    else:
        try:
            await query.delete_message()
        except Exception:
            pass

    # Endi tavsif haqida so'raymiz (token hali ham pending_downloads'da)
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
    """'Tavsifini yuboraymi?' javobi - shu bilan sessiya yakunlanadi."""
    query = update.callback_query
    await query.answer()
    lang = db_get_lang(update.effective_user.id)

    _, token, choice = query.data.split(":")
    data = pending_downloads.pop(token, None)  # sessiya shu yerda tugaydi
    if not data:
        await query.edit_message_text(t(lang, "session_expired"), parse_mode="Markdown")
        return

    if choice == "yes":
        description = data.get("description") or ""
        if description:
            # Telegram xabar limiti ~4096 belgi; tavsif matnida Markdown belgilari
            # bo'lishi mumkin bo'lgani uchun parse_mode ishlatmaymiz (xato bo'lmasligi uchun)
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


async def download_and_send(context, chat_id, status_message_id, url, lang, as_audio, offer_extras=False):
    """Bitta video/audioni yuklab, foydalanuvchiga yuboradi."""
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
                # FFmpegExtractAudio kengaytmani .mp3 ga o'zgartiradi
                base, _ = os.path.splitext(file_path)
                mp3_path = base + ".mp3"
                if os.path.exists(mp3_path):
                    file_path = mp3_path

        if not os.path.exists(file_path):
            raise FileNotFoundError("Fayl topilmadi")

        if status_message_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=status_message_id,
                    text=t(lang, "converting"), parse_mode="Markdown"
                )
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

        if status_message_id:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=status_message_id)
            except Exception:
                pass

        # Video muvaffaqiyatli yuborilgandan keyin - musiqa va tavsif haqida so'raymiz
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

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"Yuklash xatoligi: {e}")
        err_text = t(lang, "error_toolarge", limit=MAX_FILE_SIZE_MB) if "max-filesize" in str(e).lower() or "larger" in str(e).lower() else t(lang, "error_generic")
        if status_message_id:
            try:
                await context.bot.edit_message_text(chat_id=chat_id, message_id=status_message_id, text=err_text, parse_mode="Markdown")
            except Exception:
                await context.bot.send_message(chat_id, err_text, parse_mode="Markdown")
        else:
            await context.bot.send_message(chat_id, err_text, parse_mode="Markdown")
        raise
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)


# ============================================================================
# QO'SHIQ QIDIRISH - bir nechta natijani sinab, birinchisi ishlagunini topadi
# (avvalgi versiyada faqat 1 ta natija sinalgani uchun ko'p hollarda "topilmadi"
#  deb chiqib ketardi - shu yerda tuzatildi)
# ============================================================================
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
    except Exception as e:
        logger.error(f"Qidiruv xatoligi: {e}")
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
            return  # muvaffaqiyatli - to'xtaymiz

        except Exception as e:
            logger.warning(f"Nomzod ishlamadi ({video_url}): {e}")
            continue  # keyingi nomzodni sinaymiz
        finally:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)

    # Barcha nomzodlar ishlamadi
    await msg.edit_text(t(lang, "music_not_found"), parse_mode="Markdown")


# ============================================================================
# UMUMIY XABAR ROUTER
# ============================================================================
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


# ============================================================================
# MAIN
# ============================================================================
def main():
    db_init()
    Thread(target=run_health_check_server, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CallbackQueryHandler(on_language_chosen, pattern=r"^lang:"))
    app.add_handler(CallbackQueryHandler(on_quality_chosen, pattern=r"^q:"))
    app.add_handler(CallbackQueryHandler(on_playlist_choice, pattern=r"^pl:"))
    app.add_handler(CallbackQueryHandler(on_music_choice, pattern=r"^music:"))
    app.add_handler(CallbackQueryHandler(on_description_choice, pattern=r"^desc:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot ishga tushdi...")
    app.run_polling()


if __name__ == "__main__":
    main()
