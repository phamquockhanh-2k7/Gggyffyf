import logging
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)

feature2_enabled = False  # trạng thái bật/tắt

# Khi nhận được link
async def handle_text_or_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global feature2_enabled
    if not feature2_enabled:
        return

    msg = update.message
    if not msg:
        return

    text = msg.text or msg.caption or ""
    if "http" in text:  # phát hiện có link
        await msg.reply_text("🤖 Bot đã nhận được link của bạn.")
        logging.info(f"Bot đã nhận được link: {text}")

# Lệnh bật/tắt
async def apion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global feature2_enabled
    feature2_enabled = True
    await update.message.reply_text("✅ Đã bật tính năng nhận link.")

async def apioff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global feature2_enabled
    feature2_enabled = False
    await update.message.reply_text("🟡 Đã tắt tính năng nhận link.")

# Đăng ký handler
def register_feature2(app):
    app.add_handler(CommandHandler("apion", apion))
    app.add_handler(CommandHandler("apioff", apioff))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_or_media))
