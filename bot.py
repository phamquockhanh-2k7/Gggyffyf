import firebase_admin
from firebase_admin import credentials, db
import time
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import asyncio

# 🔐 TOKEN BOT TELEGRAM
BOT_TOKEN = "8064426886:AAHNez92dmsVQBB6yQp65k_pjPwiJT-SBEI"

# 🔗 CẤU HÌNH FIREBASE
cred = credentials.Certificate("firebase-credentials.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://bot-telegram-99852-default-rtdb.firebaseio.com'
})

# 🤖 Tạo bot
bot = Bot(token=BOT_TOKEN)

# 📥 Lấy danh sách người dùng từ Firebase
def get_users():
    ref = db.reference('/users')
    return ref.get() or {}

# 📤 Gửi tin nhắn đến tất cả user đã lưu
async def send_bulk_message(text: str):
    users = get_users()
    for user_id in users:
        try:
            await bot.send_message(chat_id=user_id, text=text)
            await asyncio.sleep(2)  # Delay 2 giây để tránh bị chặn spam
        except Exception as e:
            print(f"❌ Không thể gửi đến {user_id}: {e}")

# 📨 Lưu user mỗi khi họ nhắn tin
async def save_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    ref = db.reference(f'/users/{user_id}')
    ref.set(True)

# ✅ Lệnh /guilink - bật chế độ nhận nội dung gửi đi
broadcast_messages = {}

async def guilink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await save_user(update, context)
    broadcast_messages[update.effective_user.id] = True
    await update.message.reply_text("✉️ Gửi nội dung bạn muốn gửi cho tất cả người dùng:")

# 📨 Nhận tin nhắn để gửi đi
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await save_user(update, context)

    if broadcast_messages.get(user_id):
        del broadcast_messages[user_id]
        await update.message.reply_text("🚀 Đang gửi nội dung đến tất cả người dùng...")
        await send_bulk_message(update.message.text)
        await update.message.reply_text("✅ Đã gửi xong!")
    else:
        await update.message.reply_text("💡 Gửi /guilink trước nếu bạn muốn gửi tin nhắn hàng loạt.")

# ▶️ Chạy bot
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("guilink", guilink))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Bot đang chạy...")
    app.run_polling()

if __name__ == "__main__":
    main()
