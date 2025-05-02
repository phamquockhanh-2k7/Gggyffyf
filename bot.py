import requests
from telegram import (
    Bot, Update, InputMediaPhoto, InputMediaVideo,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, MessageHandler, CommandHandler, CallbackQueryHandler,
    ContextTypes, filters
)
import asyncio
import nest_asyncio
import random
from keep_alive import keep_alive

nest_asyncio.apply()

BOT_TOKEN = "8064426886:AAE5Zr980N-8LhGgnXGqUXwqlPthvdKA9H0"
API_KEY = "5d2e33c19847dea76f4fdb49695fd81aa669af86"
API_URL = "https://vuotlink.vip/api"
API_FALLBACK_URL = "https://mualink.vip/api"

bot = Bot(token=BOT_TOKEN)
media_groups = {}
processing_tasks = {}
user_modes = {}  # Lưu chế độ người dùng: user_id → "shorten" hoặc "free"

# Gửi lời chào khi /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    await update.message.reply_text(
        "**🔗 Gửi link bất kỳ để rút gọn.**\n"
        "**📷 Chuyển tiếp bài viết kèm ảnh/video, bot sẽ giữ nguyên caption & rút gọn link trong caption.**\n"
        "**💬 Gõ /setmode để chọn chế độ hoạt động.**",
        parse_mode="Markdown"
    )

# Format text (rút gọn link + định dạng)
async def format_text(text: str) -> str:
    lines = text.splitlines()
    new_lines = []
    for line in lines:
        words = line.split()
        new_words = []
        for word in words:
            if word.startswith("http"):
                # Rút gọn link chính từ vuotlink.vip
                params = {"api": API_KEY, "url": word, "format": "text"}
                response = requests.get(API_URL, params=params)
                short_link = response.text.strip() if response.status_code == 200 else word
                
                # Rút gọn link dự phòng từ mualink.vip
                fallback_params = {
                    "api": "f65ee4fd9659f8ee84ad31cd1c8dd011307cbed0", 
                    "url": word, 
                    "alias": "CustomAlias", 
                    "format": "text"
                }
                fallback_response = requests.get(API_FALLBACK_URL, params=fallback_params)
                fallback_link = fallback_response.text.strip() if fallback_response.status_code == 200 else word

                # Thêm hai link vào caption
                word = f"<s>{short_link}</s> (Đây là link vượt, mua link thì nạp tiền bằng USDT)\n<b>Link dự phòng:</b> {fallback_link} ( Đây là link mua, có thể nạp bằng thẻ cào hoặc bank)"
            else:
                word = f"<b>{word}</b>"
            new_words.append(word)
        new_lines.append(" ".join(new_words))

    new_lines.append(
        '\n<b>Báo lỗi + đóng góp video tại đây</b> @nothinginthissss\n'
        '<b>Theo dõi thông báo tại đây</b> @linkdinhcaovn\n'
        '<b>CÁCH XEM LINK (nếu lỗi bot không gửi video):</b> @HuongDanVuotLink_SachKhongChu\n\n'
        '⚠️<b>Kênh xem không cần vượt :</b> <a href="https://t.me/linkdinhcaovn/4">ấn vào đây!</a>'
    )

    return "\n".join(new_lines)

# Xử lý nhóm media (ảnh/video)
async def process_media_group(mgid: str, chat_id: int, mode: str):
    await asyncio.sleep(random.uniform(3, 5))
    group = media_groups.pop(mgid, [])
    if not group:
        await bot.send_message(chat_id=chat_id, text="⚠️ Bài viết không hợp lệ hoặc thiếu ảnh/video.")
        return

    group.sort(key=lambda m: m.message_id)
    caption = group[0].caption if group[0].caption else ""
    if mode == "shorten" and caption:
        caption = await format_text(caption)

    media = []
    for i, msg in enumerate(group):
        if msg.photo:
            file_id = msg.photo[-1].file_id
            media.append(InputMediaPhoto(file_id, caption=caption if i == 0 else None, parse_mode="HTML"))
        elif msg.video:
            file_id = msg.video.file_id
            media.append(InputMediaVideo(file_id, caption=caption if i == 0 else None, parse_mode="HTML"))

    if not media:
        await bot.send_message(chat_id=chat_id, text="⚠️ Không có ảnh hoặc video hợp lệ.")
        return

    try:
        await bot.send_media_group(chat_id=chat_id, media=media)
    except Exception as e:
        print(f"Lỗi khi gửi media_group: {e}")
        await bot.send_message(chat_id=chat_id, text="⚠️ Gửi bài viết thất bại. Có thể file lỗi hoặc Telegram giới hạn.")

# Xử lý tin nhắn văn bản, ảnh, video, chuyển tiếp
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private" or not update.message:
        return

    user_id = update.effective_user.id
    mode = user_modes.get(user_id, "shorten")  # Mặc định là shorten

    # Media Group
    if update.message.media_group_id:
        mgid = update.message.media_group_id
        if mgid not in media_groups:
            media_groups[mgid] = []
            processing_tasks[mgid] = asyncio.create_task(process_media_group(mgid, update.effective_chat.id, mode))
        media_groups[mgid].append(update.message)
        return

    # Link rút gọn
    if update.message.text and update.message.text.startswith("http") and mode == "shorten":
        params = {"api": API_KEY, "url": update.message.text.strip(), "format": "text"}
        response = requests.get(API_URL, params=params)
        if response.status_code == 200:
            short_link = response.text.strip()
            
            # Rút gọn link dự phòng từ mualink.vip
            fallback_params = {
                "api": "f65ee4fd9659f8ee84ad31cd1c8dd011307cbed0", 
                "url": update.message.text.strip(), 
                "alias": "CustomAlias", 
                "format": "text"
            }
            fallback_response = requests.get(API_FALLBACK_URL, params=fallback_params)
            fallback_link = fallback_response.text.strip() if fallback_response.status_code == 200 else update.message.text.strip()

            message = (
                "📢 <b>Bạn có link rút gọn mới</b>\n"
                f"🔗 <b>Link gốc:</b> <s>{update.message.text}</s>\n"
                f"🔍 <b>Link rút gọn:</b> {short_link}\n"
                f"<b>Link dự phòng:</b> {fallback_link}\n\n"
                '⚠️<b>Kênh xem không cần vượt :</b> <a href="https://t.me/sachkhongchuu/299">ấn vào đây</a>'
            )
            await update.message.reply_text(message, parse_mode="HTML")
        return

    # Bài viết chuyển tiếp
    if (update.message.forward_date or update.message.forward_from or update.message.forward_sender_name) or update.message.caption:
        caption = update.message.caption or ""
        new_caption = await format_text(caption) if mode == "shorten" else caption
        await update.message.copy(chat_id=update.effective_chat.id, caption=new_caption, parse_mode="HTML" if mode == "shorten" else None)

# /setmode → gửi nút chọn
async def set_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    buttons = [
        [InlineKeyboardButton("🔗 Rút gọn link", callback_data="mode_shorten")],
        [InlineKeyboardButton("🆓 Link Free", callback_data="mode_free")]
    ]
    await update.message.reply_text("🔧 Chọn chế độ hoạt động của bot:", reply_markup=InlineKeyboardMarkup(buttons))

# Xử lý callback từ nút
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if query.data == "mode_shorten":
        user_modes[user_id] = "shorten"
        await query.edit_message_text("✅ Bot đã chuyển sang chế độ: Rút gọn link")
    elif query.data == "mode_free":
        user_modes[user_id] = "free"
        await query.edit_message_text("🆓 Bot đã chuyển sang chế độ: Link Free (không rút gọn)")

# Main
def main():
    keep_alive()

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setmode", set_mode))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO | filters.FORWARDED, handle_message))

    print("✅ Bot đang chạy trên Koyeb...")
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
