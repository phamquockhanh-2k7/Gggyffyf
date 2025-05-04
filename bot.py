import random
import string
import requests
import asyncio
from flask import Flask, request
from telegram import Update, InputMediaPhoto, InputMediaVideo, InputMediaDocument, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, Dispatcher, Bot

# Cấu hình
BOT_TOKEN = "7728975615:AAEsj_3faSR_97j4-GW_oYnOy1uYhNuuJP0"
FIREBASE_URL = "https://bot-telegram-99852-default-rtdb.firebaseio.com"
PORT = 8000  # Port bắt buộc cho Koyeb
WEBHOOK_URL = "https://bewildered-wenda-happyboy2k777-413cd6df.koyeb.app/webhook"  # URL webhook

# Khởi tạo Flask
web_server = Flask(__name__)
user_sessions = {}
media_groups = {}

# Khởi tạo bot và dispatcher
bot = Bot(BOT_TOKEN)
dispatcher = Dispatcher(bot, update_queue=None, workers=0, use_context=True)

@web_server.route('/')
def home():
    return "🟢 Bot đang hoạt động"

# Webhook handler
@web_server.route('/webhook', methods=['POST'])
def webhook():
    json_str = request.get_data().decode('UTF-8')
    update = Update.de_json(json_str, bot)
    dispatcher.process_update(update)
    return 'OK'

# Thiết lập webhook
async def set_webhook():
    try:
        await bot.set_webhook(WEBHOOK_URL)
        print("Webhook set successfully.")
    except Exception as e:
        print(f"Error setting webhook: {e}")

async def generate_alias():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=12))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    args = context.args
    user_url = f"{FIREBASE_URL}/users/{user_id}.json"
    user_data = requests.get(user_url).json()

    if not user_data:
        requests.put(user_url, json={})

    if args:
        try:
            alias = args[0]
            response = requests.get(f"{FIREBASE_URL}/{alias}.json").json()
            files = response if isinstance(response, list) else \
                      [v for _, v in sorted(response.items(), key=lambda x: int(x[0]))] if response else []

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

            await update.message.reply_text(f"📌 Bí danh: <code>{alias}</code>", parse_mode="HTML")

        except Exception as e:
            await update.message.reply_text(f"❌ Lỗi: {str(e)}")
        return

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
        alias = await generate_alias()
        response = requests.put(f"{FIREBASE_URL}/{alias}.json", json=session)

        if response.status_code != 200:
            raise ConnectionError("Lỗi kết nối Firebase")

        bot_username = (await context.bot.get_me()).username
        await update.message.reply_text(
            f"✅ Tạo thành công!\n"
            f"🔗 Link: https://t.me/{bot_username}?start={alias}\n"
            f"📌 Bí danh: <code>{alias}</code>",
            parse_mode="HTML"
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi hệ thống: {str(e)}")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        response = requests.get(f"{FIREBASE_URL}/users.json").json()
        
        if response:
            user_count = len(response)
            await update.message.reply_text(f"🧑‍💻 Số lượng người dùng đã lưu: {user_count}")
        else:
            await update.message.reply_text("🚫 Không có người dùng nào.")
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi khi lấy dữ liệu người dùng: {str(e)}")

def run_bot():
    asyncio.run(set_webhook())  # Đặt webhook
    web_server.run(host='0.0.0.0', port=PORT)  # Flask chạy trên Koyeb

if __name__ == '__main__':
    run_bot()
