import asyncio
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler

# Đường dẫn Firebase của bạn
FIREBASE_URL = "https://bot-telegram-99852-default-rtdb.firebaseio.com"

# --- CÁC HÀM XỬ LÝ FIREBASE ---

async def get_credits(user_id):
    """Lấy số lượt tải hiện có từ mục /ref/user_id"""
    url = f"{FIREBASE_URL}/ref/{user_id}.json"
    res = await asyncio.to_thread(requests.get, url)
    # Nếu chưa có dữ liệu (None), trả về None để nhận diện người mới
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
    """Lệnh /download để kiểm tra số lượt tải và lấy link REF"""
    if not update.message: return
    
    user_id = update.effective_user.id
    # Đảm bảo khởi tạo nếu là người mới hoàn toàn chưa từng bấm start
    credits = await init_user_if_new(user_id)
    
    ref_link = f"https://t.me/{context.bot.username}?start=ref_{user_id}"
    
    message_text = (
        f"👤 **Thông tin người dùng:**\n"
        f"🆔 ID: `{user_id}`\n"
        f"📥 Lượt tải còn lại: **{credits}** lượt\n\n"
        f"🔗 **Link giới thiệu của bạn:**\n"
        f"`{ref_link}`\n\n"
        f"💡 *Mỗi khi có 1 người mới tham gia qua link trên, bạn sẽ nhận được thêm 1 lượt tải video!*"
    )
    
    keyboard = [
        [InlineKeyboardButton("🚀 Chia sẻ ngay", url=f"https://t.me/share/url?url={ref_link}&text=Tham%20gia%20Bot%20để%20xem%20nội%20dung%20hấp%20dẫn!")]
    ]
    
    await update.message.reply_text(
        message_text, 
        parse_mode="Markdown", 
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý khi nhấn nút Tải video"""
    query = update.callback_query
    user_id = query.from_user.id
    # callback_data dạng: dl_[alias]
    alias = query.data.split("_")[1]
    
    await query.answer()
    
    # Kiểm tra và trừ lượt tải
    if await deduct_credit(user_id):
        new_credits = await get_credits(user_id)
        
        # Thông báo và gửi video (Ở đây bạn gọi logic gửi video KHÔNG bảo mật)
        await query.message.reply_text(f"🚀 Đang chuẩn bị bản lưu cho bạn... (Còn {new_credits} lượt)")
        
        # Cập nhật lại nút bấm để hiển thị số lượt mới
        keyboard = [
            [InlineKeyboardButton(f"📥 Tải video (còn {new_credits} lượt)", callback_data=f"dl_{alias}")],
            [InlineKeyboardButton("🔗 Chia sẻ nhận thêm lượt", url=f"https://t.me/{context.bot.username}?start=ref_{user_id}")]
        ]
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        
        # Lưu ý: Bạn cần import và gọi hàm gửi video từ feature1 tại đây nhưng tắt protect_content
    else:
        await query.message.reply_text("❌ Bạn đã hết lượt tải. Hãy chia sẻ link để kiếm thêm!")

def register_feature3(app):
    app.add_handler(CallbackQueryHandler(download_callback, pattern="^dl_"))
