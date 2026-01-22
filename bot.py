import asyncio
import threading
from telegram import Update
from telegram.ext import ApplicationBuilder
from keep_alive import keep_alive

# Import các tính năng
from feature1 import register_feature1
from feature2 import register_feature2
from feature3 import register_feature3
from feature4 import register_feature4 
from feature5 import register_feature5 

# ==============================================================================
# 🔴 CẤU HÌNH DANH SÁCH TOKEN (THÊM BAO NHIÊU TÙY THÍCH)
# ==============================================================================

# 1. LIST BOT CHÍNH (Full tính năng 1 -> 5)
MAIN_BOT_TOKENS = [
    "7851783179:AAFu58Cs9w1Z7i-xU4pPhnISgg0Sq3vfaPs",  # Con số 1
     "8382549702:AAFBiuSdfOo4l-Fj98tlewnhyvc_KgsAy9w",  #@laucuadongz_bot                        # Con số 2 (Bỏ dấu # ở đầu để dùng)
    # "TOKEN_CON_SO_3_O_DAY",
]

# 2. LIST BOT BROADCAST (Chỉ chạy Feature 5: Spam/Album/Forward)
BROADCAST_BOT_TOKENS = [
    "8064426886:AAFXAUoybJuTlaqUuO1fqHjvBvgxR7dyeH4",  # Con số 1
    # "TOKEN_BROADCAST_2",
]

# 3. LIST BOT SOS (Chỉ chạy Feature 4: Quét ID/Dự phòng)
SOS_BOT_TOKENS = [
    "7773089881:AAGfT6xJztiH9zSjm6rKgvKBo53qJE84uo0", 
    "8004443054:AAHTKzluiWBCV-VeCljiGoEFkOMW94NmzQU", 
    "7713949546:AAG-4EUiekIdxs6zCVVfxlZCPGrh31BnUkw", 
    "7473854195:AAFhXs8euDsYVZanx_A25MC_zIsaS_d_su8", 
    "8332572670:AAEFwN0B2BNeitWJg2tn2YvDOLPpxjLZ4GU" 
]

# ==============================================================================
# ⚙️ HÀM KHỞI TẠO VÀ CHẠY HỆ THỐNG
# ==============================================================================
async def run_multiple_bots():
    print(f"🔄 Đang khởi động hệ thống ĐA NHÂN CÁCH (List Mode)...")
    apps = []

    # ---------------------------------------------------------
    # HÀM CÀI ĐẶT 1 CON BOT
    # ---------------------------------------------------------
    async def setup_one_bot(token, name, bot_type="SOS"):
        # Bỏ qua nếu token trống hoặc chưa điền
        if not token or "TOKEN" in token: 
            return

        print(f"🛠 Đang cài đặt {name}...")
        try:
            app = ApplicationBuilder().token(token).build()
            
            # --- PHÂN LOẠI TÍNH NĂNG ---
            if bot_type == "MAIN":
                # ✅ Bot chính: Nạp FULL tính năng
                register_feature1(app) 
                register_feature2(app)
                register_feature3(app)
                register_feature4(app)
                register_feature5(app) 
                
            elif bot_type == "BROADCAST":
                # Bot Broadcast: Chỉ chạy tính năng 5
                register_feature5(app) 
                
            else: 
                # Bot SOS: Chỉ chạy tính năng 4
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
    # VÒNG LẶP KHỞI ĐỘNG (TỰ ĐỘNG CHẠY HẾT CÁC LIST)
    # ---------------------------------------------------------
    
    # 1. Chạy dàn MAIN
    for i, token in enumerate(MAIN_BOT_TOKENS):
        await setup_one_bot(token, f"👑 MAIN BOT {i+1}", bot_type="MAIN")

    # 2. Chạy dàn BROADCAST
    for i, token in enumerate(BROADCAST_BOT_TOKENS):
        await setup_one_bot(token, f"📢 BROADCAST BOT {i+1}", bot_type="BROADCAST")

    # 3. Chạy dàn SOS
    for i, token in enumerate(SOS_BOT_TOKENS):
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
