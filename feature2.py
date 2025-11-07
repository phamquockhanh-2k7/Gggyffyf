from telegram import Update
from telegram.ext import ContextTypes
import re

# Biến lưu trạng thái chế độ API cho từng người dùng
api_mode = {}

async def apion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bật chế độ API"""
    user_id = update.effective_user.id
    api_mode[user_id] = True
    await update.message.reply_text("🟢... Đã bật chế độ API. Gửi link bất kỳ để bot nhận!")

async def apioff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tắt chế độ API"""
    user_id = update.effective_user.id
    api_mode[user_id] = False
    await update.message.reply_text("🔴 Đã tắt chế độ API, bot quay lại chức năng bình thường.")

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Nhận link khi ở chế độ API"""
    user_id = update.effective_user.id
    text = update.message.text

    # Chỉ phản hồi nếu đang bật chế độ API
    if api_mode.get(user_id, False) and re.match(r'https?://\S+', text):
        await update.message.reply_text("✅ Bot đã nhận được link của bạn.")
