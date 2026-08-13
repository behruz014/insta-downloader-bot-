import os
import logging
import json
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)
import yt_dlp

# Log sozlamalari
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Render platformasi uchib qolmasligi uchun HTTP server
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
ADMIN_PASSWORD = "behruz700"
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

# /start xabari
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)

    welcome_text = (
        "✨ **InstaSave Botiga xush kelibsiz!** ✨\n\n"
        "Men sizga sevimli va qiziqarli medialaringizni bir necha soniyada yuklab beraman! 🚀\n\n"
        "📌 **Imkoniyatlarim:**\n"
        "🎬 **Instagram / TikTok / YouTube:** Link yuboring, avtomatik yuklab beraman!\n"
        "🔍 **Musiqa qidiruv:** Qo'shiq nomini yoki xonandani yozing.\n\n"
        "👇 *Boshlash uchun havola yoki qo'shiq nomini yozib yuboring!*"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

# Admin panel
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args or args[0] != ADMIN_PASSWORD:
        await update.message.reply_text("❌ *Siz uchun bu bo'lim taqiqlangan!*", parse_mode="Markdown")
        return

    users = load_users()
    await update.message.reply_text(
        f"📊 **Admin Panel**\n\n"
        f"👥 Jami foydalanuvchilar: **{len(users)}** ta\n\n"
        f"📢 Xabar yuborish: `/broadcast behruz700 Xabar matni`",
        parse_mode="Markdown"
    )

# Broadcast
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args or args[0] != ADMIN_PASSWORD:
        await update.message.reply_text("❌ *Buyruq noto'g'ri!*", parse_mode="Markdown")
        return

    text = " ".join(args[1:])
    if not text:
        await update.message.reply_text("⚠️ Xabar matnini yozing!", parse_mode="Markdown")
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

    # Link kelganda (Video yuklash)
    if any(domain in text for domain in supported):
        msg = await update.message.reply_text("⏳ *Media yuklanmoqda, kuting...*", parse_mode="Markdown")
        video_file_path = None
        
        try:
            ydl_opts = {
                'format': 'best',
                'outtmpl': 'download_%(id)s.%(ext)s',
                'quiet': True,
                'no_warnings': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
            }
            if os.path.exists("cookies.txt"):
                ydl_opts['cookiefile'] = "cookies.txt"

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(text, download=True)
                video_file_path = ydl.prepare_filename(info)

            with open(video_file_path, 'rb') as video_file:
                await update.message.reply_video(
                    video=video_file, 
                    caption="✅ *Video yuklab olindi!*\n\n🤖 @InstaSaveBot",
                    parse_mode="Markdown"
                )
            await msg.delete()

        except Exception as e:
            logging.error(f"Xatolik: {e}")
            await msg.edit_text("❌ *Yuklab bo'lmadi. Linkni tekshiring yoki video yopiq/bloklangan.*", parse_mode="Markdown")

        finally:
            if video_file_path and os.path.exists(video_file_path):
                os.remove(video_file_path)

    # Qo'shiq nomi kelganda (Musiqa qidiruv)
    else:
        msg = await update.message.reply_text(f"🔍 **«{text}»** musiqasi qidirilmoqda...", parse_mode="Markdown")
        file_path = None
        try:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': 'song_%(id)s.%(ext)s',
                'quiet': True,
                'no_warnings': True,
                'default_search': 'ytsearch1:',
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch1:{text}", download=True)
                if 'entries' in info and len(info['entries']) > 0:
                    video_info = info['entries'][0]
                else:
                    video_info = info
                
                title = video_info.get('title', text)
                file_path = ydl.prepare_filename(video_info)

            with open(file_path, 'rb') as audio_file:
                await update.message.reply_audio(
                    audio=audio_file, 
                    title=title, 
                    caption=f"🎧 **{title}**\n\n🤖 @InstaSaveBot",
                    parse_mode="Markdown"
                )
            await msg.delete()

        except Exception as e:
            logging.error(f"Musiqa xatoligi: {e}")
            await msg.edit_text("❌ *Musiqa topilmadi. Boshqacha nom bilan qidirib ko'ring.*", parse_mode="Markdown")

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

    print("Bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()
