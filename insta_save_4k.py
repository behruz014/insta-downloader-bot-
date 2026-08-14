import os
import logging
import aiohttp
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# Log sozlamalari
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Render uchun Health Check server
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot ishlamoqda!")

def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

BOT_TOKEN = "8387237045:AAFbN2d1JkZhj3Cak2SsQF5ob7paRbb2iDs"

# Cobalt API yordamida yuklash funksiyasi
async def fetch_from_cobalt(url: str, is_audio: bool = False):
    api_url = "https://api.cobalt.tools/"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    payload = {
        "url": url,
        "downloadMode": "audio" if is_audio else "auto",
        "audioFormat": "mp3"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(api_url, json=payload, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("url")
            return None

# /start xabari
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "<b>Salom! Men media yuklovchi botman.</b> 🚀\n\n"
        "🎬 <b>Video yuklash uchun:</b>\n"
        "<i>Instagram, TikTok yoki YouTube linkini yuboring.</i>"
    )
    await update.message.reply_text(text, parse_mode="HTML")

# Xabarlarni qabul qilish
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    supported = ["instagram.com", "tiktok.com", "youtube.com", "youtu.be", "vt.tiktok.com"]
    
    if any(domain in text for domain in supported):
        keyboard = [
            [
                InlineKeyboardButton("📹 Video", callback_data=f"video|{text}"),
                InlineKeyboardButton("🎵 MP3 (Audio)", callback_data=f"audio|{text}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "<b>Yuklab olish turini tanlang:</b> 📥", 
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            "❌ <b>Noto'g'ri havola!</b>\n<i>Iltimos, Instagram, TikTok yoki YouTube linkini yuboring.</i>",
            parse_mode="HTML"
        )

# Tugma bosilganda
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split("|", 1)
    download_type = data[0]
    url = data[1]

    msg = await query.message.edit_text("⏳ <b>Media tayyorlanmoqda, kuting...</b>", parse_mode="HTML")

    try:
        is_audio = True if download_type == "audio" else False
        download_link = await fetch_from_cobalt(url, is_audio=is_audio)

        if not download_link:
            await msg.edit_text("❌ <b>Xatolik!</b> Videoni yuklab bo'lmadi. Profil yopiq bo'lishi mumkin.", parse_mode="HTML")
            return

        if download_type == "video":
            await query.message.reply_video(
                video=download_link,
                caption="✅ <b>Muvaffaqiyatli yuklab olindi!</b>",
                parse_mode="HTML"
            )
        else:
            await query.message.reply_audio(
                audio=download_link,
                caption="✅ <b>Audio yuklab olindi!</b>",
                parse_mode="HTML"
            )

        await msg.delete()

    except Exception as e:
        logging.error(f"Xatolik: {e}")
        await msg.edit_text("❌ <b>Yuklashda xatolik yuz berdi.</b>", parse_mode="HTML")

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
