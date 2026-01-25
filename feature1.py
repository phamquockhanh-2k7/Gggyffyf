import secrets
import string
import asyncio
import requests
from datetime import datetime
from telegram import Update, InputMediaPhoto, InputMediaVideo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, filters
import config  # Import config từ thư mục gốc

# Import Relative (dấu chấm) để lấy hàm từ file credits.py cùng thư mục
from .credits import init_user_if_new, add_credit, delete_msg_job, get_credits, check_credits, cheat_credits

FIREBASE_URL = f"{config.FIREBASE_URL}/shared"

def generate_alias(length=7):
    date_prefix = datetime.now().strftime("%d%m%Y")
    random_part = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(length))
    return date_prefix + random_part

async def check_channel_membership(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        if not user: return False
        
        try:
            member = await context.bot.get_chat_member(config.MAIN_CHANNEL_USERNAME, user.id)
            if member.status in ['member', 'administrator', 'creator']: return True
        except: pass 

        args = context.args
        confirm_link = f"https://t.me/{context.bot.username}?start={args[0]}" if args else f"https://t.me/{context.bot.username}?start=start"
        
        keyboard = [
            [InlineKeyboardButton("🔥 THAM GIA KÊNH NGAY", url=f"https://t.me/{config.MAIN_CHANNEL_USERNAME[1:]}")],
            [InlineKeyboardButton("🔓 THAM GIA KÊNH NÀY NỮA", url=config.JOIN_LINK_CHANNEL)],
            [InlineKeyboardButton("🔓 XÁC NHẬN ĐÃ THAM GIA", url=confirm_link)]
        ]
        if update.message:
            await update.message.reply_text(f"📛 BẠN PHẢI THAM GIA KÊNH {config.MAIN_CHANNEL_USERNAME} TRƯỚC!", reply_markup=InlineKeyboardMarkup(keyboard))
        return False
    except: return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not await check_channel_membership(update, context): return
    user_id = update.effective_user.id
    existing_user_data = await get_credits(user_id)
    current_credits = await init_user_if_new(user_id)
    protect = context.user_data.get('user_protection', True)
    
    ref_link = f"https://t.me/{context.bot.username}?start=ref_{user_id}"
    full_share_url = f"https://t.me/share/url?url={ref_link}&text=--VideoHot--"

    if context.args:
        command = context.args[0]
        if command.startswith("ref_"):
            try:
                referrer_id = command.split("_")[1]
                keyboard = [[InlineKeyboardButton("LINK FREE", url=config.REF_LINK_1)], [InlineKeyboardButton("Link 2", url=config.REF_LINK_2)]]
                if existing_user_data is None and referrer_id != str(user_id):
                    await add_credit(referrer_id)
                    await update.message.reply_text("🎉 Đã tính ref!", reply_markup=InlineKeyboardMarkup(keyboard))
                else:
                    await update.message.reply_text("👋 Chào mừng!", reply_markup=InlineKeyboardMarkup(keyboard))
                await update.message.reply_text(f"Bạn có {current_credits} lượt.", reply_markup=InlineKeyboardMarkup(keyboard))
            except: pass
            return

        alias = command
        try:
            res = await asyncio.to_thread(requests.get, f"{FIREBASE_URL}/{alias}.json")
            data = res.json()
            if res.status_code == 200 and data:
                media, text = [], []
                for item in data:
                    if item["type"] == "photo": media.append(InputMediaPhoto(item["file_id"]))
                    elif item["type"] == "video": media.append(InputMediaVideo(item["file_id"]))
                    elif item["type"] == "text": text.append(item["file_id"])
                
                msgs_del = []
                if text: msgs_del.append(await update.message.reply_text("\n\n".join(text), protect_content=protect))
                if media:
                    for i in range(0, len(media), 10):
                        msgs_del.extend(await update.message.reply_media_group(media[i:i+10], protect_content=protect))
                        await asyncio.sleep(0.5)

                kb = [[InlineKeyboardButton(f"📥 Tải ({current_credits} lượt)", callback_data=f"dl_{alias}")],
                      [InlineKeyboardButton("🔗 Chia sẻ", url=full_share_url)],
                      [InlineKeyboardButton("🎁 Nhiệm vụ", callback_data="task_open")]]
                msgs_del.append(await update.message.reply_text("📌 Nhấn tải bên dưới:", reply_markup=InlineKeyboardMarkup(kb)))
                
                for m in msgs_del: context.job_queue.run_once(delete_msg_job, 86400, data=m.message_id, chat_id=update.effective_chat.id)

                if context.user_data.get('current_mode') == 'API':
                    # Import Dynamic từ shortener.py
                    from .shortener import generate_shortened_content
                    full_link = f"https://t.me/{context.bot.username}?start={alias}"
                    short_txt = await generate_shortened_content(full_link)
                    await update.message.reply_text(f"🚀 API:\n<pre>{short_txt}</pre>", parse_mode="HTML")
            else: await update.message.reply_text("❌ Link hỏng.")
        except: await update.message.reply_text("🔒 Lỗi mạng.")
    else: await update.message.reply_text("📥 Gửi /newlink để tạo.")

async def newlink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not await check_channel_membership(update, context): return
    user_id = update.effective_user.id
    context.user_data['current_mode'] = 'STORE'
    if 'storage_files' not in context.bot_data: context.bot_data['storage_files'] = {}
    if 'storage_alias' not in context.bot_data: context.bot_data['storage_alias'] = {}
    context.bot_data['storage_files'][user_id] = []
    context.bot_data['storage_alias'][user_id] = generate_alias()
    await update.message.reply_text("✅ Chế độ lưu: Gửi file đi, xong nhắn /done.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('current_mode') != 'STORE': return 
    user_id = update.effective_user.id
    storage = context.bot_data.get('storage_files', {})
    if user_id not in storage: return
    entry = None
    if update.message.photo: entry = {"file_id": update.message.photo[-1].file_id, "type": "photo"}
    elif update.message.video: entry = {"file_id": update.message.video.file_id, "type": "video"}
    elif update.message.text: entry = {"file_id": update.message.text, "type": "text"}
    if entry: context.bot_data['storage_files'][user_id].append(entry)

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('current_mode') != 'STORE': return
    user_id = update.effective_user.id
    files = context.bot_data.get('storage_files', {}).get(user_id, [])
    alias = context.bot_data.get('storage_alias', {}).get(user_id)
    if 'storage_files' in context.bot_data: context.bot_data['storage_files'].pop(user_id, None)
    if not files: return await update.message.reply_text("❌ Chưa gửi gì.")
    
    try:
        res = await asyncio.to_thread(requests.put, f"{FIREBASE_URL}/{alias}.json", json=files)
        if res.status_code == 200:
            link = f"https://t.me/{context.bot.username}?start={alias}"
            await update.message.reply_text(f"✅ Link: {link}\nFile: {len(files)}")
        else: await update.message.reply_text("❌ Lỗi lưu.")
    except: await update.message.reply_text("🔒 Lỗi mạng.")
    context.user_data['current_mode'] = None

async def sigmaboy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not await check_channel_membership(update, context): return
    context.user_data['user_protection'] = context.args[0].lower() == "off" if context.args else True
    await update.message.reply_text("⚙️ Đã chỉnh bảo mật.")

def register_feature1(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("newlink", newlink))
    app.add_handler(CommandHandler("done", done))
    app.add_handler(CommandHandler("sigmaboy", sigmaboy))
    app.add_handler(CommandHandler("profile", check_credits)) 
    app.add_handler(CommandHandler("cheattogetdownload", cheat_credits))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | (filters.TEXT & ~filters.COMMAND), handle_message), group=0)
