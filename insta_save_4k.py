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

# Render platformasi uxlab qolmasligi uchun HTTP server
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
ADMIN_PASSWORD = "behruz700"  # Admin paroli

# Siz bergan majburiy obuna kanali
REQUIRED_CHANNEL = "@boynazarov014"

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

# Majburiy obunani tekshirish funksiyasi
async def check_subscription(user_id, context):
    if not REQUIRED_CHANNEL:
        return True
    try:
        member = await context.bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
        if member.status in ['creator', 'administrator', 'member']:
            return True
        return False
    except Exception as e:
        logging.error(f"Obuna tekshirishda xatolik: {e}")
        return True  # Agar bot kanalda admin bo'lmasa, foydalanuvchilar to'silib qolmasligi uchun True qaytaradi

# Obuna xabari
async def send_sub_message(update: Update):
    keyboard = [
        [InlineKeyboardButton("📢 Kanalga a'zo bo'lish", url=f"https://t.me/boynazarov014")],
        [InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg_text = "⚠️ **Botdan foydalanish uchun avval rasmiy kanalimizga a'zo bo'ling!**"
    
    if update.message:
        await update.message.reply_text(msg_text, reply_markup=reply_markup, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.message.reply_text(msg_text, reply_markup=reply_markup, parse_mode="Markdown")

# /start xabari
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)

    if not await check_subscription(user_id, context):
        await send_sub_message(update)
        return

    welcome_text = (
        "✨ **InstaSave Botiga xush kelibsiz!** ✨\n\n"
        "Men sizga sevimli va qiziqarli medialaringizni bir necha soniyada yuklab beraman! 🚀\n\n"
        "📌 **Imkoniyatlarim:**\n"
        "🎬 **Instagram / TikTok / YouTube:** Link yuboring.\n"
        "🎵 **Videodan audio:** Link yuborib, MP3 qilib oling.\n"
        "🔍 **Musiqa qidiruv:** Qo'shiq nomini yozing.\n\n"
        "👇 *Boshlash uchun havola yoki qo'shiq nomini yozib yuboring!*"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

# Admin panel (/admin behruz700)
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args or args[0] != ADMIN_PASSWORD:
        await update.message.reply_text("🔒 **Parol noto'g'ri!** Ishlatish: `/admin behruz700`", parse_mode="Markdown")
        return

    users = load_users()
    await update.message.reply_text(
        f"📊 **Admin Panel**\n\n"
        f"👥 Jami foydalanuvchilar: **{len(users)}** ta\n\n"
        f"📢 Xabar yuborish: `/broadcast behruz700 Xabar matni`",
        parse_mode="Markdown"
    )

# Broadcast (/broadcast behruz700 Xabar)
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args or args[0] != ADMIN_PASSWORD:
        await update.message.reply_text("🔒 **Parol noto'g'ri!** Ishlatish: `/broadcast behruz700 Xabar`", parse_mode="Markdown")
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

# Message Handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)

    if not await check_subscription(user_id, context):
        await send_sub_message(update)
        return

    text = update.message.text.strip()
    supported = ["instagram.com", "tiktok.com", "youtube.com", "youtu.be"]

    if any(domain in text for domain in supported):
        keyboard = [
            [
                InlineKeyboardButton("📹 Videoni yuklash (HD)", callback_data=f"video|{text}"),
                InlineKeyboardButton("🎵 Audioni yuklash (MP3)", callback_data=f"audio|{text}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("⚡ **Nimani yuklab olmoqchisiz?**", reply_markup=reply_markup, parse_mode="Markdown")

    else:
        msg = await update.message.reply_text(f"🔍 **«{text}»** musiqasi qidirilmoqda...", parse_mode="Markdown")
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
            await msg.edit_text("❌ *Musiqa topilmadi yoki yuklab bo'lmadi.*", parse_mode="Markdown")

        finally:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)

# Callback Handler
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "check_sub":
        user_id = query.from_user.id
        if await check_subscription(user_id, context):
            await query.message.edit_text("✅ **A'zolik tasdiqlandi! Endi botdan foydalanishingiz mumkin.**", parse_mode="Markdown")
        else:
            await query.answer("❌ Hali kanalga a'zo bo'lmadingiz!", show_alert=True)
        return

    data = query.data.split("|", 1)
    download_type = data[0]
    url = data[1]

    msg = await query.message.edit_text("⏳ *Fayl yuklanmoqda va tayyorlanmoqda...*", parse_mode="Markdown")

    file_path = None
    try:
        ydl_opts_base = {
            'quiet': True,
            'no_warnings': True,
        }
        
        if os.path.exists("cookies.txt"):
            ydl_opts_base['cookiefile'] = "cookies.txt"

        if download_type == "video":
            ydl_opts = {
                **ydl_opts_base,
                'format': 'bestvideo+bestaudio/best',
                'merge_output_format': 'mp4',
                'outtmpl': 'download_%(id)s.%(ext)s',
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
                **ydl_opts_base,
                'format': 'bestaudio/best',
                'outtmpl': 'download_%(id)s.%(ext)s',
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
        await msg.edit_text("❌ *Xatolik yuz berdi. Havola to'g'riligini tekshiring.*", parse_mode="Markdown")

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
