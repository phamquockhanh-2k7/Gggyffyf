import random
import string
import requests
import asyncio
from flask import Flask
from threading import Thread
from telegram import Update, InputMediaPhoto, InputMediaVideo, InputMediaDocument, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# Cấu hình
BOT_TOKEN = "7728975615:AAEsj_3faSR_97j4-GW_oYnOy1uYhNuuJP0"
FIREBASE_URL = "https://bot-telegram-99852-default-rtdb.firebaseio.com"
PORT = 8000  # Port bắt buộc cho Koyeb

# Khởi tạo Flask
web_server = Flask(__name__)
user_sessions = {}
media_groups = {}

@web_server.route('/')
def home():
    return "🟢 Bot đang hoạt động"

def generate_alias():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=12))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    args = context.args

    # Lưu ID người dùng vào Firebase nếu chưa tồn tại
    user_url = f"{FIREBASE_URL}/users/{user_id}.json"
    user_data = requests.get(user_url).json()

    if not user_data:
        # Nếu ID chưa có trong Firebase, tạo mới
        requests.put(user_url, json={})

    if args:
        try:
            alias = args[0]
            response = requests.get(f"{FIREBASE_URL}/shared/{alias}.json").json()

            files = response if isinstance(response, list) else \
                      [v for _,v in sorted(response.items(), key=lambda x: int(x[0]))] if response else []

            if not files:
                raise ValueError("Nội dung không tồn tại")

            text_list = []
            media_group = []

            for item in files:
                if item['type'] == 'text':
                    text_list.append(item['file_id'])
                else:
                    media_class = {
                        'photo': InputMediaPhoto,
                        'video': InputMediaVideo,
                        'document': InputMediaDocument
                    }[item['type']]
                    media_group.append(media_class(item['file_id']))

            # Gửi text nếu có
            for text in text_list:
                await update.message.reply_text(
                    text=text,
                    protect_content=True,
                    disable_web_page_preview=True
                )

            # Gửi media theo nhóm 10
            for i in range(0, len(media_group), 10):
                await update.message.reply_media_group(
                    media=media_group[i:i+10],
                    protect_content=True
                )
                await asyncio.sleep(1)

            await update.message.reply_text(f"📌 Bí danh: <code>{alias}</code>", parse_mode="HTML")

        except Exception as e:
            await update.message.reply_text(f"❌ Lỗi: {str(e)}")
        return

    # Nếu không có alias
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("📤 Tạo bài viết mới", callback_data="newpost"),
        InlineKeyboardButton("🌐 Truy cập bot", url="https://t.me/filebotstorage_bot")
    ]])
    await update.message.reply_text("👋 Xin chào! Hãy chọn thao tác bên dưới:", reply_markup=keyboard)

async def newpost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_sessions[user_id] = []
    await update.message.reply_text("📤 Gửi nội dung (ảnh/video/file/text) và nhấn /done khi xong")

async def handle_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
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
    elif update.message.document:
        content = {'type': 'document', 'file_id': update.message.document.file_id}
    elif update.message.photo:
        content = {'type': 'photo', 'file_id': update.message.photo[-1].file_id}
    elif update.message.video:
        content = {'type': 'video', 'file_id': update.message.video.file_id}

    if content:
        user_sessions[user_id].append(content)
        await update.message.reply_text("✅ Đã lưu. Tiếp tục hoặc /done")

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
    user_id = update.message.from_user.id
    session = user_sessions.pop(user_id, None)

    if not session:
        await update.message.reply_text("❌ Chưa có nội dung")
        return

    try:
        alias = generate_alias()

        # Lưu nội dung vào "shared" với bí danh
        response = requests.put(f"{FIREBASE_URL}/shared/{alias}.json", json=session)

        if response.status_code != 200:
            raise ConnectionError("Lỗi kết nối Firebase")

        # Lưu ID người dùng vào "users"
        user_url = f"{FIREBASE_URL}/users/{user_id}/file/{alias}.json"
        requests.put(user_url, json={"file_id": alias, "type": "shared"})

        bot_username = (await context.bot.get_me()).username
        await update.message.reply_text(
            f"✅ Tạo thành công!\n"
            f"🔗 Link: https://t.me/{bot_username}?start={alias}\n"
            f"📌 Bí danh: <code>{alias}</code>",
            parse_mode="HTML"
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi hệ thống: {str(e)}")

def run_bot():
    Thread(target=web_server.run, kwargs={'host':'0.0.0.0','port':PORT}).start()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("done", done))
    app.add_handler(CommandHandler("newpost", newpost))  # lệnh ẩn không gợi ý
    app.add_handler(MessageHandler(filters.ALL, handle_content))

    print("🤖 Bot đang hoạt động...")
    app.run_polling()

if __name__ == '__main__':
    run_bot()
