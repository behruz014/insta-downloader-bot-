import os
import uuid
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

# ==========================================
# SOZLAMALAR
# ==========================================
BOT_TOKEN = "8476281963:AAHq_8j7cT49_UbkM8P5aZ1JPk7DGhwsELk"
SUPPORTED_DOMAINS = ["instagram.com", "tiktok.com", "youtube.com", "youtu.be"]

def get_ydl_options(outtmpl, is_audio=False):
    opts = {
        'quiet': True,
        'no_warnings': True,
        'outtmpl': outtmpl,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'
    }
    if is_audio:
        opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
    else:
        opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    return opts

# ==========================================
# HANDLERLAR
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "👋 *Xush kelibsiz!*\n\n"
        "📥 *Video yuklash uchun:* Instagram, TikTok yoki YouTube linkini yuboring.\n"
        "🎵 *Musiqa topish uchun:* Qo'shiq nomini yoki xonandani yozing."
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def download_and_send_video(update: Update, url: str):
    msg = await update.message.reply_text("🔎 Video yuklanmoqda...")
    file_id = uuid.uuid4().hex[:8]
    outtmpl = f"video_{file_id}.%(ext)s"
    
    loop = asyncio.get_running_loop()
    file_path = None

    try:
        def extract():
            with yt_dlp.YoutubeDL(get_ydl_options(outtmpl)) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info)

        file_path = await loop.run_in_executor(None, extract)

        with open(file_path, 'rb') as video:
            await update.message.reply_video(video=video, caption="✅ Video tayyor!")
        await msg.delete()

    except Exception as e:
        await msg.edit_text("❌ Videoni yuklab bo'lmadi. Linkni tekshiring.")
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

async def search_and_send_music(update: Update, query: str):
    msg = await update.message.reply_text(f"🔍 «{query}» qidirilmoqda...")
    file_id = uuid.uuid4().hex[:8]
    outtmpl = f"music_{file_id}.%(ext)s"
    
    loop = asyncio.get_running_loop()
    mp3_path = None

    try:
        def extract():
            opts = get_ydl_options(outtmpl, is_audio=True)
            opts['default_search'] = 'ytsearch1:'
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(query, download=True)
                if 'entries' in info and len(info['entries']) > 0:
                    info = info['entries'][0]
                
                title = info.get('title', 'Musiqa')
                base_path = ydl.prepare_filename(info)
                base, _ = os.path.splitext(base_path)
                return base + ".mp3", title

        mp3_path, title = await loop.run_in_executor(None, extract)

        if os.path.exists(mp3_path):
            with open(mp3_path, 'rb') as audio:
                await update.message.reply_audio(audio=audio, title=title, caption=f"🎧 {title}")
            await msg.delete()
        else:
            await msg.edit_text("❌ Musiqa topilmadi.")

    except Exception as e:
        await msg.edit_text("❌ Musiqani yuklashda xatolik yuz berdi.")
    finally:
        if mp3_path and os.path.exists(mp3_path):
            os.remove(mp3_path)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    if any(domain in text for domain in SUPPORTED_DOMAINS):
        await download_and_send_video(update, text)
    else:
        await search_and_send_music(update, text)

# ==========================================
# ASOSIY ISHGA TUSHIRISH
# ==========================================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot muvaffaqiyatli ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()
