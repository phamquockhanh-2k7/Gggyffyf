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
BOT_TOKEN = "8064426886:AAE5Zr980N-8LhGgnXGqUXwqlPthvdKA9H0"
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
async def shorten_url(url: str) -> Tuple[str, str]:
    """Rút gọn URL bằng cả 2 dịch vụ với cơ chế retry"""
    async def _shorten(service: str) -> str:
        for _ in range(2):  # Thử tối đa 2 lần
            try:
                config = API_CONFIG[service]
                params = {
                    "api": config["api_key"],
                    "url": quote(url, safe=''),
                    "format": "text"
                }
                response = requests.get(config["api_url"], params=params, timeout=10)
                
                if response.status_code == 200 and response.text.strip() and response.text.strip() != url:
                    return response.text.strip()
            except Exception as e:
                logger.warning(f"Lỗi {service}: {str(e)}")
                await asyncio.sleep(1)
        return url

    # Chạy song song cả 2 dịch vụ
    vuotlink, mualink = await asyncio.gather(
        _shorten("vuotlink"),
        _shorten("mualink")
    )
    
    logger.info(f"Rút gọn thành công: V={vuotlink}, M={mualink}")
    return vuotlink, mualink

async def format_caption(text: str) -> str:
    """Định dạng caption với link rút gọn"""
    if not text:
        return ""
    
    async def _process(match):
        url = match.group(0)
        vlink, mlink = await shorten_url(url)
        return (
            f"\n<b>• VUOTLINK:</b> {vlink}"
            f"\n<b>• MUALINK:</b> {mlink}"
        )
    
    # Xử lý tất cả link trong text
    pattern = re.compile(r'https?://[^\s]+')
    result = await asyncio.to_thread(pattern.sub, lambda m: asyncio.run_coroutine_threadsafe(_process(m), text)
    
    return f"{result}\n\n<b>🔗 Đã rút gọn tự động</b>"

# --------------------- HANDLERS ---------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛠 <b>Bot rút gọn link đa dịch vụ</b>\n\n"
        "• Gửi link trực tiếp hoặc bài viết có chứa link\n"
        "• Tự động rút gọn bằng <b>VuotLink</b> và <b>MuaLink</b>\n\n"
        "⚙️ <i>/help để xem hướng dẫn</i>",
        parse_mode="HTML"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return

    # Xử lý link trực tiếp
    if update.message.text and re.match(r'^https?://', update.message.text.strip()):
        url = update.message.text.strip()
        vlink, mlink = await shorten_url(url)
        
        await update.message.reply_text(
            f"🌐 <b>Link gốc:</b> {url}\n\n"
            f"🔗 <b>VUOTLINK:</b> {vlink}\n"
            f"🔗 <b>MUALINK:</b> {mlink}\n\n"
            "✅ <i>Đã rút gọn tự động</i>",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        return

    # Xử lý media có caption
    if update.message.caption or (update.message.photo or update.message.video):
        new_caption = await format_caption(update.message.caption or "")
        await update.message.copy(
            chat_id=update.effective_chat.id,
            caption=new_caption,
            parse_mode="HTML"
        )

# --------------------- MAIN ---------------------
def main():
    keep_alive()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(
        filters.TEXT | filters.PHOTO | filters.VIDEO,
        handle_message
    ))

    logger.info("Bot đã sẵn sàng")
    app.run_polling()

if __name__ == "__main__":
    main()
