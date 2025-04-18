import random
import string
import requests
import time
import asyncio
import threading
from flask import Flask
from telegram import Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters,
)

# Cấu hình bot
BOT_TOKEN = "7851783179:AAGvKfRo42CNyCmd4qUyg0GZ9wKIhDFAJaA"
FIREBASE_URL = "https://bot-telegram-99852-default-rtdb.firebaseio.com/shared"

# Biến toàn cục
user_files = {}
user_alias = {}

# Hàm tạo alias ngẫu nhiên
def generate_alias(length=12):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if args:
        alias = args[0]
        url = f"{FIREBASE_URL}/{alias}.json"
        res = requests.get(url)
        if res.status_code == 200 and res.json():
            media_items = res.json()
            media_group = []
            for item in media_items:
                if item["type"] == "photo":
                    media_group.append(InputMediaPhoto(item["file_id"]))
                elif item["type"] == "video":
                    media_group.append(InputMediaVideo(item["file_id"]))
            if media_group:
                for i in range(0, len(media_group), 10):
                    await update.message.reply_media_group(media_group[i:i+10])
                    await asyncio.sleep(1)
            else:
                await update.message.reply_text("Không có nội dung để hiển thị.")
        else:
            await update.message.reply_text("❌ Không tìm thấy dữ liệu với mã này.")
    else:
        await update.message.reply_text("📥 Gửi ảnh hoặc video cho mình. Khi xong thì nhắn /done để lưu và lấy link.")

# Xử lý media
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_files:
        user_files[user_id] = []
        user_alias[user_id] = generate_alias()

    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        entry = {"file_id": file_id, "type": "photo"}
    elif update.message.video:
        file_id = update.message.video.file_id
        entry = {"file_id": file_id, "type": "video"}
    else:
        return

    if entry not in user_files[user_id]:
        user_files[user_id].append(entry)

# /done
async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    files = user_files.get(user_id, [])
    alias = user_alias.get(user_id)

    if not files or not alias:
        await update.message.reply_text("❌ Bạn chưa gửi ảnh hoặc video nào.")
        return

    url = f"{FIREBASE_URL}/{alias}.json"
    response = requests.put(url, json=files)

    if response.status_code == 200:
        link = f"https://t.me/filebotstorage_bot?start={alias}"
        await update.message.reply_text(f"✅ Đã lưu thành công!\n🔗 Link truy cập: {link}")
    else:
        await update.message.reply_text("❌ Đã có lỗi xảy ra khi lưu dữ liệu.")

    del user_files[user_id]
    del user_alias[user_id]

# Flask web server (cho health check)
app_web = Flask('')

@app_web.route('/')
def home():
    return "Bot is running!"

def start_flask():
    app_web.run(host='0.0.0.0', port=8000)

# Chạy Telegram bot
async def telegram_main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("done", done))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, handle_media))

    print("Bot đang chạy...")
    await app.run_polling()

# Main entry
if __name__ == '__main__':
    threading.Thread(target=start_flask).start()

    loop = asyncio.get_event_loop()
    if loop.is_running():
        asyncio.ensure_future(telegram_main())
    else:
        loop.run_until_complete(telegram_main())
