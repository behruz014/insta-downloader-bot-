import os
import logging
import json
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)
import yt_dlp

# Log sozlamalari
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Render platformasida xizmat to'xtab qolmasligi uchun HTTP server
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot ishlamoqda!")

def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# Bot API Token va Admin ID
BOT_TOKEN = "8387237045:AAFbN2d1JkZhj3Cak2SsQF5ob7paRbb2iDs"
ADMIN_ID = None  # Admin sifatida o'zingizning Telegram ID'ingizni qo'shishingiz mumkin (masalan: 123456789)

# Foydalanuvchilarni saqlash fayli
USERS_FILE = "users.json"

def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_user(user_id):
    users = load_users()
    if user_id not in users:
        users.add(user_id)
        with open(USERS_FILE, "w") as f:
            json.dump(list(users), f)

# /start komandasi
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)
    
    welcome_text = (
        "Salom! Men mukammal media va musiqa yuklovchi botman. 🚀\n\n"
        "📹 **Video va Rasmlar:** Instagram, TikTok yoki YouTube havolasini yuboring.\n"
        "🎵 **Musiqa qidirish:** Qo'shiq nomini yoki xonandani yozib yuboring!\n\n"
        "⚙️ **Boshqaruv:** /admin - Admin panel (faqat admin uchun)"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

# Admin Panel (/admin)
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if ADMIN_ID and user_id != ADMIN_ID:
        await update.message.reply_text("❌ Bu komanda faqat admin uchun!")
        return

    users = load_users()
    keyboard = [
        [InlineKeyboardButton("📢 Xabar yuborish (Rassilka)", callback_data="broadcast_info")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"📊 **Admin Panel**\n\n"
        f"👥 Jami foydalanuvchilar: **{len(users)}** ta\n\n"
        f"Xabar yuborish uchun `/broadcast <xabar>` komandasidan foydalaning.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# /broadcast komandasi
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if ADMIN_ID and user_id != ADMIN_ID:
        return

    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("Xato! Ishlatish: `/broadcast Xabar matni`", parse_mode="Markdown")
        return

    users = load_users()
    count = 0
    for uid in users:
        try:
            await context.bot.send_message(chat_id=uid, text=text)
            count += 1
        except Exception:
            pass

    await update.message.reply_text(f"✅ Xabar **{count}** ta foydalanuvchiga yetkazildi.", parse_mode="Markdown")

# Xabarlarni qayta ishlash
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)

    text = update.message.text.strip()
    supported = ["instagram.com", "tiktok.com", "youtube.com", "youtu.be"]

    # Havola bo'lsa
    if any(domain in text for domain in supported):
        keyboard = [
            [
                InlineKeyboardButton("📹 Video (Maksimal sifat)", callback_data=f"video|{text}"),
                InlineKeyboardButton("🎵 MP3 (Audio)", callback_data=f"audio|{text}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Yuklash turini tanlang:", reply_markup=reply_markup)

    # Qidiruv bo'lsa
    else:
        msg = await update.message.reply_text(f"🔍 **\"{text}\"** bo'yicha musiqa qidirilmoqda...", parse_mode="Markdown")
        file_path = None
        try:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': 'song_%(id)s.%(ext)s',
                'quiet': True,
                'no_warnings': True,
                'default_search': 'ytsearch1',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(text, download=True)
                if 'entries' in info and len(info['entries']) > 0:
                    video_info = info['entries'][0]
                else:
                    video_info = info
                
                title = video_info.get('title', 'Musiqa')
                file_path = f"song_{video_info['id']}.mp3"

            with open(file_path, 'rb') as audio_file:
                await update.message.reply_audio(
                    audio=audio_file,
                    title=title,
                    caption=f"✅ **{title}**",
                    parse_mode="Markdown"
                )
            await msg.delete()

        except Exception as e:
            logging.error(f"Qidiruvda xatolik: {e}")
            await msg.edit_text("❌ Musiqa topilmadi. Qayta urinib ko'ring.")

        finally:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)

# Callback tugmalar
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "broadcast_info":
        await query.message.reply_text("Barcha obunachilarga xabar yuborish uchun `/broadcast <xabar_matni>` deb yuboring.")
        return

    data = query.data.split("|", 1)
    download_type = data[0]
    url = data[1]

    msg = await query.message.edit_text("⏳ Yuklanmoqda, kuting...")

    file_path = None
    try:
        if download_type == "video":
            ydl_opts = {
                'format': 'bestvideo+bestaudio/best',
                'merge_output_format': 'mp4',
                'outtmpl': 'download_%(id)s.%(ext)s',
                'quiet': True,
                'no_warnings': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file_path = ydl.prepare_filename(info)

            with open(file_path, 'rb') as video_file:
                await query.message.reply_video(video=video_file, caption="✅ Video yuklab olindi!")

        elif download_type == "audio":
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': 'download_%(id)s.%(ext)s',
                'quiet': True,
                'no_warnings': True,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file_path = f"download_{info['id']}.mp3"

            with open(file_path, 'rb') as audio_file:
                await query.message.reply_audio(audio=audio_file, caption="🎵 Audiosi (MP3) yuklab olindi!")

        await msg.delete()

    except Exception as e:
        logging.error(f"Xatolik: {e}")
        await msg.edit_text("❌ Yuklab bo'lmadi. Havolani qayta tekshirib ko'ring.")

    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

def main():
    Thread(target=run_health_check_server, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))

    print("Bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()
