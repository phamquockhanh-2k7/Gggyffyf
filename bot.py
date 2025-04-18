import time
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from firebase import firebase

# Thiết lập bot và kết nối với Firebase
BOT_TOKEN = "8064426886:AAHNez92dmsVQBB6yQp65k_pjPwiJT-SBEI"
bot = Bot(token=BOT_TOKEN)

# Firebase URL để lấy danh sách người dùng
FIREBASE_URL = "https://bot-telegram-99852-default-rtdb.firebaseio.com"
firebase = firebase.FirebaseApplication(FIREBASE_URL, None)

async def send_bulk_message(message_text: str):
    # Lấy tất cả user_id từ Firebase
    users_ref = firebase.get('/users', None)  # Lấy toàn bộ dữ liệu người dùng từ Firebase

    if users_ref:
        for user_id, user_data in users_ref.items():
            try:
                # Gửi tin nhắn đến từng user_id
                await bot.send_message(chat_id=user_id, text=message_text)

                # Thêm delay để tránh spam
                time.sleep(2)  # Delay 2 giây giữa các tin nhắn
            except Exception as e:
                print(f"Không thể gửi tin nhắn đến {user_id}: {e}")

async def guilink(update: Update, context: CallbackContext):
    if not update.message or update.effective_chat.type != "private":
        return

    if update.message.text:
        # Lấy nội dung tin nhắn từ người dùng
        message_text = update.message.text

        # Gửi tin nhắn tới tất cả người dùng đã từng sử dụng bot
        await send_bulk_message(message_text)

        # Thông báo cho người dùng đã gửi thành công
        await update.message.reply_text("✅ Tin nhắn đã được gửi đến tất cả người dùng!")

def main():
    # Khởi tạo ứng dụng Telegram
    app = Application.builder().token(BOT_TOKEN).build()

    # Đăng ký handler cho lệnh /guilink và gửi tin nhắn
    app.add_handler(CommandHandler("guilink", guilink))

    print("✅ Bot đang chạy...")

    # Bắt đầu polling
    app.run_polling()

if __name__ == "__main__":
    main()
