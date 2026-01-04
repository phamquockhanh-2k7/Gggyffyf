import asyncio
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
from telegram.ext import ContextTypes, CallbackQueryHandler

# Đường dẫn Firebase của bạn
FIREBASE_URL = "https://bot-telegram-99852-default-rtdb.firebaseio.com"

# --- CÁC HÀM XỬ LÝ FIREBASE ---

async def get_credits(user_id):
    """Lấy số lượt tải hiện có từ mục /ref/user_id"""
    url = f"{FIREBASE_URL}/ref/{user_id}.json"
    res = await asyncio.to_thread(requests.get, url)
    return res.json() if (res.status_code == 200 and res.json() is not None) else None

async def init_user_if_new(user_id):
    """Tặng 1 lượt cho người mới lần đầu tương tác"""
    current = await get_credits(user_id)
    if current is None:
        url = f"{FIREBASE_URL}/ref/{user_id}.json"
        await asyncio.to_thread(requests.put, url, json=1)
        return 1
    return current

async def add_credit(user_id, amount=1):
    """Cộng lượt tải cho người giới thiệu"""
    current = await get_credits(user_id) or 0
    url = f"{FIREBASE_URL}/ref/{user_id}.json"
    await asyncio.to_thread(requests.put, url, json=current + amount)

async def deduct_credit(user_id):
    """Trừ 1 lượt tải khi nhấn nút tải video"""
    current = await get_credits(user_id) or 0
    if current > 0:
        url = f"{FIREBASE_URL}/ref/{user_id}.json"
        await asyncio.to_thread(requests.put, url, json=current - 1)
        return True
    return False

# --- XỬ LÝ GIAO DIỆN NÚT BẤM ---

async def delete_msg_job(context: ContextTypes.DEFAULT_TYPE):
    """Hàm chạy ngầm xóa tin nhắn sau 24h"""
    try:
        await context.bot.delete_message(chat_id=context.job.chat_id, message_id=context.job.data)
    except: pass

async def check_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /profile để kiểm tra số lượt tải và lấy link REF"""
    try: await update.message.delete()
    except: pass

    if not update.message: return
    user_id = update.effective_user.id
    credits = await init_user_if_new(user_id)
    ref_link = f"https://t.me/{context.bot.username}?start=ref_{user_id}"
    share_text = "--🔥Free100Video18+ỞĐây💪--"
    
    message_text = (
        f"👤 **THÔNG TIN CỦA BẠN**\n"
        f"🆔 ID: `{user_id}`\n"
        f"📥 Lượt tải còn lại: **{credits}** lượt\n\n"
        f"🔗 **Link giới thiệu cá nhân:**\n"
        f"`{ref_link}`\n\n"
        f"💡 *Mẹo: Chia sẻ link trên để nhận thêm 1 lượt tải cho mỗi người mới tham gia!*"
    )
    
    keyboard = [[InlineKeyboardButton("🚀 Chia sẻ ngay nhận lượt", url=f"https://t.me/share/url?url={ref_link}&text={share_text}")]]
    await update.message.reply_text(message_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý khi nhấn nút Tải video"""
    query = update.callback_query
    user_id = query.from_user.id
    alias = query.data.split("_")[1]
    
    try:
        credits = await get_credits(user_id)
        if credits is None: credits = 1
        
        if credits <= 0:
            await query.answer(text="❌ Bạn đã hết lượt tải miễn phí!", show_alert=True)
            ref_link = f"https://t.me/{context.bot.username}?start=ref_{user_id}"
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"Hãy chia sẻ link để nhận thêm lượt tải:\n`{ref_link}`",
                parse_mode="Markdown"
            )
            return

        await query.answer(text="✅ Đang lấy dữ liệu bản lưu...")

        shared_url = f"{FIREBASE_URL}/shared/{alias}.json"
        res = await asyncio.to_thread(requests.get, shared_url)
        data = res.json()

        if res.status_code == 200 and data:
            if await deduct_credit(user_id):
                new_credits = credits - 1
                media_group, text_content, docs_to_send = [], [], []
                
                for item in data:
                    f_id = item["file_id"]
                    f_type = item["type"]
                    if f_type == "photo": media_group.append(InputMediaPhoto(f_id))
                    elif f_type == "video": media_group.append(InputMediaVideo(f_id))
                    elif f_type == "text": text_content.append(f_id)
                    elif f_type == "document": docs_to_send.append(f_id) # NHẬN DIỆN DOCUMENT

                # 1. Gửi văn bản
                if text_content:
                    await context.bot.send_message(chat_id=query.message.chat_id, text="\n\n".join(text_content))
                
                # 2. Gửi Album (Ảnh/Video)
                if media_group:
                    for i in range(0, len(media_group), 10):
                        await context.bot.send_media_group(chat_id=query.message.chat_id, media=media_group[i:i+10])
                
                # 3. Gửi File (APK, ZIP, PDF...)
                for doc_id in docs_to_send:
                    await context.bot.send_document(chat_id=query.message.chat_id, document=doc_id)

                await context.bot.send_message(chat_id=query.message.chat_id, text=f"✅ Đã gửi bản lưu! (Bạn còn {new_credits} lượt)")

                # Cập nhật nút bấm hiển thị số lượt mới
                ref_link = f"https://t.me/{context.bot.username}?start=ref_{user_id}"
                share_text = "--🔥Free100Video18+ỞĐây💪--"
                keyboard = [
                    [InlineKeyboardButton(f"📥 Tải video (còn {new_credits} lượt)", callback_data=f"dl_{alias}")],
                    [InlineKeyboardButton("🔗 Chia sẻ nhận thêm lượt", url=f"https://t.me/share/url?url={ref_link}&text={share_text}")]
                ]
                await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await context.bot.send_message(chat_id=query.message.chat_id, text="❌ Không tìm thấy dữ liệu gốc.")
            
    except Exception as e:
        print(f"Lỗi Callback: {e}")
        await query.answer(text="⚠️ Có lỗi xảy ra.")

async def cheat_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try: await update.message.delete()
    except: pass
    if not update.message: return
    user_id = update.effective_user.id
    await add_credit(user_id, amount=20)
    await update.message.reply_text("✨ Admin: Đã nạp thêm +20 lượt tải.")

def register_feature3(app):
    app.add_handler(CallbackQueryHandler(download_callback, pattern="^dl_"))
