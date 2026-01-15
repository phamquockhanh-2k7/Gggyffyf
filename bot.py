import threading
from telegram.ext import ApplicationBuilder # Dùng Builder chuẩn
from keep_alive import keep_alive
from feature1 import register_feature1
from feature2 import register_feature2
from feature3 import register_feature3
from feature4 import register_feature4

BOT_TOKEN = "7851783179:AAFu58Cs9w1Z7i-xU4pPhnISgg0Sq3vfaPs"

def main():
    # 1. Khởi tạo Application với JobQueue (đã có trong requirements)
    # Builder này sẽ tự tìm thấy apscheduler nếu bạn đã cài đúng [job-queue]
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # 2. Đăng ký tính năng
    # QUAN TRỌNG: Đăng ký Feature 1 (CommandHandler) TRƯỚC để Start được ưu tiên
    register_feature1(app)
    register_feature2(app)
    register_feature3(app)
    register_feature4(app)

    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    # Chạy Flask ở một luồng riêng để không chặn Bot
    t = threading.Thread(target=keep_alive)
    t.start()
    
    # Chạy hàm main chính
    main()
