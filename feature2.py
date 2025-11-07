import asyncio
import random
import requests
import nest_asyncio
from telegram import Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, filters
from feature1 import check_channel_membership  # Tái sử dụng từ feature1

nest_asyncio.apply()

# === THAY THẾ BẰNG GIÁ TRỊ THẬT ===
API_KEY = "5d2e33c19847dea76f4fdb49695fd81aa669af86"     # Ví dụ: "abc123"
API_URL = "https://vuotlink.vip/api"  # Ví dụ: "https://vuotlink.vip/api"

# State để bật/tắt tính năng cho từng user
user_api_enabled = {}  # user_id: True/False

# Lưu trữ media groups tạm thời (cho xử lý nhóm)
media_groups = {}
processing_tasks = {}

async def format_text(text: str) -> str:
    lines = text.splitlines()
    new_lines = []
    for line in lines:
        words = line.split()
        new_words = []
        for word in words:
            if word.startswith("http"):
                params = {"api": API_KEY, "url": word, "format": "text"}
                response = requests.get(API_URL, params=params)
                short_link = response.text.strip() if response.status_code == 200 else word
                word = f"<s>{short_link}</s>"
            else:
                word = f"<b>{word}</b>"
            new_words.append(word)
        new_lines.append(" ".join(new_words))

    new_lines.append(
        '\n<b>Báo lỗi + đóng góp video tại đây</b> @nothinginthissss (có lỗi sẽ đền bù)\n'
        '<b>Theo dõi thông báo tại đây</b> @sachkhongchuu\n'
        '<b>CÁCH XEM LINK:</b> @HuongDanVuotLink_SachKhongChu\n\n'
        '⚠️<b>Kênh xem không cần vượtt :</b> <a href="https://t.me/sachkhongchuu/299">ấn vào đây</a>'
    )

    return "\n".join(new_lines)

async def process_media_group(media_group_id: str, user_chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    await asyncio.sleep(random.uniform(3, 5))
    messages = media_groups.pop(media_group_id, [])
    if not messages:
        return

    messages.sort(key=lambda m: m.message_id)
    media = []
    caption = None

    for i, message in enumerate(messages):
        if i == 0 and message.caption:
            caption = await format_text(message.caption)

        if message.photo:
            file_id = message.photo[-1].file_id
            media.append(InputMediaPhoto(media=file_id, caption=caption if i == 0 else None, parse_mode="HTML"))
        elif message.video:
            file_id = message.video.file_id
            media.append(InputMediaVideo(media=file_id, caption=caption if i == 0 else None, parse_mode="HTML"))

    if media:
        await context.bot.send_media_group(chat_id=user_chat_id, media=media)

# /api handler: Bật/tắt tính năng
async def api_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not await check_channel_membership(update, context):
        return

    user_id = update.message.from_user.id
    args = context.args
    if args and args[0].lower() == "on":
        user_api_enabled[user_id] = True
        await update.message.reply_text("✅ Tính năng API đã bật! Gửi tin nhắn để bot xử lý và gửi lại.")
    elif args and args[0].lower() == "off":
        user_api_enabled[user_id] = False
        await update.message.reply_text("❌ Tính năng API đã tắt.")
    else:
        status = "bật" if user_api_enabled.get(user_id, False) else "tắt"
        await update.message.reply_text(f"📋 Trạng thái API: {status}\nNhắn /api on để bật, /api off để tắt.")

# Handler cho tin nhắn (chỉ xử lý nếu API bật)
async def handle_api_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not await check_channel_membership(update, context):
        return

    user_id = update.message.from_user.id
    if not user_api_enabled.get(user_id, False):
        return  # Không xử lý nếu chưa bật

    chat_type = update.message.chat.type
    if chat_type != "private":
        return

    # Xử lý media group
    if update.message.media_group_id:
        mgid = update.message.media_group_id
        if mgid not in media_groups:
            media_groups[mgid] = []
            processing_tasks[mgid] = asyncio.create_task(process_media_group(mgid, update.message.chat_id, context))
        
        media_groups[mgid].append(update.message)
        return
    
    # Xử lý tin nhắn đơn lẻ có caption (ảnh/video)
    if update.message.caption:
        caption = await format_text(update.message.caption)
        
        if update.message.photo:
            await context.bot.send_photo(
                chat_id=update.message.chat.id, 
                photo=update.message.photo[-1].file_id,
                caption=caption, 
                parse_mode="HTML"
            )
        elif update.message.video:
            await context.bot.send_video(
                chat_id=update.message.chat.id, 
                video=update.message.video.file_id,
                caption=caption, 
                parse_mode="HTML"
            )
        return
    
    # Xử lý tin nhắn text chứa link
    if update.message.text and "http" in update.message.text:
        caption = await format_text(update.message.text)
        await context.bot.send_message(chat_id=update.message.chat.id, text=caption, parse_mode="HTML")
        return
    
    # Xử lý tin nhắn forward
    if update.message.forward_from or update.message.forward_from_chat:
        caption = update.message.caption or ""
        new_caption = await format_text(caption)
        await update.message.copy(chat_id=update.effective_chat.id, caption=new_caption, parse_mode="HTML")

def register_feature2(app):
    app.add_handler(CommandHandler("api", api_command))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_api_message))  # Catch tất cả tin nhắn, nhưng chỉ xử lý nếu bật
