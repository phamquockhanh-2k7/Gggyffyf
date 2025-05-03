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

# CẤU HÌNH BOT (THAY BẰNG THÔNG TIN THẬT CỦA BẠN)
BOT_TOKEN = "8064426886:AAE5Zr980N-8LhGgnXGqUXwqlPthvdKA9H0"  # 👈 Thay bằng token thật
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
    """Rút gọn link với xử lý riêng cho từng dịch vụ"""
    try:
        config = API_CONFIG.get(service)
        if not config:
            logger.error(f"Service {service} not configured")
            return url

        # Chuẩn bị params chung
        params = {
            "api": config["api_key"],
            "url": quote(url, safe=''),
            "format": "text"  # Bắt buộc cho cả 2 dịch vụ
        }

        response = requests.get(
            config["api_url"],
            params=params,
            timeout=15
        )
        
        # Debug
        logger.info(f"{service} API call: {response.url}")
        logger.info(f"Response: {response.status_code} - {response.text}")

        if response.status_code == 200:
            result = response.text.strip()
            
            # Xử lý đặc biệt cho MuaLink
            if service == "mualink":
                if not result:  # Trường hợp trả về trống
                    logger.warning("MuaLink returned empty response")
                    return url
                elif result == url:  # Trường hợp không rút gọn được
                    logger.warning("MuaLink returned original URL")
                    return url
                    
            return result
        return url

    except Exception as e:
        logger.error(f"Error shortening with {service}: {str(e)}")
        return url

def shorten_all_links(url: str) -> Tuple[str, str]:
    """Rút gọn bằng cả 2 dịch vụ và kiểm tra kết quả"""
    logger.info(f"Shortening URL: {url}")
    
    vuotlink = shorten_link(url, "vuotlink")
    mualink = shorten_link(url, "mualink")
    
    # Kiểm tra chất lượng kết quả
    if vuotlink == url:
        logger.warning("VuotLink failed to shorten")
    if mualink == url:
        logger.warning("MuaLink failed to shorten")
    
    return vuotlink, mualink

async def format_text_with_dual_links(text: str) -> str:
    """Định dạng văn bản với cả 2 phiên bản rút gọn"""
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
    
    footer = (
        "\n\n<b>📢 Thông báo:</b> Đã rút gọn bằng 2 dịch vụ độc lập\n"
        "<b>⚠️ Hỗ trợ:</b> @nothinginthissss"
    )
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
        "CHỌN CHẾ ĐỘ:",
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
            f"📌 <b>MUALINK:</b> {mlink if mlink != url else '❌ Lỗi'}\n\n"
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
