import requests
import asyncio
import re
import json
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, filters
import config

# --- CẤU HÌNH ---
# ID của ADMIN (Chỉ fen mới được đổi cookie). 
# Fen thay số ID của fen vào đây, hoặc lấy từ config nếu có.
ADMIN_IDS = [123456789, 987654321]  # <--- THAY ID CỦA FEN VÀO ĐÂY

# Biến lưu trữ Cookie trong RAM (để đỡ phải gọi Firebase liên tục)
CURRENT_COOKIE = config.VUOTLINK_PRO_COOKIE 
BYPASS_USERS = set()

# --- HÀM HỖ TRỢ FIREBASE ---
def save_cookie_to_firebase(cookie_value):
    """Lưu cookie lên Firebase để bot khởi động lại không bị mất"""
    if not config.FIREBASE_URL: return
    try:
        url = f"{config.FIREBASE_URL}/settings/vuotlink_cookie.json"
        requests.put(url, json=cookie_value)
    except Exception as e:
        print(f"Lỗi lưu Firebase: {e}")

def get_cookie_from_firebase():
    """Lấy cookie từ Firebase khi khởi động"""
    if not config.FIREBASE_URL: return None
    try:
        url = f"{config.FIREBASE_URL}/settings/vuotlink_cookie.json"
        res = requests.get(url)
        if res.status_code == 200 and res.json():
            return res.json()
    except Exception as e:
        print(f"Lỗi đọc Firebase: {e}")
    return None

# --- KHỞI ĐỘNG: Cập nhật Cookie từ Database ---
saved_cookie = get_cookie_from_firebase()
if saved_cookie:
    CURRENT_COOKIE = saved_cookie
    print("✅ Đã load Cookie từ Firebase!")
else:
    print("⚠️ Dùng Cookie mặc định từ Env.")

# --- CÁC LỆNH ---

async def command_setcookie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh thay đổi Cookie nóng: /setcookie <cookie_mới>"""
    user_id = update.effective_user.id
    
    # 1. Bảo mật: Chỉ Admin mới được đổi
    # Nếu fen chưa biết ID, hãy bảo bot print(user_id) ra để xem
    # Hoặc tạm thời bỏ qua check nếu fen dùng bot 1 mình
    # if user_id not in ADMIN_IDS:
    #     await update.message.reply_text("⛔ Bạn không có quyền đổi Cookie!")
    #     return

    # 2. Lấy nội dung cookie
    try:
        # Lấy toàn bộ nội dung sau chữ /setcookie
        new_cookie = update.message.text.split(maxsplit=1)[1].strip()
    except IndexError:
        await update.message.reply_text("⚠️ Cách dùng: `/setcookie lang=vi_VN;...`", parse_mode="Markdown")
        return

    # 3. Cập nhật
    global CURRENT_COOKIE
    CURRENT_COOKIE = new_cookie # Cập nhật vào RAM
    
    # Chạy thread riêng để lưu vào Firebase (tránh lag bot)
    await asyncio.to_thread(save_cookie_to_firebase, new_cookie)
    
    await update.message.reply_text("✅ **ĐÃ CẬP NHẬT COOKIE MỚI!**\nBot đã sẵn sàng bypass mà không cần restart.", parse_mode="Markdown")

async def command_bat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    BYPASS_USERS.add(update.effective_user.id)
    await update.message.reply_text("🟢 **ĐÃ BẬT BYPASS!**")

async def command_tat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in BYPASS_USERS:
        BYPASS_USERS.remove(update.effective_user.id)
    await update.message.reply_text("🔴 **ĐÃ TẮT BYPASS!**")

async def bypass_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg_text = update.message.text.strip()
    
    if user_id not in BYPASS_USERS: return
    if "vuotlink.vip" not in msg_text: return

    status_msg = await update.message.reply_text("🕵️‍♂️ Đang soi link với Cookie mới nhất...")

    # Cấu hình Request
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Cookie': CURRENT_COOKIE, # <--- Dùng biến toàn cục đã cập nhật
        'Referer': 'https://vuotlink.vip/'
    }

    try:
        response = await asyncio.to_thread(requests.get, msg_text, headers=headers, allow_redirects=False, timeout=15)
        
        if response.status_code in [301, 302, 303, 307]:
            final_link = response.headers.get('Location')
            await status_msg.edit_text(f"✅ **LINK GỐC:**\n**{final_link}**", parse_mode="Markdown")
        elif response.status_code == 200:
            # Code xử lý HTML Redirect (như cũ)
            html = response.text
            import re
            link = None
            m = re.search(r'window\.location\.href\s*=\s*["\'](.*?)["\']', html)
            if m: link = m.group(1)
            
            if link:
                 await status_msg.edit_text(f"✅ **LINK GỐC:**\n\n**{link}**", parse_mode="Markdown")
            else:
                 await status_msg.edit_text("❌ Cookie có thể đã chết. Hãy dùng /setcookie để đổi cái mới!")
        else:
            await status_msg.edit_text(f"❌ Lỗi HTTP: {response.status_code}")

    except Exception as e:
        await status_msg.edit_text(f"❌ Lỗi: {e}")

def register_feature7(app):
    app.add_handler(CommandHandler("setcookie", command_setcookie)) # <--- Đăng ký lệnh mới
    app.add_handler(CommandHandler("bat", command_bat))
    app.add_handler(CommandHandler("tat", command_tat))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.Regex(r'^/') & filters.Regex(r"vuotlink\.vip"), bypass_logic), group=10)
