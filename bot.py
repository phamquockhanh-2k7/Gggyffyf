import requests
import asyncio
import logging
import re
import time
from urllib.parse import quote
from telegram import Bot, Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# --------------------- CẤU HÌNH ---------------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# CẤU HÌNH API (THAY BẰNG THÔNG TIN THẬT)
BOT_TOKEN = "YOUR_BOT_TOKEN"
API_CONFIG = {
    "mualink": {  # ĐƯỢC ƯU TIÊN XỬ LÝ TRƯỚC
        "api_key": "f65ee4fd9659f8ee84ad31cd1c8dd011307cbed0",
        "api_url": "https://mualink.vip/api",
        "timeout": 20
    },
    "vuotlink": {
        "api_key": "5d2e33c19847dea76f4fdb49695fd81aa669af86",
        "api_url": "https://vuotlink.vip/api",
        "timeout": 10
    }
}

# --------------------- CORE FUNCTIONS ---------------------
async def shorten_url(url: str) -> Tuple[str, str]:
    """Rút gọn URL với MuaLink ưu tiên"""
    async def _shorten(service: str) -> str:
        config = API_CONFIG[service]
        for attempt in range(2):  # Thử tối đa 2 lần
            try:
                params = {
                    "api": config["api_key"],
                    "url": quote(url, safe=''),
                    "format": "text",
                    "_": str(int(time.time()))  # Cache buster
                }
                
                response = requests.get(
                    config["api_url"],
                    params=params,
                    timeout=config["timeout"]
                )
                
                if response.status_code == 200:
                    result = response.text.strip()
                    if result and result != url:
                        if service == "mualink":
                            if result.startswith("https://mualink.vip/"):
                                return result
                        else:
                            return result
                
                await asyncio.sleep(1)  # Đợi trước khi retry
                
            except Exception as e:
                logger.warning(f"{service} attempt {attempt+1} failed: {str(e)}")
                await asyncio.sleep(1)
        
        return url  # Fallback về URL gốc

    # Xử lý MuaLink TRƯỚC, nếu fail mới dùng VuotLink
    mualink = await _shorten("mualink")
    vuotlink = await _shorten("vuotlink") if mualink == url else url
    
    logger.info(f"Kết quả: MuaLink={mualink}, VuotLink={vuotlink}")
    return vuotlink, mualink

async def format_caption(text: str) -> str:
    """Định dạng caption với link đã rút gọn"""
    if not text:
        return ""
    
    urls = re.findall(r'https?://[^\s]+', text)
    for url in urls:
        vlink, mlink = await shorten_url(url)
        replacement = (
            f"\n<b>• VUOTLINK:</b> {vlink if vlink != url else '❌ Lỗi'}\n"
            f"<b>• MUALINK:</b> {mlink if mlink != url else '❌ Lỗi'}"
        )
        text = text.replace(url, replacement)
    
    return f"{text}\n\n<b>🔗 Đã rút gọn tự động</b>"

# --------------------- HANDLERS ---------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 <b>Bot rút gọn link đa dịch vụ</b>\n\n"
        "Gửi link hoặc bài viết có chứa link để tự động rút gọn\n"
        "• MuaLink được ưu tiên xử lý trước\n"
        "• VuotLink sẽ được dùng khi MuaLink lỗi",
        parse_mode="HTML"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.effective_chat.type != "private":
        return

    # Xử lý link trực tiếp
    if update.message.text and re.match(r'^https?://', update.message.text.strip()):
        url = update.message.text.strip()
        vlink, mlink = await shorten_url(url)
        
        status = ""
        if mlink == url:
            status = "\n\n⚠️ MuaLink đang bảo trì, đã dùng VuotLink thay thế"
        
        await update.message.reply_text(
            f"🌐 <b>Link gốc:</b> {url}\n\n"
            f"🔗 <b>MuaLink:</b> {mlink}\n"
            f"🔗 <b>VuotLink:</b> {vlink}"
            f"{status}",
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
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(
        filters.TEXT | filters.PHOTO | filters.VIDEO,
        handle_message
    ))
    
    logger.info("Bot đã sẵn sàng, MuaLink được ưu tiên xử lý trước...")
    app.run_polling()

if __name__ == "__main__":
    main()
