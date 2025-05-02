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
from keep_alive import keep_alive

nest_asyncio.apply()

BOT_TOKEN = "8064426886:AAE5Zr980N-8LhGgnXGqUXwqlPthvdKA9H0"
API_KEY = "5d2e33c19847dea76f4fdb49695fd81aa669af86"
API_URL = "https://vuotlink.vip/api"
PASSWORD = "2703"

bot = Bot(token=BOT_TOKEN)
media_groups = {}
processing_tasks = {}
user_modes = {}
authenticated_users = set()
awaiting_password = {}  # user_id → chế độ đang chọn

# Format caption
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
        '\n<b>Báo lỗi + đóng góp video tại đây</b> @nothinginthissss\n'
        '<b>Theo dõi thông báo tại đây</b> @linkdinhcaovn\n'
        '<b>CÁCH XEM LINK (nếu lỗi bot không gửi video):</b> @HuongDanVuotLink_SachKhongChu\n\n'
        '⚠️<b>Kênh xem không cần vượt :</b> <a href="https://t.me/linkdinhcaovn/4">ấn vào đây!</a>'
    )

    return "\n".join(new_lines)

# Xử lý nhóm media
async def process_media_group(mgid: str, chat_id: int, mode: str):
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

# Tin nhắn văn bản/ảnh/video
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private" or not update.message:
        return

    user_id = update.effective_user.id

    # Nếu đang chờ mật khẩu
    if user_id in awaiting_password:
        if update.message.text.strip() == PASSWORD:
            user_modes[user_id] = awaiting_password[user_id]
            authenticated_users.add(user_id)
            del awaiting_password[user_id]
            await update.message.reply_text("✅ Mật khẩu đúng. Chế độ đã được kích hoạt.")
        else:
            await update.message.reply_text("❌ Sai mật khẩu. Vui lòng thử lại.")
        return

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
        params = {"api": API_KEY, "url": update.message.text.strip(), "format": "text"}
        response = requests.get(API_URL, params=params)
        if response.status_code == 200:
            short_link = response.text.strip()
            message = (
                "📢 <b>Bạn có link rút gọn mới</b>\n"
                f"🔗 <b>Link gốc:</b> <s>{update.message.text}</s>\n"
                f"🔍 <b>Link rút gọn:</b> {short_link}\n\n"
                '⚠️<b>Kênh xem không cần vượt :</b> <a href="https://t.me/sachkhongchuu/299">ấn vào đây</a>'
            )
            await update.message.reply_text(message, parse_mode="HTML")
        return

    if (update.message.forward_date or update.message.forward_from or update.message.forward_sender_name) or update.message.caption:
        caption = update.message.caption or ""
        new_caption = await format_text(caption) if mode == "shorten" else caption
        await update.message.copy(chat_id=update.effective_chat.id, caption=new_caption, parse_mode="HTML" if mode == "shorten" else None)

# /setmode → chọn chế độ
async def set_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    buttons = [
        [InlineKeyboardButton("🔗 Rút gọn link", callback_data="mode_shorten")],
        [InlineKeyboardButton("🆓 Link Free", callback_data="mode_free")]
    ]
    await update.message.reply_text("🔐 Chọn chế độ. Bạn sẽ cần nhập mật khẩu:", reply_markup=InlineKeyboardMarkup(buttons))

# Nút chọn chế độ
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "mode_shorten":
        awaiting_password[user_id] = "shorten"
    elif query.data == "mode_free":
        awaiting_password[user_id] = "free"

    await query.edit_message_text("🛡 Nhập mật khẩu để xác thực:")

# Không phản hồi lệnh /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return  # Không gửi gì cả

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
