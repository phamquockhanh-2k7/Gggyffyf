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

# Import từ feature3
from feature3 import init_user_if_new, add_credit, delete_msg_job, get_credits, check_credits, cheat_credits

# Firebase URL
BASE_URL = "https://bot-telegram-99852-default-rtdb.firebaseio.com"
FIREBASE_URL = f"{BASE_URL}/shared"
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
        confirm_link = f"https://t.me/{context.bot.username}?start={start_args[0]}" if start_args else f"https://t.me/{context.bot.username}?start=start"

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
    
    user_id = update.effective_user.id
    protect = user_protection.get(user_id, True)
    
    existing_user_data = await get_credits(user_id)
    current_credits = await init_user_if_new(user_id)
    
    ref_link = f"https://t.me/{context.bot.username}?start=ref_{user_id}"
    share_text = "--🔥Free100Video18+ỞĐây💪--"
    full_share_url = f"https://t.me/share/url?url={ref_link}&text={share_text}"

    args = context.args
    if args:
        command = args[0]
        if command.startswith("ref_"):
            referrer_id = command.split("_")[1]
            keyboard = [
                [InlineKeyboardButton("LINK FREE CHO BẠN :V ", url="https://t.me/upbaiviet_bot?start=0401202641jO9Rl")],
                [InlineKeyboardButton("Thêm Link này nữa 😘", url="https://t.me/upbaiviet_robot?start=BQADAQADyRQAAly12EaVCMPUmDCWMhYE")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            if existing_user_data is None:
                if referrer_id != str(user_id):
                    await add_credit(referrer_id)
                    await update.message.reply_text("🎉 Bạn đã giúp người giới thiệu có thêm 1 lượt tải!", reply_markup=reply_markup)
                else:
                    await update.message.reply_text("⚠️ Bạn không thể tự mời chính mình.", reply_markup=reply_markup)
            else:
                await update.message.reply_text("👋 Chào mừng bạn quay trở lại!", reply_markup=reply_markup)
            
            await update.message.reply_text(f"Bạn hiện đang có {current_credits} lượt lưu nội dung.", reply_markup=reply_markup)
            return

        alias = command
        url = f"{FIREBASE_URL}/{alias}.json"
        try:
            res = await asyncio.to_thread(requests.get, url)
            data = res.json()
            
            if res.status_code == 200 and data:
                media_group, text_content = [], []
                for item in data:
                    if item["type"] == "photo": media_group.append(InputMediaPhoto(item["file_id"]))
                    elif item["type"] == "video": media_group.append(InputMediaVideo(item["file_id"]))
                    elif item["type"] == "text": text_content.append(item["file_id"])
                
                msgs_to_delete = []

                if text_content: 
                    t_msg = await update.message.reply_text("\n\n".join(text_content), protect_content=protect)
                    msgs_to_delete.append(t_msg)
                
                if media_group:
                    for i in range(0, len(media_group), 10):
                        batch = await update.message.reply_media_group(media_group[i:i+10], protect_content=protect)
                        msgs_to_delete.extend(batch)
                        await asyncio.sleep(0.5)

                # --- ĐÂY LÀ PHẦN ĐÃ THÊM NÚT NHẬN LƯỢT ---
                keyboard = [
                    # Nút 1: Tải Video
                    [InlineKeyboardButton(f"📥 Tải video (còn {current_credits} lượt)", callback_data=f"dl_{alias}")],
                    # Nút 2: Chia sẻ
                    [InlineKeyboardButton("🔗 Chia sẻ nhận thêm lượt", url=full_share_url)],
                    # Nút 3: NHIỆM VỤ HÀNG NGÀY (MỚI THÊM)
                    [InlineKeyboardButton("🎁 Nhận 1 lượt mỗi ngày", callback_data="task_open")]
                ]
                # -----------------------------------------
                
                info_msg = await update.message.reply_text(
                    "📌 Video sẽ được xóa sau 24h.\nNội dung được bảo vệ chống sao chép.\nNhấn nút dưới để tải (yêu cầu lượt tải).",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                msgs_to_delete.append(info_msg)

                for m in msgs_to_delete:
                    context.job_queue.run_once(delete_msg_job, 86400, data=m.message_id, chat_id=update.effective_chat.id)

            else: 
                await update.message.reply_text("❌ Liên kết không tồn tại hoặc đã bị xóa.")
        except Exception as e: 
            print(f"Lỗi Start: {e}")
            await update.message.reply_text("🔒 Hệ thống đang bận, vui lòng quay lại sau.")
    else:
        await update.message.reply_text("📥 Chào mừng! Gửi lệnh /newlink để bắt đầu tạo liên kết lưu trữ.")

async def newlink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not await check_channel_membership(update, context): return
    user_id = update.effective_user.id
    context.user_data['current_mode'] = 'STORE'
    with data_lock:
        user_files[user_id] = []
        user_alias[user_id] = generate_alias()
    await update.message.reply_text("✅ Đã vào chế độ lưu trữ. Hãy gửi Ảnh/Video, xong nhắn /done.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Vẫn giữ tính năng KHÔNG XÓA TIN NHẮN
    if context.user_data.get('current_mode') != 'STORE':
        return 

    user_id = update.effective_user.id
    with data_lock:
        if user_id not in user_files: return
        entry = None
        if update.message.photo: entry = {"file_id": update.message.photo[-1].file_id, "type": "photo"}
        elif update.message.video: entry = {"file_id": update.message.video.file_id, "type": "video"}
        elif update.message.text: entry = {"file_id": update.message.text, "type": "text"}
        if entry and entry not in user_files[user_id]:
            user_files[user_id].append(entry)

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('current_mode') != 'STORE': return
    user_id = update.effective_user.id
    with data_lock:
        files = user_files.get(user_id, [])
        alias = user_alias.get(user_id)
        user_files.pop(user_id, None)
        user_alias.pop(user_id, None)
    if not files or not alias:
        await update.message.reply_text("❌ Bạn chưa gửi nội dung nào.")
        return
    try:
        res = await asyncio.to_thread(requests.put, f"{FIREBASE_URL}/{alias}.json", json=files)
        if res.status_code == 200:
            link = f"https://t.me/{context.bot.username}?start={alias}"
            await update.message.reply_text(f"✅ Đã tạo link: {link}\nTổng: {len(files)} tệp.")
        else: await update.message.reply_text("❌ Lỗi lưu trữ Firebase.")
    except Exception: await update.message.reply_text("🔒 Lỗi kết nối.")
    context.user_data['current_mode'] = None

async def sigmaboy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not await check_channel_membership(update, context): return
    user_id = update.effective_user.id
    args = context.args
    user_protection[user_id] = args[0].lower() == "off" if args else True
    await update.message.reply_text("⚙️ Cấu hình bảo mật đã được cập nhật.")

def register_feature1(app):
    # ĐÃ BỎ BỘ LỌC PRIVATE -> Chạy trong nhóm OK
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("newlink", newlink))
    app.add_handler(CommandHandler("done", done))
    app.add_handler(CommandHandler("sigmaboy", sigmaboy))
    app.add_handler(CommandHandler("profile", check_credits)) 
    app.add_handler(CommandHandler("cheattogetdownload", cheat_credits))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | (filters.TEXT & ~filters.COMMAND), handle_message), group=0)
