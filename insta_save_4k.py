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

# Server "uxlab qolmasligi" uchun
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Active")

def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# YANI TOKENINGIZNI SHU YERGA YOZING:
BOT_TOKEN = "YANGI_TOKENINGIZNI_SHU_YERGA_YOZING"
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

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)
    await update.message.reply_text("✨ InstaSave Botiga xush kelibsiz! Link yoki qo'shiq nomini yuboring.", parse_mode="Markdown")

# /admin behruz700
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args or args[0] != ADMIN_PASSWORD:
        await update.message.reply_text("❌ Taqiqlangan!", parse_mode="Markdown")
        return
    users = load_users()
    await update.message.reply_text(f"📊 Jami foydalanuvchilar: **{len(users)}** ta", parse_mode="Markdown")

# /broadcast behruz700 Xabar
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args or args[0] != ADMIN_PASSWORD: return
    text = " ".join(args[1:])
    if not text: return
    users = load_users()
    for uid in users:
        try: await context.bot.send_message(chat_id=uid, text=text)
        except: pass
    await update.message.reply_text("✅ Xabar yuborildi.")

# Asosiy funksiya
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_user.id)
    text = update.message.text.strip()
    supported = ["instagram.com", "tiktok.com", "youtube.com", "youtu.be"]

    # Video yuklash
    if any(domain in text for domain in supported):
        msg = await update.message.reply_text("⏳ Yuklanmoqda...")
        video_file_path = None
        try:
            ydl_opts = {
                'format': 'best',
                'outtmpl': 'download_%(id)s.%(ext)s',
                'quiet': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(text, download=True)
                video_file_path = ydl.prepare_filename(info)
            with open(video_file_path, 'rb') as video_file:
                await update.message.reply_video(video=video_file)
            await msg.delete()
        except Exception as e:
            await msg.edit_text("❌ Xatolik yuz berdi.")
        finally:
            if video_file_path and os.path.exists(video_file_path): os.remove(video_file_path)
    
    # Musiqa qidirish
    else:
        msg = await update.message.reply_text(f"🔍 «{text}» qidirilmoqda...")
        file_path = None
        try:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': 'song_%(id)s.%(ext)s',
                'quiet': True,
                'default_search': 'ytsearch1:',
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch1:{text}", download=True)
                file_path = ydl.prepare_filename(info['entries'][0])
            with open(file_path, 'rb') as audio_file:
                await update.message.reply_audio(audio=audio_file)
            await msg.delete()
        except:
            await msg.edit_text("❌ Musiqa topilmadi.")
        finally:
            if file_path and os.path.exists(file_path): os.remove(file_path)

def main():
    Thread(target=run_health_check_server, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
