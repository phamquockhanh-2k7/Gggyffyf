import asyncio
import threading
from telegram import Update
from telegram.ext import ApplicationBuilder
from keep_alive import keep_alive
import config  # Import file config vừa tạo

# Import các tính năng
from feature1 import register_feature1
from feature2 import register_feature2
from feature3 import register_feature3
from feature4 import register_feature4
from feature5 import register_feature5

# ==============================================================================
# ⚙️ HÀM KHỞI TẠO VÀ CHẠY HỆ THỐNG
# ==============================================================================
async def run_multiple_bots():
    print(f"🔄 Đang khởi động hệ thống ĐA NHÂN CÁCH (Secure Mode)...")
    apps = []

    # ---------------------------------------------------------
    # HÀM CÀI ĐẶT 1 CON BOT
    # ---------------------------------------------------------
    async def setup_one_bot(token, name, bot_type="SOS"):
        if not token or "TOKEN" in token:
            return

        print(f"🛠 Đang cài đặt {name}...")
        try:
            app = ApplicationBuilder().token(token).build()
            
            # --- PHÂN LOẠI TÍNH NĂNG ---
            if bot_type == "MAIN":
                register_feature1(app) 
                register_feature2(app)
                register_feature3(app)
                register_feature4(app)
                register_feature5(app) 
                
            elif bot_type == "BROADCAST":
                register_feature5(app) 
                
            else: # SOS
                register_feature4(app) 
            
            # Khởi động
            await app.initialize()
            await app.start()
            await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
            
            apps.append(app)
            print(f"✅ {name}: Đã chạy thành công!")
            
        except Exception as e:
            print(f"❌ Lỗi cài đặt {name}: {e}")

    # ---------------------------------------------------------
    # VÒNG LẶP KHỞI ĐỘNG (Lấy Token từ config)
    # ---------------------------------------------------------
    
    # 1. Chạy dàn MAIN
    for i, token in enumerate(config.MAIN_BOT_TOKENS):
        await setup_one_bot(token, f"👑 MAIN BOT {i+1}", bot_type="MAIN")

    # 2. Chạy dàn BROADCAST
    for i, token in enumerate(config.BROADCAST_BOT_TOKENS):
        await setup_one_bot(token, f"📢 BROADCAST BOT {i+1}", bot_type="BROADCAST")

    # 3. Chạy dàn SOS
    for i, token in enumerate(config.SOS_BOT_TOKENS):
        await setup_one_bot(token, f"🚑 SOS BOT {i+1}", bot_type="SOS")

    print(f"\n🚀 TỔNG KẾT: ĐANG CHẠY {len(apps)} BOT CÙNG LÚC.")
    
    # Giữ server sống
    while True:
        await asyncio.sleep(1000)

# ==============================================================================
# KHỐI CHẠY CHÍNH
# ==============================================================================
if __name__ == '__main__':
    t = threading.Thread(target=keep_alive)
    t.start()
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    try:
        loop.run_until_complete(run_multiple_bots())
    except KeyboardInterrupt:
        print("🛑 Đã dừng Bot.")
