import os
import logging
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

# Loglarni sozlash
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Render platformasida Web Service statusi xato bermasligi uchun oddiy server
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot ishlamoqda!")

def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# Sizning Telegram Bot Tokeningiz
BOT_TOKEN = "8387237045:AAFbN2d1JkZhj3Cak2SsQF5ob7paRbb2iDs"

# /start komandasi uchun
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Salom! Men Instagram videolarini yuklab beruvchi botman. 🚀\n\n"
        "Menga Instagram Reel yoki video havolasini yuboring!"
    )

# Videoni yuklash va Telegram'ga yuborish
async def download_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    
    if "instagram.com" not in url:
        return

    msg = await update.message.reply_text("⏳ Video yuklanmoqda, kuting...")

    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': 'video_%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
    }

    file_path = None
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

        with open(file_path, 'rb') as video_file:
            await update.message.reply_video(video=video_file, caption="✅ Video yuklab olindi!")
        
        await msg.delete()

    except Exception as e:
        logging.error(f"Xatolik: {e}")
        await msg.edit_text("❌ Videoni yuklab bo'lmadi. Havola to'g'riligini tekshiring.")

    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

def main():
    # Orqa fonda kichik serverni yurgizib qo'yish
    Thread(target=run_health_check_server, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_and_send))

    print("Bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()
