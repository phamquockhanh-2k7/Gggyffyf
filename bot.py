import random
import string
import requests
import time
import asyncio
import threading
from flask import Flask
from datetime import datetime, timedelta
from telegram import Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters,
)

# ===== CẤU HÌNH =====
BOT_TOKEN = "8064426886:AAGiR-ghFQNBvOOA-f9rKFGmHySbFMchmDE"
FIREBASE_URL = "https://bot-telegram-99852-default-rtdb.firebaseio.com/shared"
ADMIN_PASSWORD = "191122"

# ===== BIẾN TOÀN CỤC =====
user_files = {}
user_alias = {}
admin_users = {}  # Lưu user_id và thời gian xác minh admin

# ===== HÀM HỖ TRỢ =====
def generate_alias(length=12):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def is_admin(user_id):
    if user_id in admin_users:
        if datetime.now() < admin_users[user_id]:
            return True
        else:
            del admin_users[user_id]  # Hết hạn quyền admin
    return False

# ===== LỆNH /start =====
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

# ===== XỬ LÝ MEDIA =====
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

# ===== LỆNH /done =====
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

# ===== LỆNH /admin =====
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("🛡 Gửi mật khẩu như sau: `/admin 191122`", parse_mode="Markdown")
        return

    password = context.args[0]
    if password == ADMIN_PASSWORD:
        admin_users[user_id] = datetime.now() + timedelta(hours=24)
        await update.message.reply_text("✅ Bạn đã được cấp quyền admin trong 24 giờ.")
    else:
        await update.message.reply_text("❌ Sai mật khẩu.")

# ===== LỆNH /abc =====
async def abc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_admin(user_id):
        await update.message.reply_text("✅ Bạn là admin!")
    else:
        await update.message.reply_text("🚫 Lệnh này chỉ dành cho admin. Dùng /admin để xác minh.")

# ===== FLASK CHO HEALTH CHECK =====
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Bot is running!"

def start_flask():
    app_web.run(host='0.0.0.0', port=8000)

# ===== CHẠY TELEGRAM BOT =====
async def telegram_main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("done", done))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("abc", abc))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, handle_media))

    print("✅ Bot đang chạy...")
    await app.run_polling()

# ===== MAIN =====
if __name__ == '__main__':
    threading.Thread(target=start_flask).start()
    asyncio.run(telegram_main())
