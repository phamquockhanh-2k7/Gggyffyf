import random
import string
import requests
import asyncio
from telegram import Update, InputMediaPhoto, InputMediaVideo, InputMediaDocument
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from keep_alive import keep_alive

# Cấu hình
BOT_TOKEN = "7728975615:AAEsj_3faSR_97j4-GW_oYnOy1uYhNuuJP0"
FIREBASE_URL = "https://bot-telegram-99852-default-rtdb.firebaseio.com/shared"

# Biến toàn cục
user_sessions = {}
media_groups = {}

def generate_alias():
    """Tạo bí danh ngẫu nhiên 12 ký tự"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=12))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý lệnh /start"""
    user_id = update.message.from_user.id
    args = context.args
    
    if args:
        try:
            alias = args[0]
            response = requests.get(f"{FIREBASE_URL}/{alias}.json").json()
            
            if not response:
                raise ValueError("Nội dung không tồn tại")
            
            # Chuyển đổi dữ liệu Firebase
            sorted_items = sorted(response.items(), key=lambda x: int(x[0]))
            files = [item[1] for item in sorted_items]
            
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
            
            await update.message.reply_text(f"📌 Bí danh: `{alias}`", parse_mode="Markdown")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Lỗi: {str(e)}")
        return
    
    user_sessions[user_id] = []
    await update.message.reply_text("📤 Gửi nội dung (ảnh/video/file/text) và nhấn /done khi xong")

async def handle_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý mọi loại nội dung"""
    user_id = update.message.from_user.id
    if user_id not in user_sessions:
        await start(update, context)
        return

    # Xử lý media group
    if update.message.media_group_id:
        mgid = update.message.media_group_id
        if mgid not in media_groups:
            media_groups[mgid] = []
            asyncio.create_task(process_media_group(mgid, user_id))
        media_groups[mgid].append(update.message)
        return
    
    # Xử lý từng loại nội dung
    content = {}
    
    if update.message.text:
        content = {
            'type': 'text',
            'file_id': update.message.text
        }
    elif update.message.document:
        content = {
            'type': 'document',
            'file_id': update.message.document.file_id
        }
    elif update.message.photo:
        content = {
            'type': 'photo',
            'file_id': update.message.photo[-1].file_id
        }
    elif update.message.video:
        content = {
            'type': 'video',
            'file_id': update.message.video.file_id
        }
    
    if content:
        user_sessions[user_id].append(content)
        await update.message.reply_text("✅ Đã lưu. Tiếp tục gửi hoặc /done")

async def process_media_group(mgid: str, user_id: int):
    """Xử lý nhóm media"""
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
    """Hoàn tất quá trình lưu"""
    user_id = update.message.from_user.id
    session = user_sessions.pop(user_id, None)
    
    if not session:
        await update.message.reply_text("❌ Chưa có nội dung")
        return
    
    try:
        alias = generate_alias()
        data = {str(i): item for i, item in enumerate(session)}
        response = requests.put(f"{FIREBASE_URL}/{alias}.json", json=data)
        
        if response.status_code != 200:
            raise ConnectionError("Lỗi kết nối Firebase")
            
        bot_username = (await context.bot.get_me()).username
        await update.message.reply_text(
            f"✅ Tạo thành công!\n"
            f"🔗 Link truy cập:\n"
            f"t.me/{bot_username}?start={alias}\n\n"
            f"📌 Bí danh: `{alias}`",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi hệ thống: {str(e)}")

def run_bot():
    """Khởi chạy ứng dụng"""
    keep_alive()
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Đăng ký handler
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("done", done))
    app.add_handler(MessageHandler(filters.ALL, handle_content))
    
    print("🤖 Bot đang hoạt động...")
    app.run_polling()

if __name__ == '__main__':
    run_bot()
