import asyncio
import threading
from telegram import Update
from telegram.ext import ApplicationBuilder
from keep_alive import keep_alive
import config  # Import file config cùng cấp

# --- IMPORT TỪ THƯ MỤC FEATURES (Cấu trúc mới) ---
from features.storage import register_feature1      
from features.shortener import register_feature2    
from features.credits import register_feature3      
from features.sos_tracker import register_feature4  
from features.broadcast import register_feature5    

# ==============================================================================
# ⚙️ HÀM KHỞI TẠO VÀ CHẠY HỆ THỐNG
# ==============================================================================
async def run_multiple_bots():
    print(f"🔄 Đang khởi động hệ thống ĐA NHÂN CÁCH (Modular Pro Mode)...")
    apps = []

    # Hàm cài đặt 1 bot
    async def setup_one_bot(token, name, bot_type="SOS"):
        if not token or "TOKEN" in token: return

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
            
            await app.initialize()
            await app.start()
            await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
            apps.append(app)
            print(f"✅ {name}: OK!")
        except Exception as e:
            print(f"❌ Lỗi {name}: {e}")

    # --- CHẠY LIST BOT TỪ CONFIG ---
    # 1. Main Bots
    for i, token in enumerate(config.MAIN_BOT_TOKENS):
        await setup_one_bot(token, f"👑 MAIN {i+1}", "MAIN")

    # 2. Broadcast Bots
    for i, token in enumerate(config.BROADCAST_BOT_TOKENS):
        await setup_one_bot(token, f"📢 CAST {i+1}", "BROADCAST")

    # 3. SOS Bots
    for i, token in enumerate(config.SOS_BOT_TOKENS):
        await setup_one_bot(token, f"🚑 SOS {i+1}", "SOS")

    print(f"\n🚀 TỔNG: {len(apps)} BOT ĐANG CHẠY.")
    while True: await asyncio.sleep(1000)

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
        print("🛑 Stop.")
