import secrets
import string
import asyncio
import requests
from datetime import datetime
from threading import Lock
from telegram import (
    Update, InputMediaPhoto, InputMediaVideo, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    CommandHandler, MessageHandler, ContextTypes, filters
)

# Import các hàm từ feature3 để xử lý lượt tải và referral
from feature3 import init_user_if_new, add_credit, delete_msg_job, get_credits

FIREBASE_URL = "https://bot-telegram-99852-default-rtdb.firebaseio.com/shared"
CHANNEL_USERNAME = "@hoahocduong_vip"

user_files = {}
user_alias = {}
user_protection = {}
data_lock = Lock()

def generate_alias(length=7):
    date_prefix = datetime.now().strftime("%d%m%Y")
    random_part = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(length))
    return date_prefix + random_part

async def check_channel_membership(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        if not user: return False
        member = await context.bot.get_chat_member(CHANNEL_USERNAME, user.id)
        if member.status in ['member', 'administrator', 'creator']:
            return True

        start_args = context.args
        if update.message and update.message.text.startswith('/start') and start_args:
            confirm_link = f"https://t.me/{context.bot.username}?start={start_args[0]}"
        else:
            confirm_link = f"https://t.me/{context.bot.username}?start=start"

        keyboard = [
            [InlineKeyboardButton("🔥 THAM GIA KÊNH NGAY", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")],
            [InlineKeyboardButton("🔓 THAM GIA KÊNH NÀY NỮA", url=f"https://t.me/+FLoRiJiPtUJhNjhl")],
            [InlineKeyboardButton("🔓 XÁC NHẬN ĐÃ THAM GIA", url=confirm_link)]
        ]
        if update.message:
            await update.message.reply_text(
                "📛 BẠN PHẢI THAM GIA KÊNH TRƯỚC KHI SỬ DỤNG BOT!\n"
                f"👉 Kênh yêu cầu: {CHANNEL_USERNAME}\n"
                "✅ Sau khi tham gia, nhấn nút XÁC NHẬN để tiếp tục",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return False
    except Exception as e:
        print(f"Lỗi kiểm tra kênh: {e}")
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not await check_channel_membership(update, context): return
    
    user_id = update.message.from_user.id
    protect = user_protection.get(user_id, True)
    
    # --- LOGIC MỚI: TẶNG 1 LƯỢT CHO NGƯỜI MỚI ---
    current_credits = await init_user_if_new(user_id)
    
    args = context.args
    if args:
        command = args[0]
        
        # --- LOGIC MỚI: XỬ LÝ LINK REFERRAL ---
        if command.startswith("ref_"):
            referrer_id = command.split("_")[1]
            if referrer_id != str(user_id):
                await add_credit(referrer_id)
                await update.message.reply_text("🎉 Bạn đã giúp người giới thiệu nhận thêm 1 lượt tải!")
            await update.message.reply_text(f"Chào mừng! Bạn đang có {current_credits} lượt lưu video miễn phí.")
            return

        # --- LOGIC XEM NỘI DUNG (ALIAS) ---
        alias = command
        url = f"{FIREBASE_URL}/{alias}.json"
        try:
            res = await asyncio.to_thread(requests.get, url)
            if res.status_code == 200 and res.json():
                media_items = res.json()
                media_group, text_content = [], []
                for item in media_items:
                    if item["type"] == "photo": media_group.append(InputMediaPhoto(item["file_id"]))
                    elif item["type"] == "video": media_group.append(InputMediaVideo(item["file_id"]))
                    elif item["type"] == "text": text_content.append(item["file_id"])
                
                # Gửi nội dung văn bản (Nếu có)
                if text_content: 
                    await update.message.reply_text("\n\n".join(text_content), protect_content=protect)
                
                # Gửi Media Group (Ảnh/Video)
                sent_messages = []
                for i in range(0, len(media_group), 10):
                    batch = await update.message.reply_media_group(media_group[i:i+10], protect_content=protect)
                    sent_messages.extend(batch)
                    await asyncio.sleep(0.5)

                # --- LOGIC MỚI: HẸN GIỜ XÓA & NÚT BẤM ---
                if sent_messages:
                    # Xóa tin nhắn đầu tiên trong group sau 24h (86400 giây)
                    context.job_queue.run_once(delete_msg_job, 86400, data=sent_messages[0].message_id, chat_id=update.effective_chat.id)

                # Hiển thị nút bấm và thông báo bảo mật
                keyboard = [
                    [InlineKeyboardButton(f"📥 Tải video (còn {current_credits} lượt)", callback_data=f"dl_{alias}")],
                    [InlineKeyboardButton("🔗 Chia sẻ nhận thêm lượt", url=f"https://t.me/{context.bot.username}?start=ref_{user_id}")]
                ]
                await update.message.reply_text(
                    "📌 Video sẽ được xóa sau 24h.\n"
                    "Nội dung đang được bảo vệ không thể lưu trực tiếp.\n"
                    "Để lưu video, hãy ấn nút phía dưới. Mỗi lượt chia sẻ bạn nhận được 1 lượt tải.",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else: 
                await update.message.reply_text("❌ Không tìm thấy dữ liệu với mã này.")
        except Exception as e: 
            await update.message.reply_text("🔒 Lỗi kết nối database")
    else:
        await update.message.reply_text("📥 Gửi lệnh /newlink để bắt đầu tạo liên kết lưu trữ nội dung.")

async def newlink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not await check_channel_membership(update, context): return
    user_id = update.message.from_user.id
    context.user_data['current_mode'] = 'STORE'
    with data_lock:
        user_files[user_id] = []
        user_alias[user_id] = generate_alias()
    await update.message.reply_text("✅ Bây giờ bạn có thể gửi ảnh, video để lưu trữ. Khi xong hãy nhắn /done để tạo link lưu trữ.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('current_mode') != 'STORE': return 
    user_id = update.message.from_user.id
    with data_lock:
        if user_id not in user_files: return
    entry = None
    if update.message.photo: entry = {"file_id": update.message.photo[-1].file_id, "type": "photo"}
    elif update.message.video: entry = {"file_id": update.message.video.file_id, "type": "video"}
    elif update.message.text: entry = {"file_id": update.message.text, "type": "text"}
    if entry:
        with data_lock:
            if entry not in user_files[user_id]: user_files[user_id].append(entry)

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('current_mode') != 'STORE': return
    user_id = update.message.from_user.id
    with data_lock:
        files = user_files.get(user_id, [])
        alias = user_alias.get(user_id)
        user_files.pop(user_id, None)
        user_alias.pop(user_id, None)
    if not files or not alias:
        await update.message.reply_text("❌ Bạn chưa bắt đầu bằng link hoặc chưa gửi nội dung.")
        return
    try:
        response = await asyncio.to_thread(requests.put, f"{FIREBASE_URL}/{alias}.json", json=files)
        if response.status_code == 200:
            link = f"https://t.me/{context.bot.username}?start={alias}"
            await update.message.reply_text(f"✅ Đã lưu thành công!\n🔗 Link truy cập: {link}\n📦 Tổng số nội dung: {len(files)}")
        else: await update.message.reply_text("❌ Có vẻ link này bị lỗi.")
    except Exception: await update.message.reply_text("🔒 Lỗi kết nối database")
    context.user_data['current_mode'] = None

async def sigmaboy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not await check_channel_membership(update, context): return
    user_id = update.message.from_user.id
    args = context.args
    if args and args[0].lower() == "on": user_protection[user_id] = False
    elif args and args[0].lower() == "off": user_protection[user_id] = True
    await update.message.reply_text(".")

def register_feature1(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("newlink", newlink))
    app.add_handler(CommandHandler("done", done))
    app.add_handler(CommandHandler("sigmaboy", sigmaboy))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | (filters.TEXT & ~filters.COMMAND), handle_message), group=0)
