import asyncio
import random
import requests
from telegram import Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, filters

API_KEY = "5d2e33c19847dea76f4fdb49695fd81aa669af86"
API_URL = "https://vuotlink.vip/api"

# Biến trạng thái bật/tắt feature2
feature2_enabled = False

# Lưu nhóm media tạm
media_groups = {}

async def format_text(text: str) -> str:
    """Định dạng caption: in đậm, rút link, thêm phần hướng dẫn."""
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

async def process_media_group(media_group_id: str, user_chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Gửi lại nhóm media sau khi nhận đủ."""
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

async def handle_text_or_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý tin nhắn nếu feature2 đang bật."""
    global feature2_enabled

    if not feature2_enabled:
        # Tính năng 2 đang tắt => bỏ qua, để tính năng 1 xử lý
        return

    msg = update.message
    if not msg:
        return

    # Nhóm media
    if msg.media_group_id:
        mgid = msg.media_group_id
        if mgid not in media_groups:
            media_groups[mgid] = []
            asyncio.create_task(process_media_group(mgid, msg.chat_id, context))
        media_groups[mgid].append(msg)
        return

    # Ảnh / video có caption
    if msg.caption:
        caption = await format_text(msg.caption)
        if msg.photo:
            await msg.reply_photo(photo=msg.photo[-1].file_id, caption=caption, parse_mode="HTML")
        elif msg.video:
            await msg.reply_video(video=msg.video.file_id, caption=caption, parse_mode="HTML")
        return

    # Tin nhắn văn bản chứa link
    if msg.text and "http" in msg.text:
        caption = await format_text(msg.text)
        await msg.reply_text(caption, parse_mode="HTML")
        return

    # Tin nhắn chuyển tiếp
    if msg.forward_from or msg.forward_from_chat:
        new_caption = await format_text(msg.caption or "")
        await msg.copy(chat_id=msg.chat_id, caption=new_caption, parse_mode="HTML")

# Lệnh bật feature2
async def apion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global feature2_enabled
    feature2_enabled = True
    await update.message.reply_text("✅ Đã bật tính năng 2 (rút link + định dạng nội dung).")

# Lệnh tắt feature2
async def apioff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global feature2_enabled
    feature2_enabled = False
    await update.message.reply_text("🟡 Đã tắt tính năng 2, quay lại tính năng mặc định.")

def register_feature2(app):
    """Đăng ký handler cho tính năng 2."""
    app.add_handler(CommandHandler("apion", apion))
    app.add_handler(CommandHandler("apioff", apioff))
    app.add_handler(MessageHandler(
        filters.PHOTO | filters.VIDEO | filters.TEXT & ~filters.COMMAND,
        handle_text_or_media
    ))
