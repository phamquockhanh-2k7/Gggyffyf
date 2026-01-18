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

# ==============================================================================
# 🔴 CẤU HÌNH TOKEN CHO 5 CON BOT
# ==============================================================================

# 1. BOT CHÍNH (Video, Link, Spam)
TOKEN_MAIN  = "7851783179:AAFu58Cs9w1Z7i-xU4pPhnISgg0Sq3vfaPs" 

# 2. DANH SÁCH 4 BOT SOS (Dự phòng, Bắt ID)
# 👉 Bạn dán Token của 4 con Bot phụ vào giữa dấu ngoặc kép ""
SOS_TOKENS = [
    "7773089881:AAGfT6xJztiH9zSjm6rKgvKBo53qJE84uo0",  # Laucuadong01_bot
    "8004443054:AAHTKzluiWBCV-VeCljiGoEFkOMW94NmzQU",                             # daihoc69bot
    "7713949546:AAG-4EUiekIdxs6zCVVfxlZCPGrh31BnUkw",                             # xclassvnvip_bot
    "7473854195:AAFhXs8euDsYVZanx_A25MC_zIsaS_d_su8",# hoahocduong_bbot
    "8332572670:AAEFwN0B2BNeitWJg2tn2YvDOLPpxjLZ4GU"# hoichancuu01_bot
]

# ==============================================================================
# ⚙️ HÀM KHỞI TẠO VÀ CHẠY NHIỀU BOT
# ==============================================================================
async def run_multiple_bots():
    print(f"🔄 Đang khởi động hệ thống 1 Main + {len(SOS_TOKENS)} SOS...")
    
    # Danh sách để lưu các bot đang chạy
    apps = []

    # ---------------------------------------------------------
    # HÀM PHỤ: CÀI ĐẶT 1 CON BOT
    # ---------------------------------------------------------
    async def setup_one_bot(token, name, is_main=False):
        # Kiểm tra token có hợp lệ không (để tránh lỗi nếu bạn chưa điền đủ)
        if not token or "TOKEN" in token: 
            print(f"⚠️ Bỏ qua {name} (Chưa có Token)")
            return

        print(f"🛠 Đang cài đặt {name}...")
        try:
            app = ApplicationBuilder().token(token).build()
            
            # --- CÀI TÍNH NĂNG ---
            if is_main:
                # Bot chính: Cài full tính năng
                register_feature1(app) # Upload
                register_feature2(app) # Link rút gọn
                register_feature3(app) # Credit
                register_feature4(app) # Bắt ID
            else:
                # Bot SOS: Chỉ cài tính năng bắt ID
                register_feature4(app) 
            
            # Khởi động Bot
            await app.initialize()
            await app.start()
            
            # Kích hoạt lắng nghe (Bắt buộc có allowed_updates để bắt ID)
            await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
            
            apps.append(app)
            print(f"✅ {name}: Đã chạy thành công!")
            
        except Exception as e:
            print(f"❌ Lỗi cài đặt {name}: {e}")

    # ---------------------------------------------------------
    # CHẠY LẦN LƯỢT CÁC BOT
    # ---------------------------------------------------------
    
    # 1. Chạy Bot Chính trước
    await setup_one_bot(TOKEN_MAIN, "BOT CHÍNH (VIDEO)", is_main=True)

    # 2. Chạy vòng lặp cho 4 Bot SOS
    for i, token in enumerate(SOS_TOKENS):
        await setup_one_bot(token, f"BOT SOS {i+1}")

    print(f"\n🚀 TỔNG KẾT: ĐANG CHẠY {len(apps)} BOT TRÊN SERVER NÀY.")
    
    # Giữ server sống mãi mãi
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
