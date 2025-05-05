import random
import string
import requests
import asyncio
from flask import Flask, request
from threading import Thread
import time

from telegram import Update, InputMediaPhoto, InputMediaVideo, InlineKeyboardMarkup, InlineKeyboardButton, Bot
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

# Cấu hình
BOT_TOKEN    = "7728975615:AAEsj_3faSR_97j4-GW_oYnOy1uYhNuuJP0"
FIREBASE_URL = "https://bot-telegram-99852-default-rtdb.firebaseio.com"
PORT         = 8000  # Port bắt buộc cho Koyeb
WEBHOOK_URL  = "https://bewildered-wenda-happyboy2k777-413cd6df.koyeb.app"

# Khởi tạo Flask và lưu session
web_server    = Flask(__name__)
user_sessions = {}
media_groups  = {}

# Tạo application toàn cục để dùng cả trong webhook và run_bot
application = Application.builder().token(BOT_TOKEN).build()

@web_server.route('/')
def home():
    return "🟢 Bot đang hoạt động"

def generate_alias():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=12))

def set_webhook():
    bot = Bot(token=BOT_TOKEN)
    webhook_url = f"{WEBHOOK_URL}/{BOT_TOKEN}"
    if bot.set_webhook(webhook_url):
        print("Webhook đã được cấu hình thành công")
    else:
        print("Không thể cấu hình webhook")

def save_user_file(user_id, file_id, file_type):
    url = f"{FIREBASE_URL}/users/{user_id}/files.json"
    try:
        res = requests.get(url)
        files = res.json() or {}
        new_index = len(files)
    except:
        new_index = 0
    data = {"file_id": file_id, "type": file_type}
    requests.patch(url, json={str(new_index): data})

def save_shared_files(alias, files_data):
    shared_url = f"{FIREBASE_URL}/shared/{alias}.json"
    response = requests.put(shared_url, json=files_data)
    if response.status_code != 200:
        print("Lỗi khi lưu alias vào /shared")
    else:
        print(f"Alias {alias} đã được lưu vào /shared")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args

    # đảm bảo user đã có entry trong Firebase
    user_url  = f"{FIREBASE_URL}/users/{user_id}.json"
    user_data = requests.get(user_url).json()
    if not user_data:
        requests.put(user_url, json={})

    if args:
        alias    = args[0]
        response = requests.get(f"{FIREBASE_URL}/shared/{alias}.json").json()
        files = (response if isinstance(response, list)
                 else [v for _, v in sorted(response.items(), key=lambda x: int(x[0]))]
                 if response else [])
        if not files:
            await update.message.reply_text("❌ Nội dung không tồn tại")
            return

        text_list  = []
        media_group = []

        for item in files:
            if item['type'] == 'text':
                text_list.append(item['file_id'])
            else:
                cls = {'photo': InputMediaPhoto, 'video': InputMediaVideo}[item['type']]
                media_group.append(cls(item['file_id']))

        for text in text_list:
            await update.message.reply_text(
                text=text,
                protect_content=True,
                disable_web_page_preview=True
            )

        for i in range(0, len(media_group), 10):
            await update.message.reply_media_group(
                media=media_group[i:i+10],
                protect_content=True
            )
            await asyncio.sleep(1)

        await update.message.reply_text(
            f"📌 Bí danh: <code>{alias}</code>",
            parse_mode="HTML"
        )
        return

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("📤 Tạo bài viết mới", callback_data="newpost"),
        InlineKeyboardButton("🌐 Truy cập bot", url="https://t.me/filebotstorage_bot")
    ]])
    await update.message.reply_text(
        "👋 Xin chào! Hãy chọn thao tác bên dưới:",
        reply_markup=keyboard
    )

async def newpost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_sessions[user_id] = []

    # nếu từ callback query
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(
            "📤 Gửi nội dung (ảnh/video) và nhấn /done khi xong"
        )
    else:
        await update.message.reply_text(
            "📤 Gửi nội dung (ảnh/video) và nhấn /done khi xong"
        )

async def handle_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_sessions:
        await start(update, context)
        return

    if update.message.media_group_id:
        mgid = update.message.media_group_id
        if mgid not in media_groups:
            media_groups[mgid] = []
            asyncio.create_task(process_media_group(mgid, user_id))
        media_groups[mgid].append(update.message)
        return

    content = {}
    if update.message.text:
        content = {'type': 'text', 'file_id': update.message.text}
    elif update.message.photo:
        content = {'type': 'photo', 'file_id': update.message.photo[-1].file_id}
    elif update.message.video:
        content = {'type': 'video', 'file_id': update.message.video.file_id}

    if content:
        user_sessions[user_id].append(content)

async def process_media_group(mgid: str, user_id: int):
    await asyncio.sleep(2)
    group = sorted(media_groups.pop(mgid, []), key=lambda x: x.message_id)
    for msg in group:
        if msg.photo:
            user_sessions[user_id].append({
                'type': 'photo',
                'file_id': msg.photo[-1].file_id
            })
        elif msg.video:
            user_sessions[user_id].append({
                'type': 'video',
                'file_id': msg.video.file_id
            })

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = user_sessions.pop(user_id, None)
    if not session:
        await update.message.reply_text("❌ Chưa có nội dung")
        return

    try:
        alias = generate_alias()
        save_shared_files(alias, session)
        resp = requests.put(
            f"{FIREBASE_URL}/users/{user_id}/files/{alias}.json",
            json=session
        )
        if resp.status_code != 200:
            raise ConnectionError("Lỗi kết nối Firebase")

        bot_username = (await context.bot.get_me()).username
        await update.message.reply_text(
            f"✅ Tạo thành công!\n"
            f"🔗 Link: https://t.me/{bot_username}?start={alias}\n"
            f"📌 Bí danh: <code>t.me/upbaiviet_bot?start={alias}</code>",
            parse_mode="HTML"
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi hệ thống: {e}")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        response = requests.get(f"{FIREBASE_URL}/users.json").json()
        if response:
            await update.message.reply_text(f"🧑‍💻 Số lượng người dùng đã lưu: {len(response)}")
        else:
            await update.message.reply_text("🚫 Không có người dùng nào.")
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi khi lấy dữ liệu người dùng: {e}")

@web_server.route(f"/{BOT_TOKEN}", methods=['POST'])
def webhook():
    json_str = request.get_data().decode('UTF-8')
    update   = Update.de_json(json_str, Bot(token=BOT_TOKEN))
    application.process_update(update)
    return 'OK'

def run_bot():
    set_webhook()
    # Chạy Flask trên host 0.0.0.0 và port định sẵn
    Thread(target=lambda: web_server.run(host="0.0.0.0", port=PORT)).start()
    # Giữ chương trình không exit
    while True:
        time.sleep(10)

# Đăng ký các handler (bao gồm cả callback query)
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(newpost, pattern="^newpost$"))
application.add_handler(CommandHandler("newpost", newpost))
application.add_handler(CommandHandler("check", check))
application.add_handler(CommandHandler("done", done))
application.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO, handle_content))

if __name__ == '__main__':
    run_bot()
