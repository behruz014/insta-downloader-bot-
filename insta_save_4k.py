import os
import logging
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import yt_dlp

# Log sozlamalari
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Render va boshqa xostinglar uchun soxta server (Web Service to'xtab qolmasligi uchun)
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is active!")

def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# Siz taqdim etgan Telegram Bot Token
BOT_TOKEN = "8387237045:AAFbN2d1JkZhj3Cak2SsQF5ob7paRbb2iDs"

# /start xabari
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Salom! Men universal media va musiqa yuklovchi botman. 🚀\n\n"
        "🎬 **Video yuklash uchun:** Instagram, TikTok yoki YouTube havolasini yuboring.\n"
        "🎵 **Musiqa qidirish uchun:** Qo'shiq nomini yoki xonandani yozib yuboring!"
    )

# Xabarlarni qayta ishlash (Link yoki Qo'shiq nomi)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    # Agar havola (link) bo'lsa
    supported = ["instagram.com", "tiktok.com", "youtube.com", "youtu.be"]
    if any(domain in text for domain in supported):
        keyboard = [
            [
                InlineKeyboardButton("📹 Video (Eng yuqori sifat)", callback_data=f"video|{text}"),
                InlineKeyboardButton("🎵 MP3 (Audio)", callback_data=f"audio|{text}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Nimani yuklab olishni xohlaysiz?", reply_markup=reply_markup)
    
    # Agar shunchaki tekst (qo'shiq nomi) bo'lsa -> Musiqa qidirish
    else:
        msg = await update.message.reply_text(f"🔍 **\"{text}\"** qo'shig'i qidirilmoqda...")
        file_path = None
        try:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': 'song_%(id)s.%(ext)s',
                'quiet': True,
                'no_warnings': True,
                'default_search': 'ytsearch1', # YouTube'dan 1-natijani qidiradi
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
                    caption=f"✅ **{title}**"
                )
            await msg.delete()

        except Exception as e:
            logging.error(f"Qidiruvda xatolik: {e}")
            await msg.edit_text("❌ Musiqa topilmadi yoki yuklab bo'lmadi. Boshqacharoq yozib ko'ring.")

        finally:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)

# Link orqali yuklash tugmasi bosilganda
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split("|", 1)
    download_type = data[0]
    url = data[1]

    msg = await query.message.edit_text("⏳ Yuklanmoqda, kuting...")

    file_path = None
    try:
        if download_type == "video":
            ydl_opts = {
                'format': 'bestvideo+bestaudio/best', # Eng yuqori sifat
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
                'outtmpl': 'download_%(id)s.mp3',
                'quiet': True,
                'no_warnings': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file_path = f"download_{info['id']}.mp3"

            with open(file_path, 'rb') as audio_file:
                await query.message.reply_audio(audio=audio_file, caption="✅ Audio (MP3) yuklab olindi!")

        await msg.delete()

    except Exception as e:
        logging.error(f"Xatolik: {e}")
        await msg.edit_text("❌ Yuklab bo'lmadi. Havola to'g'riligini va profil ochiqligini tekshiring.")

    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

def main():
    Thread(target=run_health_check_server, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))

    print("Bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()
