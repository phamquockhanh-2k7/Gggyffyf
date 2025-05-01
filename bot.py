import requests
from telegram import Bot, Update, InputMediaPhoto, InputMediaVideo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, CommandHandler, CallbackContext, CallbackQueryHandler, filters
import asyncio
import nest_asyncio
import random
from keep_alive import keep_alive
import time

# Cho phép nest_asyncio để tránh xung đột vòng lặp
nest_asyncio.apply()

BOT_TOKEN = "8064426886:AAE5Zr980N-8LhGgnXGqUXwqlPthvdKA9H0"
API_KEY = "5d2e33c19847dea76f4fdb49695fd81aa669af86"
API_URL = "https://vuotlink.vip/api"

bot = Bot(token=BOT_TOKEN)
media_groups = {}
processing_tasks = {}
user_modes = {}
user_passwords = {}

# Lưu thời gian reset mật khẩu
password_reset_time = {}

async def start(update: Update, context: CallbackContext):
    if not update.message or update.effective_chat.type != "private":
        return
    keyboard = [
        [
            InlineKeyboardButton("Rút gọn link", callback_data='shorten'),
            InlineKeyboardButton("Link Free", callback_data='free')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Chọn chế độ sử dụng bot:",
        reply_markup=reply_markup
    )

async def handle_mode_selection(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = update.effective_user.id
    mode = query.data
    
    # Lưu chế độ của người dùng
    if mode == "shorten":
        user_modes[user_id] = "shorten"
        await query.answer(text="Bạn đã chọn chế độ 'Rút gọn link'.")
    elif mode == "free":
        user_modes[user_id] = "free"
        await query.answer(text="Bạn đã chọn chế độ 'Link Free'.")

    # Sau khi chọn chế độ, yêu cầu mật khẩu
    await query.message.reply_text("Hãy nhập mật khẩu để sử dụng bot. Chi tiết liên hệ: @nothinginthissss")

async def handle_message(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    mode = user_modes.get(user_id, None)

    # Kiểm tra mật khẩu
    if user_id not in user_passwords:
        await update.message.reply_text("Vui lòng nhập mật khẩu để tiếp tục sử dụng bot.")
        return

    entered_password = update.message.text.strip()
    if entered_password != "2703":
        await update.message.reply_text("Mật khẩu không đúng. Vui lòng thử lại.")
        return

    # Kiểm tra chế độ
    if mode == "shorten":
        await shorten_link(update, context)
    elif mode == "free":
        await free_link(update, context)
    else:
        await update.message.reply_text("Chưa chọn chế độ. Vui lòng sử dụng lệnh /start để bắt đầu.")

async def shorten_link(update: Update, context: CallbackContext):
    if not update.message or update.effective_chat.type != "private":
        return

    if update.message.text and update.message.text.startswith("http"):
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

async def free_link(update: Update, context: CallbackContext):
    if not update.message or update.effective_chat.type != "private":
        return

    if update.message.text and update.message.text.startswith("http"):
        message = (
            "📢 <b>Bạn có link gốc</b>\n"
            f"🔗 <b>Link gốc:</b> {update.message.text}\n\n"
            '⚠️<b>Kênh xem không cần vượt :</b> <a href="https://t.me/sachkhongchuu/299">ấn vào đây</a>'
        )
        await update.message.reply_text(message, parse_mode="HTML")

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
        '<b>Theo dõi thông báo tại đây</b> @linkdinhcaovn\n'
        '<b>CÁCH XEM LINK(lỗi bot không gửi video):</b> @HuongDanVuotLink_SachKhongChu\n\n'
        '⚠️<b>Kênh xem không cần vượt :</b> <a href="https://t.me/linkdinhcaovn/4">ấn vào đây!</a>'
    )

    return "\n".join(new_lines)

async def process_media_group(mgid: str, chat_id: int):
    await asyncio.sleep(random.uniform(3, 5))
    group = media_groups.pop(mgid, [])
    if not group:
        await bot.send_message(chat_id=chat_id, text="⚠️ Bài viết không hợp lệ hoặc thiếu ảnh/video.")
        return

    group.sort(key=lambda m: m.message_id)
    caption = await format_text(group[0].caption) if group[0].caption else None
    media = []

    for i, msg in enumerate(group):
        if msg.photo:
            file_id = msg.photo[-1].file_id
            media.append(InputMediaPhoto(file_id, caption=caption if i == 0 else None, parse_mode="HTML"))
        elif msg.video:
            file_id = msg.video.file_id
            media.append(InputMediaVideo(file_id, caption=caption if i == 0 else None, parse_mode="HTML"))

    if not media:
        await bot.send_message(chat_id=chat_id, text="⚠️ Bài viết không có ảnh hoặc video hợp lệ.")
        return

    try:
        await bot.send_media_group(chat_id=chat_id, media=media)
    except Exception as e:
        print(f"Lỗi khi gửi media_group: {e}")
        await bot.send_message(chat_id=chat_id, text="⚠️ Gửi bài viết thất bại. Có thể do file lỗi hoặc Telegram bị giới hạn.")

async def set_password(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    entered_password = update.message.text.strip()

    if entered_password == "2703":
        user_passwords[user_id] = "2703"
        await update.message.reply_text("Mật khẩu chính xác! Bot đã được kích hoạt.")
        # Lưu thời gian mật khẩu được đặt lại
        password_reset_time[user_id] = time.time()
    else:
        await update.message.reply_text("Mật khẩu không đúng. Vui lòng thử lại.")

def main():
    # 1) Giữ bot luôn "sống" qua Flask
    keep_alive()

    # 2) Khởi tạo và đăng ký handlers
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_mode_selection))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.TEXT & filters.COMMAND, set_password))

    print("✅ Bot đang chạy...haha")

    # 3) Bắt đầu polling, không đóng loop khi kết thúc
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
