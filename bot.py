import random
import string
import requests
import asyncio
from flask import Flask, request
from threading import Thread
from telegram import Update, InputMediaPhoto, InputMediaVideo, InlineKeyboardMarkup, InlineKeyboardButton, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# Cấu hình
BOT_TOKEN = "7728975615:AAEsj_3faSR_97j4-GW_oYnOy1uYhNuuJP0"
FIREBASE_URL = "https://bot-telegram-99852-default-rtdb.firebaseio.com"
PORT = 8000
WEBHOOK_URL = "https://bewildered-wenda-happyboy2k777-413cd6df.koyeb.app"

# Khởi tạo Flask
web_server = Flask(__name__)
user_sessions = {}
media_groups = {}

# Khởi tạo Telegram Application
application = Application.builder().token(BOT_TOKEN).build()

def generate_alias():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=12))

def save_user_file(user_id, file_id, file_type):
    url = f"{FIREBASE_URL}/users/{user_id}/files.json"
    try:
        res = requests.get(url)
        files = res.json() or {}
        new_index = len(files)
    except:
        new_index = 0

    data = {
        "file_id": file_id,
        "type": file_type
    }
    requests.patch(f"{FIREBASE_URL}/users/{user_id}/files.json", json={str(new_index): data})

def save_shared_files(alias, files_data):
    shared_url = f"{FIREBASE_URL}/shared/{alias}.json"
    response = requests.put(shared_url, json=files_data)
    if response.status_code != 200:
        print("Lỗi khi lưu alias vào /shared")

# Các handler functions
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Giữ nguyên nội dung hàm start của bạn

async def newpost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Giữ nguyên nội dung hàm newpost

async def handle_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Giữ nguyên nội dung hàm handle_content

async def process_media_group(mgid: str, user_id: int):
    # Giữ nguyên nội dung hàm process_media_group

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Giữ nguyên nội dung hàm done

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Giữ nguyên nội dung hàm check

# Đăng ký các handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("check", check))
application.add_handler(CommandHandler("done", done))
application.add_handler(CommandHandler("newpost", newpost))
application.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO, handle_content))

@web_server.route('/')
def home():
    return "🟢 Bot đang hoạt động"

@web_server.route(f"/{BOT_TOKEN}", methods=['POST'])
def telegram_webhook():
    json_str = request.get_data().decode('UTF-8')
    update = Update.de_json(json_str, application.bot)
    application.update_queue.put(update)
    return 'OK'

async def set_webhook():
    await application.bot.set_webhook(f"{WEBHOOK_URL}/{BOT_TOKEN}")

def run_flask():
    web_server.run(host='0.0.0.0', port=PORT)

async def main():
    await set_webhook()
    print("Webhook đã được cấu hình thành công")
    
    # Chạy Flask trong một thread riêng
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Bắt đầu xử lý các update
    await application.start()
    await asyncio.Event().wait()  # Chặn chương trình chính

if __name__ == '__main__':
    asyncio.run(main())
