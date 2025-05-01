import requests
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
from telegram.ext import Application, MessageHandler, CommandHandler, CallbackContext, filters, CallbackQueryHandler
import asyncio
import nest_asyncio
import random
from keep_alive import keep_alive

# Cho phép nest_asyncio để tránh xung đột vòng lặp
nest_asyncio.apply()

BOT_TOKEN = "8064426886:AAE5Zr980N-8LhGgnXGqUXwqlPthvdKA9H0"
API_KEY = "5d2e33c19847dea76f4fdb49695fd81aa669af86"
API_URL = "https://vuotlink.vip/api"

bot = Bot(token=BOT_TOKEN)
media_groups = {}
processing_tasks = {}
user_passwords = {}  # Lưu mật khẩu người dùng
user_modes = {}  # Lưu chế độ người dùng (shorten hoặc free)

# Mật khẩu mặc định
DEFAULT_PASSWORD = "2703"

async def start(update: Update, context: CallbackContext):
    if not update.message or update.effective_chat.type != "private":
        return
    await update.message.reply_text(
        "**👋 Chào mừng banj!😍**\n"
        "**🔗 Gửi link bất kỳ để rút gọn.**\n"
        "**📷 Chuyển tiếp bài viết kèm ảnh/video, bot sẽ giữ nguyên caption & rút gọn link trong caption.**\n"
        "**💬 Mọi thắc mắc, hãy liên hệ admin.**",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: CallbackContext):
    user_id = update.effective_user.id

    # Kiểm tra xem người dùng đã nhập mật khẩu chưa
    if user_id not in user_passwords:
        await update.message.reply_text("Vui lòng nhập mật khẩu để tiếp tục sử dụng bot.")
        return

    entered_password = update.message.text.strip()
    
    # Kiểm tra mật khẩu
    if entered_password == DEFAULT_PASSWORD:
        user_passwords[user_id] = DEFAULT_PASSWORD
        await update.message.reply_text("Mật khẩu chính xác! Bot đã được kích hoạt.")
        
        # Sau khi mật khẩu đúng, bot yêu cầu chọn chế độ
        if user_id not in user_modes:
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
        return
    else:
        await update.message.reply_text("Mật khẩu không đúng. Vui lòng thử lại.")
        
async def process_media_group(mgid: str, chat_id: int, mode: str):
    await asyncio.sleep(random.uniform(3, 5))
    group = media_groups.pop(mgid, [])
    if not group:
        await bot.send_message(chat_id=chat_id, text="⚠️ Bài viết không hợp lệ hoặc thiếu ảnh/video.")
        return

    group.sort(key=lambda m: m.message_id)
    caption = await format_text(group[0].caption, mode) if group[0].caption else None
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

async def format_text(text: str, mode: str) -> str:
    lines = text.splitlines()
    new_lines = []
    for line in lines:
        words = line.split()
        new_words = []
        for word in words:
            if word.startswith("http"):
                if mode == "shorten":
                    params = {"api": API_KEY, "url": word, "format": "text"}
                    response = requests.get(API_URL, params=params)
                    short_link = response.text.strip() if response.status_code == 200 else word
                    word = f"<s>{short_link}</s>"
                else:
                    word = f"<a href='{word}'>{word}</a>"
            new_words.append(word)
        new_lines.append(" ".join(new_words))

    # Thêm nội dung cho chế độ shorten
    if mode == "shorten":
        additional_text = (
            "\n\n<b>Báo lỗi + đóng góp video tại đây</b> @nothinginthissss (có lỗi sẽ đền bù)\n"
            "<b>Theo dõi thông báo tại đây</b> @sachkhongchuu\n"
            "<b>CÁCH XEM LINK (lỗi bot không gửi video):</b> @HuongDanVuotLink_SachKhongChu\n\n"
            '⚠️<b>Kênh xem không cần vượt :</b> <a href="https://t.me/sachkhongchuu/299">ấn vào đây</a>'
        )
        new_lines.append(additional_text)

    return "\n".join(new_lines)

async def shorten_link(update: Update, context: CallbackContext):
    user_id = update.effective_user.id

    if user_id not in user_passwords:
        await update.message.reply_text("Vui lòng nhập mật khẩu để tiếp tục sử dụng bot.")
        return

    if user_id not in user_modes:
        await update.message.reply_text("Vui lòng chọn chế độ sử dụng bot trước.")
        return

    mode = user_modes[user_id]

    if update.message.media_group_id:
        mgid = update.message.media_group_id
        if mgid not in media_groups:
            media_groups[mgid] = []
            processing_tasks[mgid] = asyncio.create_task(process_media_group(mgid, update.effective_chat.id, mode))
        media_groups[mgid].append(update.message)
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
        return

    if update.message.forward_origin:
        caption = update.message.caption or ""
        new_caption = await format_text(caption, mode)
        await update.message.copy(chat_id=update.effective_chat.id, caption=new_caption, parse_mode="HTML")

async def set_mode(update: Update, context: CallbackContext):
    user_id = update.effective_user.id

    if user_id not in user_passwords:
        await update.message.reply_text("Vui lòng nhập mật khẩu để tiếp tục sử dụng bot.")
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

async def button(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    mode = query.data
    user_modes[user_id] = mode
    await query.answer()
    await query.edit_message_text(text=f"Chế độ đã được thay đổi thành: {mode}")

def main():
    keep_alive()

    # 1) Khởi tạo và đăng ký handlers
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setmode", set_mode))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, shorten_link))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, shorten_link))
    app.add_handler(CallbackQueryHandler(button))

    print("✅ Bot đang chạy...")

    # 3) Bắt
