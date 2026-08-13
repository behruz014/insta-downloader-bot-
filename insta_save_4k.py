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

# Render platformasi to'xtab qolmasligi uchun HTTP server
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Active")

def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

BOT_TOKEN = "8387237045:AAFbN2d1JkZhj3Cak2SsQF5ob7paRbb2iDs"
ADMIN_ID = None  # Xohlasangiz Telegram ID'ingizni yozing

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

# /start xabari (Chiroyli dizayn)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)
    
    welcome_text = (
        "✨ **InstaSave Botiga xush kelibsiz!** ✨\n\n"
        "Men sizga sevimli va qiziqarli medialaringizni bir necha soniyada yuklab beraman! 🚀\n\n"
        "📌 **Imkoniyatlarim:**\n"
        "🎬 **Instagram / TikTok / YouTube:** Video havolasini yuboring.\n"
        "🎵 **Videodan audio:** Link yuborib, MP3 formatida ajratib oling.\n"
        "🔍 **Musiqa qidiruv:** Qo'shiq nomi yoki xonandani yozing.\n\n"
        "👇 *Boshlash uchun havola yoki qo'shiq nomini yozib yuboring!*"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

# Admin panel
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if ADMIN_ID and user_id != ADMIN_ID:
        await update.message.reply_text("❌ *Faqat admin uchun!*", parse_mode="Markdown")
        return

    users = load_users()
    await update.message.reply_text(
        f"📊 **Admin Panel**\n\n"
        f"👥 Jami foydalanuvchilar: **{len(users)}** ta\n\n"
        f"📢 Xabar yuborish: `/broadcast Xabar matni`",
        parse_mode="Markdown"
    )

# Xabar tarqatish (Broadcast)
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if ADMIN_ID and user_id != ADMIN_ID:
        return

    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("⚠️ Ishlatish: `/broadcast Xabar matni`", parse_mode="Markdown")
        return

    users = load_users()
    count = 0
    for uid in users:
        try:
            await context.bot.send_message(chat_id=uid, text=text)
            count += 1
        except Exception:
            pass

    await update.message.reply_text(f"✅ Xabar **{count}** ta foydalanuvchiga yuborildi.", parse_mode="Markdown")

# Xabarlarni qabul qilish
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)

    text = update.message.text.strip()
    supported = ["instagram.com", "tiktok.com", "youtube.com", "youtu.be"]

    # Havola yuborilganda
    if any(domain in text for domain in supported):
        keyboard = [
            [
                InlineKeyboardButton("📹 Videoni yuklash (HD)", callback_data=f"video|{text}"),
                InlineKeyboardButton("🎵 Audioni yuklash (MP3)", callback_data=f"audio|{text}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("⚡ **Nimani yuklab olmoqchisiz?**", reply_markup=reply_markup, parse_mode="Markdown")

    # Qo'shiq nomi bo'lganda
    else:
        msg = await update.message.reply_text(f"🔍 **«{text}»** musiqasi qidirilmoqda, bir oz kuting...", parse_mode="Markdown")
        file_path = None
        try:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': 'song_%(id)s.%(ext)s',
                'quiet': True,
                'no_warnings': True,
                'default_search': 'ytsearch1',
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(text, download=True)
                if 'entries' in info and len(info['entries']) > 0:
                    video_info = info['entries'][0]
                else:
                    video_info = info
                
                title = video_info.get('title', 'Musiqa')
                file_path = ydl.prepare_filename(video_info)

            with open(file_path, 'rb') as audio_file:
                await update.message.reply_audio(
                    audio=audio_file, 
                    title=title, 
                    caption=f"🎧 **{title}**\n\n🤖 @InstaSaveBot orqali yuklandi",
                    parse_mode="Markdown"
                )
            await msg.delete()

        except Exception as e:
            logging.error(f"Xatolik: {e}")
            await msg.edit_text("❌ *Musiqa topilmadi yoki yuklab bo'lmadi. Qayta urinib ko'ring.*", parse_mode="Markdown")

        finally:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)

# Tugmalar bosilganda
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split("|", 1)
    download_type = data[0]
    url = data[1]

    msg = await query.message.edit_text("⏳ *Fayl yuklanmoqda va tayyorlanmoqda...*", parse_mode="Markdown")

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
                await query.message.reply_video(
                    video=video_file, 
                    caption="✅ *Video muvaffaqiyatli yuklab olindi!*\n\n🤖 @InstaSaveBot",
                    parse_mode="Markdown"
                )

        elif download_type == "audio":
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': 'download_%(id)s.%(ext)s',
                'quiet': True,
                'no_warnings': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file_path = ydl.prepare_filename(info)

            with open(file_path, 'rb') as audio_file:
                await query.message.reply_audio(
                    audio=audio_file, 
                    caption="🎵 *Audio muvaffaqiyatli yuklab olindi!*\n\n🤖 @InstaSaveBot",
                    parse_mode="Markdown"
                )

        await msg.delete()

    except Exception as e:
        logging.error(f"Xatolik: {e}")
        await msg.edit_text("❌ *Xatolik yuz berdi. Havola to'g'riligini yoki profil ochiqligini tekshiring.*", parse_mode="Markdown")

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
