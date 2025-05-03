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

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

nest_asyncio.apply()

# Configuration
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
user_modes = {}  # user_id → "shorten" or "free"

# Core Functions
def shorten_link(url: str, service: str) -> str:
    """Shorten URL using specified service"""
    try:
        config = API_CONFIG.get(service)
        if not config:
            return url
            
        params = {
            "api": config["api_key"],
            "url": url,
            "format": "text"
        }
        response = requests.get(
            config["api_url"],
            params=params,
            timeout=10
        )
        return response.text.strip() if response.status_code == 200 else url
    except Exception as e:
        logger.error(f"Error shortening link ({service}): {e}")
        return url

def shorten_all_links(url: str) -> Tuple[str, str]:
    """Shorten URL with both services"""
    vuotlink = shorten_link(url, "vuotlink")
    mualink = shorten_link(url, "mualink")
    return vuotlink, mualink

async def format_text_with_dual_links(text: str) -> str:
    """Format text and replace URLs with both shortened versions"""
    if not text:
        return ""
    
    def process_line(line: str) -> str:
        processed_words = []
        for word in line.split():
            if re.match(r'^https?://', word):
                vuotlink, mualink = shorten_all_links(word)
                processed_words.append(
                    f"<b>• VUOTLINK:</b> {vuotlink}\n"
                    f"<b>• MUALINK:</b> {mualink}"
                )
            else:
                processed_words.append(f"<b>{word}</b>")
        return " ".join(processed_words)
    
    lines = [process_line(line) for line in text.splitlines() if line.strip()]
    
    # Add footer
    footer = (
        "\n\n<b>📢 Thông báo:</b> Đã tự động rút gọn bằng 2 dịch vụ\n"
        "<b>⚠️ Kênh xem không cần vượt:</b> @linkdinhcaovn"
    )
    return "\n".join(lines) + footer

async def process_media_group(mgid: str, chat_id: int, mode: str):
    """Process media group and resend with formatted caption"""
    try:
        await asyncio.sleep(random.uniform(3, 5))
        group = media_groups.pop(mgid, None)
        if not group:
            return

        group.sort(key=lambda m: m.message_id)
        caption = group[0].caption or ""
        if mode == "shorten":
            caption = await format_text_with_dual_links(caption)

        media = []
        for i, msg in enumerate(group):
            media_args = {
                "media": msg.photo[-1].file_id if msg.photo else msg.video.file_id,
                "caption": caption if i == 0 else None,
                "parse_mode": "HTML"
            }
            if msg.photo:
                media.append(InputMediaPhoto(**media_args))
            elif msg.video:
                media.append(InputMediaVideo(**media_args))

        if media:
            await bot.send_media_group(chat_id=chat_id, media=media)
    except Exception as e:
        logger.error(f"Media group processing error: {e}")
        await bot.send_message(chat_id, "⚠️ Có lỗi khi xử lý bài viết.")

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
        
    await update.message.reply_text(
        "👋 Chào bạn! Gửi link bất kỳ để rút gọn hoặc chuyển tiếp bài viết có media.\n"
        "🔧 Dùng /setmode để thay đổi chế độ hoạt động.",
        parse_mode="Markdown"
    )

async def set_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
        
    buttons = [
        [InlineKeyboardButton("🔗 Rút gọn link", callback_data="mode_shorten")],
        [InlineKeyboardButton("🆓 Link Free", callback_data="mode_free")]
    ]
    await update.message.reply_text(
        "Chọn chế độ hoạt động:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if query.data == "mode_shorten":
        user_modes[user_id] = "shorten"
        await query.edit_message_text("✅ Đã bật chế độ rút gọn link")
    elif query.data == "mode_free":
        user_modes[user_id] = "free"
        await query.edit_message_text("🆓 Đã bật chế độ link gốc (không rút gọn)")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
        
    user_id = update.effective_user.id
    mode = user_modes.get(user_id, "shorten")

    # Handle media groups
    if update.message.media_group_id:
        mgid = update.message.media_group_id
        if mgid not in media_groups:
            media_groups[mgid] = []
            processing_tasks[mgid] = asyncio.create_task(
                process_media_group(mgid, update.effective_chat.id, mode))
        media_groups[mgid].append(update.message)
        return

    # Handle direct links
    if update.message.text and re.match(r'^https?://', update.message.text.strip()):
        url = update.message.text.strip()
        vuotlink, mualink = shorten_all_links(url)
        
        await update.message.reply_text(
            f"🔗 <b>Link gốc:</b> {url}\n\n"
            f"📌 <b>VUOTLINK:</b> {vuotlink}\n"
            f"📌 <b>MUALINK:</b> {mualink}\n\n"
            "⚠️ <i>Link được rút gọn bằng 2 dịch vụ độc lập</i>",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        return

    # Handle forwarded messages or media with caption
    if (update.message.forward_date or update.message.caption or 
        update.message.photo or update.message.video):
        caption = update.message.caption or ""
        
        if mode == "shorten":
            new_caption = await format_text_with_dual_links(caption)
        else:
            new_caption = caption

        try:
            await update.message.copy(
                chat_id=update.effective_chat.id,
                caption=new_caption,
                parse_mode="HTML" if mode == "shorten" else None
            )
        except Exception as e:
            logger.error(f"Message copy error: {e}")
            await update.message.reply_text("⚠️ Không thể xử lý bài viết này.")

# Main Application
def main():
    keep_alive()  # For Replit
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Register handlers
    handlers = [
        CommandHandler("start", start),
        CommandHandler("setmode", set_mode),
        CallbackQueryHandler(handle_callback),
        MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO, handle_message)
    ]
    for handler in handlers:
        app.add_handler(handler)

    app.run_polling()

if __name__ == "__main__":
    main()
