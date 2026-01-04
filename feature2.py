import requests
import random
import asyncio
from telegram import Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, filters
from feature1 import check_channel_membership

API_KEY = "5d2e33c19847dea76f4fdb49695fd81aa669af86"
API_URL = "https://vuotlink.vip/api"
media_groups = {}

async def format_text(text: str) -> str:
    lines = text.splitlines()
    new_lines = []
    for line in lines:
        words = line.split()
        new_words = []
        for word in words:
            if word.startswith("http"):
                params = {"api": API_KEY, "url": word, "format": "text"}
                try:
                    response = requests.get(API_URL, params=params, timeout=10)
                    short_link = response.text.strip() if response.status_code == 200 else word
                    word = f"<s>{short_link}</s>"
                except: word = f"<s>{word}</s>"
            else: word = f"<b>{word}</b>"
            new_words.append(word)
        new_lines.append(" ".join(new_words))

    new_lines.append(
        '\n<b>Báo lỗi + đóng góp video:</b> @nothinginthissss\n'
        '<b>Thông báo:</b> @sachkhongchuu\n'
        '<b>Hướng dẫn vượt link:</b> @HuongDanVuotLink_SachKhongChu\n\n'
        '⚠️<b>Kênh xem không cần vượt:</b> '
        '<a href="https://t.me/sachkhongchuu/299">Ấn vào đây</a>'
    )
    return "\n".join(new_lines)

async def process_media_group(media_group_id: str, user_chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    await asyncio.sleep(random.uniform(3, 5))
    messages = media_groups.pop(media_group_id, [])
    if not messages: return
    messages.sort(key=lambda m: m.message_id)
    media = []
    caption = None
    for i, message in enumerate(messages):
        if i == 0 and message.caption: caption = await format_text(message.caption)
        if message.photo:
            file_id = message.photo[-1].file_id
            media.append(InputMediaPhoto(file_id, caption=caption if i == 0 else None, parse_mode="HTML"))
        elif message.video:
            file_id = message.video.file_id
            media.append(InputMediaVideo(file_id, caption=caption if i == 0 else None, parse_mode="HTML"))
    if media: await context.bot.send_media_group(chat_id=user_chat_id, media=media)

async def api_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not await check_channel_membership(update, context): return
    user_id = update.message.from_user.id
    args = context.args
    if args and args[0].lower() == "on":
        context.user_data['current_mode'] = 'API' # Bật mode API
        await update.message.reply_text("✅ Tính năng API đã bật!")
    elif args and args[0].lower() == "off":
        context.user_data['current_mode'] = None
        await update.message.reply_text("❌ Tính năng API đã tắt.")

async def handle_api_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not await check_channel_membership(update, context): return
    # CHỈ xử lý nếu đang bật mode API
    if context.user_data.get('current_mode') != 'API': return

    msg = update.message
    if msg.chat.type != "private": return
    
    # Xử lý Album
    if msg.media_group_id:
        mgid = msg.media_group_id
        if mgid not in media_groups:
            media_groups[mgid] = []
            asyncio.create_task(process_media_group(mgid, msg.chat_id, context))
        media_groups[mgid].append(msg)
        return

    text = msg.text or msg.caption or ""
    if "http" in text:
        caption = await format_text(text)
        if msg.photo: await msg.reply_photo(msg.photo[-1].file_id, caption=caption, parse_mode="HTML")
        elif msg.video: await msg.reply_video(msg.video.file_id, caption=caption, parse_mode="HTML")
        else: await msg.reply_text(caption, parse_mode="HTML")
        return

    if msg.forward_from or msg.forward_from_chat:
        caption = await format_text(msg.caption or "")
        await msg.copy(chat_id=msg.chat_id, caption=caption, parse_mode="HTML")
        return
    await msg.reply_text("📩 Bot đã nhận được tin nhắn của bạn.")

def register_feature2(app):
    app.add_handler(CommandHandler("api", api_command))
    app.add_handler(MessageHandler((filters.TEXT | filters.PHOTO | filters.VIDEO | filters.FORWARDED) & ~filters.COMMAND, handle_api_message), group=1)
