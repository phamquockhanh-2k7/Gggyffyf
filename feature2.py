import requests
import random
import asyncio
from telegram import Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, filters
from feature1 import check_channel_membership  # Dùng lại kiểm tra sub kênh

# === Cấu hình ===
API_KEY = "5d2e33c19847dea76f4fdb49695fd81aa669af86"
API_URL = "https://vuotlink.vip/api"

# Bật/tắt tính năng cho từng user
user_api_enabled = {}

# Lưu nhóm media tạm
media_groups = {}

# ====== Hàm rút gọn link & định dạng caption ======
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
                except Exception:
                    word = f"<s>{word}</s>"
            else:
                word = f"<b>{word}</b>"
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

# ====== Xử lý nhóm ảnh/video ======
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
            media.append(InputMediaPhoto(file_id, caption=caption if i == 0 else None, parse_mode="HTML"))
        elif message.video:
            file_id = message.video.file_id
            media.append(InputMediaVideo(file_id, caption=caption if i == 0 else None, parse_mode="HTML"))

    if media:
        await context.bot.send_media_group(chat_id=user_chat_id, media=media)

# Custom filter: Chỉ match nếu /api bật cho user
def api_enabled_filter(update: Update) -> bool:
    if not update.message:
        return False
    user_id = update.message.from_user.id
    return user_api_enabled.get(user_id, False)

# ====== Lệnh /api ======
async def api_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not await check_channel_membership(update, context):
        return

    user_id = update.message.from_user.id
    args = context.args
    if args and args[0].lower() == "on":
        user_api_enabled[user_id] = True
        await update.message.reply_text("✅ Tính năng API đã bật! Gửi tin nhắn để bot rút gọn link và phản hồi.")
    elif args and args[0].lower() == "off":
        user_api_enabled[user_id] = False
        await update.message.reply_text("❌ Tính năng API đã tắt.")
    else:
        status = "bật" if user_api_enabled.get(user_id, False) else "tắt"
        await update.message.reply_text(f"📋 Trạng thái API: {status}\nNhắn /api on để bật, /api off để tắt.")

# ====== Xử lý tin nhắn ======
async def handle_api_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not await check_channel_membership(update, context):
        return

    user_id = update.message.from_user.id
    if not user_api_enabled.get(user_id, False):
        return

    chat_type = update.message.chat.type
    if chat_type != "private":
        return

    msg = update.message
    text = msg.text or msg.caption or ""

    # === Xử lý nhóm media (album) ===
    if msg.media_group_id:
        mgid = msg.media_group_id
        if mgid not in media_groups:
            media_groups[mgid] = []
            asyncio.create_task(process_media_group(mgid, msg.chat_id, context))
        media_groups[mgid].append(msg)
        return

    # === Ảnh hoặc video có caption ===
    if msg.caption and ("http" in msg.caption):
        caption = await format_text(msg.caption)
        if msg.photo:
            await msg.reply_photo(msg.photo[-1].file_id, caption=caption, parse_mode="HTML")
        elif msg.video:
            await msg.reply_video(msg.video.file_id, caption=caption, parse_mode="HTML")
        return

    # === Tin nhắn text có link ===
    if msg.text and "http" in msg.text:
        caption = await format_text(msg.text)
        await msg.reply_text(caption, parse_mode="HTML")
        return

    # === Tin nhắn forward ===
    if msg.forward_from or msg.forward_from_chat:
        caption = await format_text(msg.caption or "")
        await msg.copy(chat_id=msg.chat_id, caption=caption, parse_mode="HTML")
        return

    # === Tin nhắn bình thường ===
    await msg.reply_text("📩 Bot đã nhận được tin nhắn của bạn.")

# ====== Đăng ký vào app chính ======
def register_feature2(app):
    app.add_handler(CommandHandler("api", api_command))
    # Sử dụng custom filter thay vì filters tĩnh
    app.add_handler(MessageHandler(
        api_enabled_filter & (filters.TEXT | filters.PHOTO | filters.VIDEO | filters.FORWARDED) & ~filters.COMMAND,
        handle_api_message
    ))
