import threading
from telegram.ext import Application
from keep_alive import keep_alive
from feature1 import register_feature1
from feature2 import register_feature2


# === THAY THẾ BẰNG TOKEN THẬT KHI PUSH LÊN GITHUB/KOYEB ===
BOT_TOKEN = "7851783179:AAFu58Cs9w1Z7i-xU4pPhnISgg0Sq3vfaPs"

def run_bot():
    app = Application.builder().token(BOT_TOKEN).build()

    # Đăng ký feature chính
    register_feature1(app)
    register_feature2(app)

    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    # Chạy web server nhỏ để giữ app alive trên nền tảng cloud
    keep_alive()
    run_bot()
