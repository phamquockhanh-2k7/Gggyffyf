import requests
import asyncio
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, filters
import config

# --- BỎ DÒNG IMPORT SECURITY BỊ LỖI ---
# from .security import check_permission 

# Danh sách người dùng đang BẬT chế độ Bypass
BYPASS_USERS = set()

async def command_bat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bật chế độ tự động lấy link gốc"""
    user_id = update.effective_user.id
    BYPASS_USERS.add(user_id)
    await update.message.reply_text("🟢 **ĐÃ BẬT BYPASS!**\nGiờ bạn gửi link `vuotlink.vip` vào đây, tôi sẽ soi link gốc cho.", parse_mode="Markdown")

async def command_tat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tắt chế độ tự động lấy link gốc"""
    user_id = update.effective_user.id
    if user_id in BYPASS_USERS:
        BYPASS_USERS.remove(user_id)
    await update.message.reply_text("🔴 **ĐÃ TẮT BYPASS!**\nBot trở lại bình thường.", parse_mode="Markdown")

async def bypass_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg_text = update.message.text.strip()
    
    # 1. Chỉ xử lý nếu user đã BẬT và tin nhắn có chứa link vuotlink
    if user_id not in BYPASS_USERS:
        return
    
    if "vuotlink.vip" not in msg_text:
        return

    # 2. Thông báo đang xử lý
    status_msg = await update.message.reply_text("🕵️‍♂️ Đang dùng tài khoản VIP soi link...")

    # 3. Cấu hình Request với Cookie VIP
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Cookie': config.VUOTLINK_PRO_COOKIE, # Lấy từ config
        'Referer': 'https://vuotlink.vip/'
    }

    try:
        # Chạy request trong luồng riêng để không chặn bot
        response = await asyncio.to_thread(requests.get, msg_text, headers=headers, allow_redirects=False, timeout=15)
        
        # 4. Kiểm tra chuyển hướng (301, 302...)
        if response.status_code in [301, 302, 303, 307]:
            final_link = response.headers.get('Location')
            await status_msg.edit_text(f"✅ **LINK GỐC:**\n\n`{final_link}`", parse_mode="Markdown")
        
        elif response.status_code == 200:
            await status_msg.edit_text("❌ Không tìm thấy link gốc. Có thể Cookie hết hạn hoặc link sai.")
        else:
            await status_msg.edit_text(f"❌ Lỗi HTTP: {response.status_code}")

    except Exception as e:
        await status_msg.edit_text(f"❌ Lỗi kết nối: {e}")

def register_feature7(app):
    app.add_handler(CommandHandler("bat", command_bat))
    app.add_handler(CommandHandler("tat", command_tat))
    # Lắng nghe tin nhắn chứa link (Ưu tiên thấp hơn lệnh /kho nạp file)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(r"vuotlink\.vip"), bypass_logic), group=10)
