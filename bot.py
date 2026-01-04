import threading
from telegram.ext import Application
from keep_alive import keep_alive
from feature1 import register_feature1
from feature2 import register_feature2

# === CẤU HÌNH TOKEN ===
# Lưu ý: Khi push lên GitHub công khai, bạn nên dùng biến môi trường (os.getenv) để bảo mật
BOT_TOKEN = "7851783179:AAFu58Cs9w1Z7i-xU4pPhnISgg0Sq3vfaPs"

def run_bot():
    """Khởi tạo và chạy Telegram Bot"""
    
    # Khởi tạo Application với Token của bạn
    # Thêm tham số defaults nếu bạn muốn tất cả tin nhắn mặc định dùng HTML
    app = Application.builder().token(BOT_TOKEN).build()

    # Đăng ký các tính năng từ các file riêng biệt
    # Thứ tự đăng ký quan trọng: Feature 1 (Lưu trữ) sẽ được kiểm tra trước Feature 2 (API)
    register_feature1(app)
    register_feature2(app)

    print("🤖 Bot đang khởi động...")
    print("🚀 Các tính năng đã sẵn sàng: Lưu trữ Database & Rút gọn Link API")
    
    # Bắt đầu nhận tin nhắn (Polling)
    app.run_polling()

if __name__ == '__main__':
    # 1. Chạy Web Server nhỏ ở luồng riêng để giữ bot sống (Keep Alive)
    # Hàm này từ file keep_alive.py của bạn
    keep_alive()
    
    # 2. Chạy bot chính
    run_bot()
