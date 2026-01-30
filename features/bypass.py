import requests
import asyncio
import re
import json
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, filters
import config
from urllib.parse import urlparse

# ==============================================================================
# ⚙️ CẤU HÌNH DANH SÁCH TÊN MIỀN (THÊM BAO NHIÊU CŨNG ĐƯỢC)
# ==============================================================================
# Fen cứ thấy link nào cùng hệ thống vuotlink thì ném vào đây
TARGET_DOMAINS = [
    "vuotlink.vip",
    "oklink.cfd",
    "link1s.com",
    "traffic123.net"
    # Thêm tiếp vào đây...
]

# Tạo Regex tự động từ danh sách trên (để Bot nhận diện tin nhắn)
# Nó sẽ tạo ra dạng: (vuotlink\.vip|oklink\.fg|...)
DOMAIN_REGEX = r"(" + "|".join([re.escape(d) for d in TARGET_DOMAINS]) + ")"


# --- CẤU HÌNH KHÁC ---
ADMIN_IDS = [123456789, 987654321]  # ID Admin
CURRENT_COOKIE = config.VUOTLINK_PRO_COOKIE 
BYPASS_USERS = set()

# ==============================================================================
# 🛠 CÁC HÀM HỖ TRỢ
# ==============================================================================

def save_cookie_to_firebase(cookie_value):
    if not config.FIREBASE_URL: return
    try:
        url = f"{config.FIREBASE_URL}/settings/vuotlink_cookie.json"
        requests.put(url, json=cookie_value)
    except Exception as e:
        print(f"Lỗi lưu Firebase: {e}")

def get_cookie_from_firebase():
    if not config.FIREBASE_URL: return None
    try:
        url = f"{config.FIREBASE_URL}/settings/vuotlink_cookie.json"
        res = requests.get(url)
        if res.status_code == 200 and res.json():
            return res.json()
    except Exception as e:
        print(f"Lỗi đọc Firebase: {e}")
    return None

# Load cookie lúc khởi động
saved_cookie = get_cookie_from_firebase()
if saved_cookie:
    CURRENT_COOKIE = saved_cookie
    print("✅ Đã load Cookie từ Firebase!")
else:
    print("⚠️ Dùng Cookie mặc định từ Env.")

def is_target_domain(url):
    """Kiểm tra xem URL có thuộc danh sách mình hỗ trợ không"""
    for domain in TARGET_DOMAINS:
        if domain in url:
            return True
    return False

# ==============================================================================
# 🎮 LOGIC XỬ LÝ CHÍNH
# ==============================================================================

async def command_setcookie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        new_cookie = update.message.text.split(maxsplit=1)[1].strip()
        global CURRENT_COOKIE
        CURRENT_COOKIE = new_cookie
        await asyncio.to_thread(save_cookie_to_firebase, new_cookie)
        await update.message.reply_text("✅ **ĐÃ CẬP NHẬT COOKIE MỚI!**", parse_mode="Markdown")
    except IndexError:
        await update.message.reply_text("⚠️ Cách dùng: `/setcookie lang=vi_VN;...`", parse_mode="Markdown")

async def command_bat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    BYPASS_USERS.add(update.effective_user.id)
    await update.message.reply_text(f"🟢 **ĐÃ BẬT BYPASS!**\nHỗ trợ: {', '.join(TARGET_DOMAINS)}")

async def command_tat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in BYPASS_USERS:
        BYPASS_USERS.remove(update.effective_user.id)
    await update.message.reply_text("🔴 **ĐÃ TẮT BYPASS!**")

async def bypass_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg_text = update.message.text.strip()
    
    # Check 1: User có bật mode bypass không?
    if user_id not in BYPASS_USERS: return
    
    # Check 2: Link có nằm trong danh sách hỗ trợ không?
    if not is_target_domain(msg_text): return

    status_msg = await update.message.reply_text("🕵️‍♂️ Đang truy vết link gốc...")

    # Cấu hình Request
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Cookie': CURRENT_COOKIE, 
        # Mẹo: Referer để chính cái link đang gửi để server đỡ nghi
        'Referer': 'https://vuotlink.vip/' 
    }

    def run_check():
        current_url = msg_text
        max_hops = 5 # Chống lặp vô tận
        
        # VÒNG LẶP RƯỢT ĐUỔI
        # Nếu link trả về vẫn là link vuotlink (hoặc oklink), bot sẽ request tiếp
        for _ in range(max_hops):
            try:
                # allow_redirects=False để tự mình kiểm soát từng bước nhảy
                res = requests.get(current_url, headers=headers, allow_redirects=False, timeout=15)
                
                # TRƯỜNG HỢP 1: Gặp chuyển hướng (301, 302)
                if res.status_code in [301, 302, 303, 307]:
                    next_link = res.headers.get('Location')
                    
                    # Nếu link mới VẪN LÀ link rút gọn (ví dụ oklink -> vuotlink) -> Lặp tiếp
                    if is_target_domain(next_link):
                        current_url = next_link
                        continue # Quay lại đầu vòng lặp
                    else:
                        return next_link # ✅ Tìm thấy link lạ (Google Drive,...) -> Trả về luôn
                
                # TRƯỜNG HỢP 2: Gặp 200 OK (Có thể là HTML Redirect)
                elif res.status_code == 200:
                    html = res.text
                    # Quét link ẩn trong HTML
                    link_match = re.search(r'window\.location\.href\s*=\s*["\'](.*?)["\']', html)
                    if not link_match:
                         link_match = re.search(r'content=["\']\d+;\s*url=(.*?)["\']', html)
                    
                    if link_match:
                        found_link = link_match.group(1)
                         # Tương tự: Nếu link tìm thấy vẫn là link rút gọn -> Lặp tiếp
                        if is_target_domain(found_link):
                            current_url = found_link
                            continue
                        else:
                            return found_link # ✅ Link gốc đây rồi
                    else:
                        return "ERROR_COOKIE" # Vào được trang nhưng không thấy link -> Cookie chết
                else:
                    return f"ERROR_HTTP_{res.status_code}"

            except Exception as e:
                return str(e)
        
        return "ERROR_LOOP" # Quá số lần nhảy

    # Chạy logic
    result = await asyncio.to_thread(run_check)

    if result.startswith("http"):
        # Format đẹp nếu là Google Drive
        display_link = f"{result}"
        if "drive.google.com" in result:
            display_link = f"📂 **GOOGLE DRIVE:**\n{display_link}"
            
        await status_msg.edit_text(f"✅ **BẮT ĐƯỢC LINK:**\n{display_link}", parse_mode="Markdown")
    elif result == "ERROR_COOKIE":
        await status_msg.edit_text("❌ Cookie đã hết hạn hoặc không đúng cho domain này. Dùng /setcookie để đổi!")
    else:
        await status_msg.edit_text(f"❌ Thất bại: {result}")

def register_feature7(app):
    app.add_handler(CommandHandler("setcookie", command_setcookie))
    app.add_handler(CommandHandler("bat", command_bat))
    app.add_handler(CommandHandler("tat", command_tat))
    
    # 🌟 MAGIC: Bot sẽ lắng nghe tất cả các domain trong list TARGET_DOMAINS
    app.add_handler(MessageHandler(filters.TEXT & ~filters.Regex(r'^/') & filters.Regex(DOMAIN_REGEX), bypass_logic), group=10)
