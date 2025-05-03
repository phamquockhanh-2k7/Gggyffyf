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
    """Tạo bí danh ngẫu nhiên và in đậm"""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=12))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    args = context.args
    
    if args:
        try:
            alias = args[0]
            # Sửa lỗi truy vấn Firebase
            response = requests.get(f"{FIREBASE_URL}/{alias}.json").json()
            
            if not response:
                raise ValueError("Không có dữ liệu")
            
            # Chuyển đổi định dạng Firebase dict sang list
            files = [v for k, v in sorted(response.items(), key=lambda x: int(x[0]))]
            
            media_group = []
            for item in files:
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
                
        except Exception as e:
            await update.message.reply_text(f"❌ Lỗi: {str(e)}")
        return
    
    user_sessions[user_id] = []
    await update.message.reply_text("📤 Gửi nội dung và nhấn /done khi xong")

async def handle_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Giữ nguyên phần xử lý nội dung
    # ... (phần này giống code trước)

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    session = user_sessions.pop(user_id, None)
    
    if not session:
        await update.message.reply_text("❌ Chưa có nội dung")
        return
    
    try:
        alias = generate_alias()
        # Lưu dữ liệu dưới dạng dictionary để giữ thứ tự
        data = {str(i): item for i, item in enumerate(session)}
        requests.put(f"{FIREBASE_URL}/{alias}.json", json=data)
        
        bot_username = (await context.bot.get_me()).username
        await update.message.reply_text(
            f"✅ Hoàn tất!\n"
            f"🔗 Link truy cập:\n"
            f"t.me/{bot_username}?start={alias}\n\n"
            f"📌 Bí danh: *`{alias}`*",  # In đậm bí danh
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {str(e)}")

# Phần còn lại giữ nguyên
# ...
