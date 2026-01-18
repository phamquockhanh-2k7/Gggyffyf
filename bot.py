import asyncio
import threading
from telegram.ext import ApplicationBuilder
from keep_alive import keep_alive

# Import các tính năng
from feature1 import register_feature1
from feature2 import register_feature2
from feature3 import register_feature3
from feature4 import register_feature4

# ==============================================================================
# 🔴 CẤU HÌNH TOKEN (QUAN TRỌNG NHẤT)
# ==============================================================================

# 1. Token Bot Chính (Con cũ - Chuyên Video, Link rút gọn, Spam nhóm)
TOKEN_MAIN = "7851783179:AAFu58Cs9w1Z7i-xU4pPhnISgg0Sq3vfaPs" 

# 2. Token Bot Phụ (Con mới - Chuyên SOS, Quản lý người vào nhóm)
# 👉 Vào BotFather tạo con mới, rồi dán Token của nó vào dưới đây:
TOKEN_SOS  = "7773089881:AAFv6vyOhy1uEPTn8T4E02MeYvvet3kutlg" 

# ==============================================================================
# ⚙️ HÀM CHẠY 2 BOT CÙNG LÚC (KHÔNG CẦN SỬA)
# ==============================================================================
async def run_dual_bots():
    print("🔄 Đang khởi động hệ thống Song Bot...")

    # --- SETUP BOT 1: BOT CHÍNH (VIDEO & SPAM) ---
    print("🛠 Đang cài đặt Bot Chính...")
    app_main = ApplicationBuilder().token(TOKEN_MAIN).build()
    register_feature1(app_main) # Start, Upload, Store
    register_feature2(app_main) # Rút gọn link (Spam thoải mái)
    register_feature3(app_main) # Xử lý nút tải, credit
    print("✅ Bot Chính: Đã sẵn sàng!")

    # --- SETUP BOT 2: BOT PHỤ (SOS SYSTEM) ---
    print("🛠 Đang cài đặt Bot SOS...")
    app_sos = ApplicationBuilder().token(TOKEN_SOS).build()
    register_feature4(app_sos)  # Chỉ chạy tính năng lưu ID & gửi tin hàng loạt
    print("✅ Bot Phụ (SOS): Đã sẵn sàng!")

    # --- BẮT ĐẦU KÍCH HOẠT ---
    await app_main.initialize()
    await app_sos.initialize()

    await app_main.start()
    await app_sos.start()

    # Kích hoạt lắng nghe (Polling) cho cả 2 con cùng lúc
    print("🚀 BẮT ĐẦU CHẠY POLLING...")
    await app_main.updater.start_polling()
    await app_sos.updater.start_polling()
    
    print("🎉 THÀNH CÔNG! 2 BOT ĐANG CHẠY TRÊN CÙNG 1 SERVER.")

    # Vòng lặp vô tận để giữ chương trình không bị tắt
    while True:
        await asyncio.sleep(1000)

# ==============================================================================
# KHỐI CHẠY CHÍNH
# ==============================================================================
if __name__ == '__main__':
    # 1. Giữ Server sống (cho UptimeRobot)
    t = threading.Thread(target=keep_alive)
    t.start()
    
    # 2. Chạy hệ thống Bot Async
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    try:
        loop.run_until_complete(run_dual_bots())
    except KeyboardInterrupt:
        print("🛑 Đã dừng Bot.")
