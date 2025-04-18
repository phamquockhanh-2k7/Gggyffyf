import random
import string
import requests
import time
from telegram import Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import Updater, MessageHandler, Filters, CommandHandler, CallbackContext

BOT_TOKEN = "7851783179:AAGvKfRo42CNyCmd4qUyg0GZ9wKIhDFAJaA"
FIREBASE_URL = "https://bot-telegram-99852-default-rtdb.firebaseio.com/shared"

user_files = {}
user_alias = {}

def generate_alias(length=12):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def start(update: Update, context: CallbackContext):
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
                    update.message.reply_media_group(media_group[i:i+10])
                    time.sleep(1)
            else:
                update.message.reply_text("Không có nội dung để hiển thị.")
        else:
            update.message.reply_text("❌ Không tìm thấy dữ liệu với mã này.")
    else:
        update.message.reply_text("📥 Gửi ảnh hoặc video cho mình. Khi xong thì nhắn /done để lưu và lấy link.")

def handle_media(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    print(f"Nhận media từ user {user_id}")

    if user_id not in user_files:
        user_files[user_id] = []
        user_alias[user_id] = generate_alias()

    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        entry = {"file_id": file_id, "type": "photo"}
        print(f"Đã nhận ảnh: {file_id}")
    elif update.message.video:
        file_id = update.message.video.file_id
        entry = {"file_id": file_id, "type": "video"}
        print(f"Đã nhận video: {file_id}")
    else:
        print("Không phải ảnh hay video")
        return

    if entry not in user_files[user_id]:
        user_files[user_id].append(entry)
        print(f"Đã thêm media vào user_files: {user_files[user_id]}")

def done(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    files = user_files.get(user_id, [])
    alias = user_alias.get(user_id)

    if not files or not alias:
        update.message.reply_text("❌ Bạn chưa gửi ảnh hoặc video nào.")
        return

    url = f"{FIREBASE_URL}/{alias}.json"
    response = requests.put(url, json=files)
    print(f"Firebase response: {response.status_code} - {response.text}")

    if response.status_code == 200:
        link = f"https://t.me/filebotstorage_bot?start={alias}"
        update.message.reply_text(f"✅ Đã lưu thành công!\n🔗 Link truy cập: {link}")
    else:
        update.message.reply_text("❌ Đã có lỗi xảy ra khi lưu dữ liệu.")
    
    del user_files[user_id]
    del user_alias[user_id]

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("done", done))
    dp.add_handler(MessageHandler(Filters.photo | Filters.video, handle_media))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
