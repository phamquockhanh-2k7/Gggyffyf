import threading
from telegram.ext import Application
from keep_alive import keep_alive
from feature1 import register_feature1
from feature2 import register_feature2
from feature3 import register_feature3 # IMPORT THÊM FEATURE 3

# === CẤU HÌNH TOKEN ===
BOT_TOKEN = "7851783179:AAFu58Cs9w1Z7i-xU4pPhnISgg0Sq3vfaPs"

def run_bot():
    """Khởi tạo và chạy Telegram Bot với đầy đủ tính năng"""
    
    # 1. Khởi tạo Application
    # JobQueue sẽ tự động được kích hoạt nếu bạn đã cài apscheduler
    app = Application.builder().token(BOT_TOKEN).build()

    # 2. Đăng ký các tính năng từ các file riêng biệt
    # register_feature3 chứa xử lý Callback cho nút bấm (download/ref)
    register_feature3(app) 
    register_feature1(app)
    register_feature2(app)

    print("🤖 Bot đang khởi động...")
    print("✅ Đã kết nối: Feature 1 (Store), Feature 2 (API), Feature 3 (Ref/Credits)")
    print("⏳ Tính năng tự động xóa sau 24h đã sẵn sàng.")
    
    # 3. Bắt đầu nhận tin nhắn (Polling)
    app.run_polling()

if __name__ == '__main__':
    # Chạy Web Server để giữ bot sống (Keep Alive)
    keep_alive()
    
    # Chạy bot chính
    run_bot()
