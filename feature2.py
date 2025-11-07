from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, filters
from feature1 import check_channel_membership  # Tái sử dụng từ feature1

# State để bật/tắt tính năng cho từng user
user_api_enabled = {}  # user_id: True/False

# /api handler: Bật/tắt tính năng
async def api_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not await check_channel_membership(update, context):
        return

    user_id = update.message.from_user.id
    args = context.args
    if args and args[0].lower() == "on":
        user_api_enabled[user_id] = True
        await update.message.reply_text("✅ Tính năng API đã bật! Gửi tin nhắn để bot phản hồi.")
    elif args and args[0].lower() == "off":
        user_api_enabled[user_id] = False
        await update.message.reply_text("❌ Tính năng API đã tắt.")
    else:
        status = "bật" if user_api_enabled.get(user_id, False) else "tắt"
        await update.message.reply_text(f"📋 Trạng thái API: {status}\nNhắn /api on để bật, /api off để tắt.")

# Handler cho tin nhắn (chỉ xử lý nếu API bật)
async def handle_api_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not await check_channel_membership(update, context):
        return

    user_id = update.message.from_user.id
    if not user_api_enabled.get(user_id, False):
        return  # Không xử lý nếu chưa bật

    chat_type = update.message.chat.type
    if chat_type != "private":
        return  # Chỉ xử lý trong chat private

    # Kiểm tra nếu tin nhắn chứa link
    text = update.message.text or update.message.caption or ""
    if "http" in text:
        await update.message.reply_text("đã nhận link")
    else:
        await update.message.reply_text("đã nhận tin nhắn")

def register_feature2(app):
    app.add_handler(CommandHandler("api", api_command))
    app.add_handler(MessageHandler(
        (filters.TEXT | filters.PHOTO | filters.VIDEO | filters.FORWARDED) & ~filters.COMMAND,
        handle_api_message
    ))
