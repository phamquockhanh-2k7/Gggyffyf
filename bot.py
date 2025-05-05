import random
import string
import requests
import asyncio
import logging
from flask import Flask, request, jsonify
from threading import Thread
from telegram import Update, InputMediaPhoto, InputMediaVideo, InlineKeyboardMarkup, InlineKeyboardButton, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
from telegram.error import TelegramError

# Cấu hình logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Cấu hình
BOT_TOKEN = "7728975615:AAEsj_3faSR_97j4-GW_oYnOy1uYhNuuJP0"
FIREBASE_URL = "https://bot-telegram-99852-default-rtdb.firebaseio.com"
PORT = 8000
WEBHOOK_URL = "https://bewildered-wenda-happyboy2k777-413cd6df.koyeb.app"

# Khởi tạo Flask
web_server = Flask(__name__)
user_sessions = {}
media_groups = {}
application = None

def generate_alias():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=12))

async def set_webhook():
    bot = Bot(token=BOT_TOKEN)
    webhook_url = f"{WEBHOOK_URL}/{BOT_TOKEN}"
    try:
        await bot.set_webhook(webhook_url)
        logger.info("Webhook configured successfully")
    except TelegramError as e:
        logger.error(f"Failed to set webhook: {str(e)}")

def save_shared_files(alias, files_data):
    shared_url = f"{FIREBASE_URL}/shared/{alias}.json"
    response = requests.put(shared_url, json=files_data)
    if response.status_code == 200:
        logger.info(f"Alias {alias} saved to /shared")
    else:
        logger.error(f"Failed to save alias {alias} to /shared")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args

    # Kiểm tra và lưu người dùng
    user_url = f"{FIREBASE_URL}/users/{user_id}.json"
    try:
        user_data = requests.get(user_url).json()
        if not user_data:
            requests.put(user_url, json={"joined_at": int(time.time())})
    except requests.RequestException as e:
        logger.error(f"Firebase error: {str(e)}")
        await update.message.reply_text("❌ Lỗi hệ thống, vui lòng thử lại sau")
        return

    if args:
        try:
            alias = args[0]
            response = requests.get(f"{FIREBASE_URL}/shared/{alias}.json").json()

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
                        'video': InputMediaVideo
                    }.get(item['type'])
                    if media_class:
                        media_group.append(media_class(item['file_id']))

            # Gửi text
            for text in text_list:
                try:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=text,
                        protect_content=True,
                        disable_web_page_preview=True
                    )
                except TelegramError as e:
                    logger.error(f"Failed to send message: {str(e)}")

            # Gửi media
            for i in range(0, len(media_group), 10):
                try:
                    await context.bot.send_media_group(
                        chat_id=update.effective_chat.id,
                        media=media_group[i:i+10],
                        protect_content=True
                    )
                    await asyncio.sleep(1)
                except TelegramError as e:
                    logger.error(f"Failed to send media group: {str(e)}")

            await update.message.reply_text(f"📌 Bí danh: <code>{alias}</code>", parse_mode="HTML")

        except Exception as e:
            logger.error(f"Error processing alias: {str(e)}")
            await update.message.reply_text(f"❌ Lỗi: {str(e)}")
        return

    # Giao diện chính
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("📤 Tạo bài viết mới", callback_data="newpost"),
        InlineKeyboardButton("🌐 Truy cập bot", url="https://t.me/filebotstorage_bot")
    ]])
    await update.message.reply_text("👋 Xin chào! Hãy chọn thao tác bên dưới:", reply_markup=keyboard)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "newpost":
        await newpost(update, context)

async def newpost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_sessions[user_id] = []
    await update.message.reply_text("📤 Gửi nội dung (ảnh/video/text) và nhấn /done khi xong")

async def handle_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_sessions:
        return

    if update.message.media_group_id:
        mgid = update.message.media_group_id
        if mgid not in media_groups:
            media_groups[mgid] = []
            asyncio.create_task(process_media_group(mgid, user_id))
        media_groups[mgid].append(update.message)
        return

    content = {}
    if update.message.text and not update.message.text.startswith('/'):
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

        bot_username = (await context.bot.get_me()).username
        await update.message.reply_text(
            f"✅ Tạo thành công!\n"
            f"🔗 Link: https://t.me/{bot_username}?start={alias}\n"
            f"📌 Bí danh: <code>{alias}</code>",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Failed to save post: {str(e)}")
        await update.message.reply_text(f"❌ Lỗi hệ thống: {str(e)}")

@web_server.route(f"/{BOT_TOKEN}", methods=['POST'])
def webhook():
    try:
        json_data = request.get_json()
        if not json_data:
            return jsonify({"status": "error", "message": "Empty data"}), 400
            
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        update = Update.de_json(json_data, application.bot)
        loop.run_until_complete(application.process_update(update))
        loop.close()
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

def create_app():
    global application
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("done", done))
    application.add_handler(CommandHandler("newpost", newpost))
    application.add_handler(CommandHandler("check", check))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO, handle_content))
    
    return application

def run_bot():
    global application
    application = create_app()
    
    # Cấu hình webhook
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(set_webhook())
    loop.close()
    
    # Khởi chạy Flask server
    Thread(target=web_server.run, kwargs={'host':'0.0.0.0','port':PORT}).start()

    logger.info("🤖 Bot is running with webhook...")
    application.run_polling()

if __name__ == '__main__':
    run_bot()
