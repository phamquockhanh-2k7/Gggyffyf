import asyncio
import threading
from telegram import Update
from telegram.ext import ApplicationBuilder
from keep_alive import keep_alive
import config  # Import file config

# --- IMPORT CÁC TÍNH NĂNG ---
from features.storage import register_feature1
from features.shortener import register_feature2
from features.credits import register_feature3
from features.sos_tracker import register_feature4
from features.broadcast import register_feature5 
from features.autopost import register_feature6  
from features.bypass import register_feature7   # <--- Feature 7: Bypass Link

# ==============================================================================
# ⚙️ HÀM KHỞI TẠO VÀ CHẠY HỆ THỐNG
# ==============================================================================
async def run_multiple_bots():
    print(f"🔄 Đang khởi động hệ thống ĐA NHÂN CÁCH (List Mode)...")
    apps = []
    
    # 🛡️ DANH SÁCH CÁC TOKEN ĐANG CHẠY (Để lọc trùng)
    running_tokens = set()

    # ---------------------------------------------------------
    # HÀM CÀI ĐẶT 1 CON BOT
    # ---------------------------------------------------------
    async def setup_one_bot(token, name, bot_type="SOS"):
        # 1. Kiểm tra token hợp lệ
        if not token or "TOKEN" in token or len(token) < 10: 
            return

        # 2. 🛡️ KIỂM TRA TRÙNG LẶP (QUAN TRỌNG NHẤT)
        if token in running_tokens:
            print(f"⚠️ CẢNH BÁO: Token của '{name}' đã được chạy ở bot khác. Bỏ qua để tránh xung đột!")
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
                # register_feature7(app) # Main có soi link không tùy fen

            elif bot_type == "POSTER":
                # Bot Poster: Auto Post + Bypass
                register_feature6(app) 
                register_feature7(app) 

            elif bot_type == "BROADCAST":
                # ✅ Bot Broadcast: Chạy Gửi tin + Auto Post + Bypass
                register_feature5(app) # Broadcast
                register_feature6(app) # Auto Post
                register_feature7(app) # Bypass Link (/bat, /tat)
                
            else: 
                # Bot SOS
                register_feature4(app) 
            
            # Khởi động
            await app.initialize()
            await app.start()
            await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
            
            # ✅ Đánh dấu token này đã chạy
            running_tokens.add(token)
            apps.append(app)
            print(f"✅ {name}: Đã chạy thành công!")
            
        except Exception as e:
            print(f"❌ Lỗi cài đặt {name}: {e}")

    # ---------------------------------------------------------
    # VÒNG LẶP KHỞI ĐỘNG
    # ---------------------------------------------------------
    
    # 1. Chạy dàn MAIN
    for i, token in enumerate(config.MAIN_BOT_TOKENS):
        await setup_one_bot(token, f"👑 MAIN BOT {i+1}", bot_type="MAIN")

    # 2. Chạy POSTER BOT (Nếu config có)
    if config.POSTER_BOT_TOKEN:
        await setup_one_bot(config.POSTER_BOT_TOKEN, "📮 POSTER BOT", bot_type="POSTER")

    # 3. Chạy dàn BROADCAST
    for i, token in enumerate(config.BROADCAST_BOT_TOKENS):
        await setup_one_bot(token, f"📢 BROADCAST BOT {i+1}", bot_type="BROADCAST")

    # 4. Chạy dàn SOS
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
