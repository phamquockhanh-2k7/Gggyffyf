import random
import string
import requests
import asyncio
from flask import Flask, request
from threading import Thread
from telegram import Update, InputMediaPhoto, InputMediaVideo, InputMediaDocument, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.ext import Defaults
from telegram.ext import CallbackContext
import telegram

BOT_TOKEN = "7728975615:AAEsj_3faSR_97j4-GW_oYnOy1uYhNuuJP0"
FIREBASE_URL = "https://bot-telegram-99852-default-rtdb.firebaseio.com"
APP_URL = "https://bewildered-wenda-happyboy2k777-413cd6df.koyeb.app"  # URL ứng dụng Koyeb của bạn

# Biến toàn cục
user_sessions = {}
media_groups = {}
PORT = 8000

# Tạo Flask app
web_server = Flask(__name__)

@web_server.route("/")
def index():
    return "🟢 Bot Telegram đang chạy bằng webhook!"

@web_server.route("/webhook", methods=["POST"])
def webhook():
    update = telegram.Update.de_json(request.get_json(force=True), bot)
    asyncio.run(application.process_update(update))
    return "ok", 200

def generate_alias():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=12))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    args = context.args

    requests.put(f"{FIREBASE_URL}/users/{user_id}.json", json={})

    if args:
        alias = args[0]
        data = requests.get(f"{FIREBASE_URL}/shared/{alias}.json").json()

        if not data:
            await update.message.reply_text("❌ Không tìm thấy nội dung.")
            return

        files = data if isinstance(data, list) else list(data.values())

        media_group = []
        texts = []

        for item in files:
            if item['type'] == 'text':
                texts.append(item['file_id'])
            else:
                klass = {
                    'photo': InputMediaPhoto,
                    'video': InputMediaVideo,
                    'document': InputMediaDocument
                }[item['type']]
                media_group.append(klass(item['file_id']))

        for text in texts:
            await update.message.reply_text(text=text)

        for i in range(0, len(media_group), 10):
            await update.message.reply_media_group(media_group[i:i+10])
            await asyncio.sleep(1)

        await update.message.reply_text(f"📌 Alias: <code>{alias}</code>", parse_mode="HTML")
        return

    await update.message.reply_text("📥 Gửi ảnh, video, văn bản... Sau đó nhấn /done để tạo liên kết.")

async def handle_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in user_sessions:
        user_sessions[user_id] = []

    if update.message.media_group_id:
        mgid = update.message.media_group_id
        if mgid not in media_groups:
            media_groups[mgid] = []
            asyncio.create_task(process_media_group(mgid, user_id))
        media_groups[mgid].append(update.message)
        return

    msg = update.message
    content = None

    if msg.text:
        content = {'type': 'text', 'file_id': msg.text}
    elif msg.document:
        content = {'type': 'document', 'file_id': msg.document.file_id}
    elif msg.photo:
        content = {'type': 'photo', 'file_id': msg.photo[-1].file_id}
    elif msg.video:
        content = {'type': 'video', 'file_id': msg.video.file_id}

    if content:
        user_sessions[user_id].append(content)

async def process_media_group(mgid, user_id):
    await asyncio.sleep(2)
    group = media_groups.pop(mgid, [])
    group.sort(key=lambda x: x.message_id)
    for msg in group:
        if msg.photo:
            user_sessions[user_id].append({'type': 'photo', 'file_id': msg.photo[-1].file_id})
        elif msg.video:
            user_sessions[user_id].append({'type': 'video', 'file_id': msg.video.file_id})

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    session = user_sessions.pop(user_id, None)

    if not session:
        await update.message.reply_text("❌ Bạn chưa gửi nội dung nào.")
        return

    alias = generate_alias()
    requests.put(f"{FIREBASE_URL}/shared/{alias}.json", json=session)
    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={alias}"
    await update.message.reply_text(f"✅ Đã tạo link: {link}\n📌 Alias: <code>{alias}</code>", parse_mode="HTML")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    res = requests.get(f"{FIREBASE_URL}/users.json").json()
    count = len(res) if res else 0
    await update.message.reply_text(f"👥 Số người dùng đã ghi nhận: {count}")

def run_flask():
    web_server.run(host="0.0.0.0", port=PORT)

# --- Khởi tạo bot ---
application = Application.builder().token(BOT_TOKEN).build()
bot = telegram.Bot(BOT_TOKEN)

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("done", done))
application.add_handler(CommandHandler("check", check))
application.add_handler(MessageHandler(filters.ALL, handle_content))

# --- Thiết lập webhook ---
async def set_webhook():
    await bot.set_webhook(url=f"{APP_URL}/webhook")

if __name__ == "__main__":
    Thread(target=run_flask).start()
    asyncio.run(set_webhook())
    await update.message.reply_text("📥 Gửi ảnh, video, văn bản... Sau đó nhấn /done để tạo liên kết.")

async def handle_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in user_sessions:
        user_sessions[user_id] = []

    if update.message.media_group_id:
        mgid = update.message.media_group_id
        if mgid not in media_groups:
            media_groups[mgid] = []
            asyncio.create_task(process_media_group(mgid, user_id))
        media_groups[mgid].append(update.message)
        return

    msg = update.message
    content = None

    if msg.text:
        content = {'type': 'text', 'file_id': msg.text}
    elif msg.document:
        content = {'type': 'document', 'file_id': msg.document.file_id}
    elif msg.photo:
        content = {'type': 'photo', 'file_id': msg.photo[-1].file_id}
    elif msg.video:
        content = {'type': 'video', 'file_id': msg.video.file_id}

    if content:
        user_sessions[user_id].append(content)

async def process_media_group(mgid, user_id):
    await asyncio.sleep(2)
    group = media_groups.pop(mgid, [])
    group.sort(key=lambda x: x.message_id)
    for msg in group:
        if msg.photo:
            user_sessions[user_id].append({'type': 'photo', 'file_id': msg.photo[-1].file_id})
        elif msg.video:
            user_sessions[user_id].append({'type': 'video', 'file_id': msg.video.file_id})

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    session = user_sessions.pop(user_id, None)

    if not session:
        await update.message.reply_text("❌ Bạn chưa gửi nội dung nào.")
        return

    alias = generate_alias()
    requests.put(f"{FIREBASE_URL}/shared/{alias}.json", json=session)
    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={alias}"
    await update.message.reply_text(f"✅ Đã tạo link: {link}\n📌 Alias: <code>{alias}</code>", parse_mode="HTML")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    res = requests.get(f"{FIREBASE_URL}/users.json").json()
    count = len(res) if res else 0
    await update.message.reply_text(f"👥 Số người dùng đã ghi nhận: {count}")

def run_flask():
    web_server.run(host="0.0.0.0", port=PORT)

# --- Khởi tạo bot ---
application = Application.builder().token(BOT_TOKEN).build()
bot = telegram.Bot(BOT_TOKEN)

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("done", done))
application.add_handler(CommandHandler("check", check))
application.add_handler(MessageHandler(filters.ALL, handle_content))

# --- Thiết lập webhook ---
async def set_webhook():
    await bot.set_webhook(url=f"{APP_URL}/webhook")

if __name__ == "__main__":
    Thread(target=run_flask).start()
    asyncio.run(set_webhook())
