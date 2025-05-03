import requests
from telegram import Bot, Update, InputMediaPhoto, InputMediaVideo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import asyncio
import nest_asyncio
import random
import re
from keep_alive import keep_alive
import logging
from typing import Tuple
from urllib.parse import quote

# --------------------- CẤU HÌNH ---------------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

nest_asyncio.apply()

# CẤU HÌNH BOT TOKEN (THAY THẾ BẰNG TOKEN THẬT CỦA BẠN)
BOT_TOKEN = "8064426886:AAE5Zr980N-8LhGgnXGqUXwqlPthvdKA9H0"  # 👈 Thay thế bằng token thực của bạn

# Cấu hình API
API_CONFIG = {
    "vuotlink": {
        "api_key": "5d2e33c19847dea76f4fdb49695fd81aa669af86",
        "api_url": "https://vuotlink.vip/api"
    },
    "mualink": {
        "api_key": "f65ee4fd9659f8ee84ad31cd1c8dd011307cbed0",
        "api_url": "https://mualink.vip/api"
    }
}

bot = Bot(token=BOT_TOKEN)
media_groups = {}
processing_tasks = {}
user_modes = {}

# --------------------- CORE FUNCTIONS ---------------------
def shorten_link(url: str, service: str) -> str:
    try:
        config = API_CONFIG.get(service)
        if not config:
            return url

        params = {
            "api": config["api_key"],
            "url": quote(url, safe=''),
            "format": "text"
        }

        response = requests.get(
            config["api_url"],
            params=params,
            timeout=10
        )
        
        if response.status_code == 200:
            return response.text.strip() or url
        return url

    except Exception:
        return url

def shorten_all_links(url: str) -> Tuple[str, str]:
    return (
        shorten_link(url, "vuotlink"),
        shorten_link(url, "mualink")
    )

async def format_text_with_dual_links(text: str) -> str:
    if not text:
        return ""
    
    def process_line(line: str) -> str:
        processed_words = []
        for word in line.split():
            if re.match(r'^https?://', word):
                vlink, mlink = shorten_all_links(word)
                processed_words.append(
                    f"<b>• VUOTLINK:</b> {vlink}\n"
                    f"<b>• MUALINK:</b> {mlink if mlink != word else '❌ Lỗi'}"
                )
            else:
                processed_words.append(f"<b>{word}</b>")
        return " ".join(processed_words)
    
    lines = [process_line(line) for line in text.splitlines() if line.strip()]
    footer = "\n\n<b>📢 Rút gọn tự động bằng 2 dịch vụ</b>"
    return "\n".join(lines) + footer

# --------------------- HANDLERS ---------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Gửi link hoặc bài viết để rút gọn bằng 2 dịch vụ\n"
        "⚙️ /setmode để thay đổi chế độ",
        parse_mode="Markdown"
    )

async def set_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [
        [InlineKeyboardButton("🔗 Chế độ rút gọn", callback_data="mode_shorten")],
        [InlineKeyboardButton("🆓 Chế độ gốc", callback_data="mode_free")]
    ]
    await update.message.reply_text(
        "CHỌN CHẾ ĐỀ:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if query.data == "mode_shorten":
        user_modes[user_id] = "shorten"
        await query.edit_message_text("✅ Đã bật chế độ rút gọn")
    else:
        user_modes[user_id] = "free"
        await query.edit_message_text("🆓 Đã bật chế độ link gốc")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
        
    user_id = update.effective_user.id
    mode = user_modes.get(user_id, "shorten")

    # Xử lý link trực tiếp
    if update.message.text and re.match(r'^https?://', update.message.text.strip()):
        url = update.message.text.strip()
        vlink, mlink = shorten_all_links(url)
        
        await update.message.reply_text(
            f"🔗 <b>Gốc:</b> {url}\n\n"
            f"📌 <b>VUOTLINK:</b> {vlink}\n"
            f"📌 <b>MUALINK:</b> {mlink}\n\n"
            "⚠️ Đã rút gọn tự động",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        return

    # Xử lý media
    if update.message.caption or update.message.photo or update.message.video:
        caption = update.message.caption or ""
        if mode == "shorten":
            new_caption = await format_text_with_dual_links(caption)
        else:
            new_caption = caption
            
        await update.message.copy(
            chat_id=update.effective_chat.id,
            caption=new_caption,
            parse_mode="HTML" if mode == "shorten" else None
        )

# --------------------- MAIN ---------------------
def main():
    keep_alive()  # Bỏ qua nếu không dùng Replit
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setmode", set_mode))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO, handle_message))

    logger.info("Bot đang chạy...")
    app.run_polling()

if __name__ == "__main__":
    main()
