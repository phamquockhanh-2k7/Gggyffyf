import random
import string
import requests
import asyncio
from telegram import Update, InputMediaPhoto, InputMediaVideo, InputMediaDocument
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from keep_alive import keep_alive

BOT_TOKEN = "7728975615:AAEsj_3faSR_97j4-GW_oYnOy1uYhNuuJP0"
FIREBASE_URL = "https://bot-telegram-99852-default-rtdb.firebaseio.com/shared"

user_sessions = {}
media_groups = {}

def generate_alias():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=12))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    args = context.args
    
    if args:
        try:
            alias = args[0]
            response = requests.get(f"{FIREBASE_URL}/{alias}.json").json()
            
            # Xử lý cả 2 trường hợp list và dict
            if isinstance(response, list):
                files = response
            else:
                files = [v for k, v in sorted(response.items(), key=lambda x: int(x[0]))] if response else []
            
            if not files:
                raise ValueError("Nội dung không tồn tại")
            
            media_group = []
            for item in files:
                if item['type'] == 'text':
                    await update.message.reply_text(
                        text=item['file_id'],
                        protect_content=True,
                        disable_web_page_preview=True
                    )
                    continue
                
                media_class = {
                    'photo': InputMediaPhoto,
                    'video': InputMediaVideo,
                    'document': InputMediaDocument
                }[item['type']]
                
                media_group.append(media_class(item['file_id']))
            
            if media_group:
                await update.message.reply_media_group(
                    media=media_group,
                    protect_content=True
                )
            
            await update.message.reply_text(f"📌 Bí danh: <code>{alias}</code>", parse_mode="HTML")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Lỗi: {str(e)}")
        return
    
    user_sessions[user_id] = []
    await update.message.reply_text("📤 Gửi nội dung (ảnh/video/file/text) và nhấn /done khi xong")

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    session = user_sessions.pop(user_id, None)
    
    if not session:
        await update.message.reply_text("❌ Chưa có nội dung")
        return
    
    try:
        alias = generate_alias()
        # Lưu dưới dạng list để tránh lỗi
        response = requests.put(f"{FIREBASE_URL}/{alias}.json", json=session)
        
        if response.status_code != 200:
            raise ConnectionError("Lỗi kết nối Firebase")
            
        bot_username = (await context.bot.get_me()).username
        await update.message.reply_text(
            f"✅ Tạo thành công!\n"
            f"🔗 Link: t.me/{bot_username}?start={alias}\n"
            f"📌 Bí danh: <code>{alias}</code>",
            parse_mode="HTML"  # Sử dụng HTML parse mode
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi hệ thống: {str(e)}")

# Các phần khác giữ nguyên
# ...
