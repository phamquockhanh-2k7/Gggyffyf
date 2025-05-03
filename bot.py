import requests
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# URL API
MUALINK_API_URL = "https://mualink.vip/api"
VUOTLINK_API_URL = "https://vuotlink.vip/api"

# API Key (thay đổi giá trị này theo nhu cầu)
MUALINK_API_KEY = "f65ee4fd9659f8ee84ad31cd1c8dd011307cbed0"
VUOTLINK_API_KEY = "5d2e33c19847dea76f4fdb49695fd81aa669af86"  # Thay bằng API Key của bạn

# API Token của bot Telegram
BOT_TOKEN = "8064426886:AAFAWxoIKjiyTGG_DxcXFXDUizHZyANldE4"  # Thay bằng token của bạn

# Các danh sách cần thiết cho việc xác thực và lưu trữ dữ liệu
authenticated_users = set()  # Lưu trữ các user_id đã xác thực
user_modes = {}  # Lưu trữ chế độ người dùng (shorten hoặc khác)
media_groups = {}  # Lưu trữ các nhóm media để xử lý theo đúng thứ tự
processing_tasks = {}  # Lưu trữ các task đang xử lý

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

# Hàm xử lý text, có thể được sử dụng để format caption hoặc tin nhắn
async def format_text(caption: str) -> str:
    # Giả sử đây là một hàm xử lý văn bản (nếu cần định dạng thêm)
    # Có thể thêm các xử lý như thay đổi text, thêm tag, v.v.
    return caption

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

    # Xử lý media group
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

# Hàm xử lý media group (ví dụ: khi nhận nhiều ảnh/video cùng lúc)
async def process_media_group(mgid: str, chat_id: int, mode: str):
    messages = media_groups[mgid]
    for message in messages:
        if message.text and message.text.startswith("http") and mode == "shorten":
            short_link_mualink = await shorten_link_mualink(message.text.strip())
            short_link_vuotlink = await shorten_link_vuotlink(message.text.strip())

            message_text = (
                f"🔗 <b>Link gốc:</b> <s>{message.text}</s>\n"
                f"🔍 <b>Link rút gọn mualink:</b> {short_link_mualink}\n"
                f"🔍 <b>Link rút gọn vuotlink:</b> {short_link_vuotlink}\n\n"
                '⚠️<b>Kênh xem không cần vượt :</b> <a href="https://t.me/sachkhongchuu/299">ấn vào đây</a>'
            )
            await context.bot.send_message(chat_id=chat_id, text=message_text, parse_mode="HTML")

# Command để xác thực người dùng
async def set_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    authenticated_users.add(user_id)
    user_modes[user_id] = "shorten"
    await update.message.reply_text("🔐 Bạn đã được xác thực. Sử dụng /send để bắt đầu.")

# Command để xử lý gửi tin nhắn
async def send_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in authenticated_users:
        await update.message.reply_text("🔐 Bạn chưa xác thực. Gõ /setmode để bắt đầu.")
        return
    
    await update.message.reply_text("📨 Bạn có thể gửi tin nhắn hoặc media, bot sẽ tự động rút gọn link.")

# Thiết lập và chạy bot
def main():
    application = Application.builder().token(BOT_TOKEN).build()  # Sử dụng token bot từ biến

    # Các command handler
    application.add_handler(CommandHandler("setmode", set_mode))
    application.add_handler(CommandHandler("send", send_message))
    
    # Handler cho các tin nhắn văn bản và media
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.VOICE, handle_message))

    # Chạy bot
    application.run_polling()

if __name__ == "__main__":
    main()
