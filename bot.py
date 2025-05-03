import requests
import asyncio
from telegram import Update
from telegram.ext import ContextTypes

# URL API
MUALINK_API_URL = "https://mualink.vip/api"
VUOTLINK_API_URL = "https://vuotlink.vip/api"

# API Key (thay đổi giá trị này theo nhu cầu)
MUALINK_API_KEY = "f65ee4fd9659f8ee84ad31cd1c8dd011307cbed0"
VUOTLINK_API_KEY = "5d2e33c19847dea76f4fdb49695fd81aa669af86"  # Thay bằng API Key của bạn

# Rút gọn link với mualink.vip
async def shorten_link_mualink(url: str) -> str:
    params_mualink = {"api": MUALINK_API_KEY, "url": url, "format": "text"}
    response_mualink = requests.get(MUALINK_API_URL, params=params_mualink)
    if response_mualink.status_code == 200:
        return response_mualink.text.strip()
    return url

# Rút gọn link với vuotlink.vip
async def shorten_link_vuotlink(url: str) -> str:
    params_vuotlink = {"api": VUOTLINK_API_KEY, "url": url, "format": "text"}
    response_vuotlink = requests.get(VUOTLINK_API_URL, params=params_vuotlink)
    if response_vuotlink.status_code == 200:
        return response_vuotlink.text.strip()
    return url

# Tin nhắn văn bản/ảnh/video
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private" or not update.message:
        return

    user_id = update.effective_user.id

    # Nếu chưa xác thực mật khẩu → từ chối
    if user_id not in authenticated_users:
        await update.message.reply_text("🔐 Bạn chưa xác thực. Gõ /setmode để bắt đầu.")
        return

    mode = user_modes.get(user_id, "shorten")

    if update.message.media_group_id:
        mgid = update.message.media_group_id
        if mgid not in media_groups:
            media_groups[mgid] = []
            processing_tasks[mgid] = asyncio.create_task(process_media_group(mgid, update.effective_chat.id, mode))
        media_groups[mgid].append(update.message)
        return

    if update.message.text and update.message.text.startswith("http") and mode == "shorten":
        # Rút gọn link từ cả 2 dịch vụ
        short_link_mualink = await shorten_link_mualink(update.message.text.strip())
        short_link_vuotlink = await shorten_link_vuotlink(update.message.text.strip())

        message = (
            "📢 <b>Bạn có link rút gọn mới</b>\n"
            f"🔗 <b>Link gốc:</b> <s>{update.message.text}</s>\n"
            f"🔍 <b>Link rút gọn mualink:</b> {short_link_mualink}\n"
            f"🔍 <b>Link rút gọn vuotlink:</b> {short_link_vuotlink}\n\n"
            '⚠️<b>Kênh xem không cần vượt :</b> <a href="https://t.me/sachkhongchuu/299">ấn vào đây</a>'
        )
        await update.message.reply_text(message, parse_mode="HTML")
        return

    if (update.message.forward_date or update.message.forward_from or update.message.forward_sender_name) or update.message.caption:
        caption = update.message.caption or ""
        new_caption = await format_text(caption) if mode == "shorten" else caption
        await update.message.copy(chat_id=update.effective_chat.id, caption=new_caption, parse_mode="HTML" if mode == "shorten" else None)
