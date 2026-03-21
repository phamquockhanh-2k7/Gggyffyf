import requests
import asyncio
import re
import json
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, filters
import config
import db
from urllib.parse import urlparse

# ==============================================================================
# ⚙️ CẤU HÌNH DANH SÁCH TÊN MIỀN
# ==============================================================================
TARGET_DOMAINS = [
    "vuotlink.vip",
    "oklink.cfd",
    "link1s.com",
    "traffic123.net",
    "shink.me"
]

DOMAIN_REGEX = r"(" + "|".join([re.escape(d) for d in TARGET_DOMAINS]) + ")"

# --- CẤU HÌNH KHÁC ---
ADMIN_IDS = [123456789] # Thay ID Admin vào
CURRENT_COOKIE = config.VUOTLINK_PRO_COOKIE 
BYPASS_USERS = set()

# ==============================================================================
# 🛠 CÁC HÀM HỖ TRỢ
# ==============================================================================

async def save_cookie(cookie_value):
    try:
        await db.set_storage_code("vuotlink_cookie", cookie_value)
    except Exception as e:
        print(f"Lỗi lưu Supabase: {e}")

async def get_cookie():
    try:
        return await db.get_storage_code("vuotlink_cookie")
    except Exception as e:
        print(f"Lỗi đọc Supabase: {e}")
    return None

def json_cookie_to_string(json_input):
    """Hàm thông minh: Chuyển JSON từ EditThisCookie thành chuỗi String chuẩn"""
    try:
        # Nếu input không bắt đầu bằng [ hoặc {, có thể là string thường -> Trả về luôn
        if not json_input.strip().startswith(("[", "{")):
            return json_input

        data = json.loads(json_input)
        cookie_parts = []
        
        # Nếu là list (Export từ EditThisCookie)
        if isinstance(data, list):
            for item in data:
                # Chỉ lấy cookie của vuotlink, bỏ qua google, facebook...
                domain = item.get("domain", "")
                if "vuotlink" in domain or "oklink" in domain: 
                    name = item.get("name")
                    value = item.get("value")
                    cookie_parts.append(f"{name}={value}")
        
        # Ghép lại thành chuỗi chuẩn
        if cookie_parts:
            return "; ".join(cookie_parts)
        else:
            return json_input # Nếu không lọc được gì thì trả về nguyên gốc thử vận may
            
    except Exception as e:
        print(f"Lỗi parse JSON Cookie: {e}")
        return json_input # Lỗi thì trả về nguyên gốc

# Cookie is loaded dynamically in bypass_logic or command_setcookie

def is_target_domain(url):
    for domain in TARGET_DOMAINS:
        if domain in url: return True
    return False

# ==============================================================================
# 🎮 LOGIC XỬ LÝ CHÍNH
# ==============================================================================

async def command_setcookie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Lấy nội dung raw từ tin nhắn
        raw_content = update.message.text.split(maxsplit=1)[1].strip()
        
        # 🔥 TỰ ĐỘNG CHUYỂN ĐỔI JSON SANG STRING
        final_cookie = json_cookie_to_string(raw_content)

        global CURRENT_COOKIE
        CURRENT_COOKIE = final_cookie
        
        await save_cookie(final_cookie)
        
        # Rút gọn cookie khi hiển thị để đỡ rối mắt
        display_cookie = final_cookie[:50] + "..." if len(final_cookie) > 50 else final_cookie
        await update.message.reply_text(f"✅ **ĐÃ CẬP NHẬT COOKIE!**\n\nBot đã tự động định dạng lại:\n`{display_cookie}`", parse_mode="Markdown")
        
    except IndexError:
        await update.message.reply_text("⚠️ Cách dùng: `/setcookie <dán_cookie_vào>`", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {e}")

async def command_bat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    BYPASS_USERS.add(update.effective_user.id)
    await update.message.reply_text(f"🟢 **ĐÃ BẬT BYPASS!**")

async def command_tat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in BYPASS_USERS:
        BYPASS_USERS.remove(update.effective_user.id)
    await update.message.reply_text("🔴 **ĐÃ TẮT BYPASS!**")

async def bypass_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg_text = update.message.text.strip()
    global CURRENT_COOKIE
    
    if user_id not in BYPASS_USERS: return
    if not is_target_domain(msg_text): return

    if not CURRENT_COOKIE:
        CURRENT_COOKIE = await get_cookie() or config.VUOTLINK_PRO_COOKIE

    status_msg = await update.message.reply_text("🕵️‍♂️ Đang truy vết link gốc...")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Cookie': CURRENT_COOKIE, 
        'Referer': 'https://vuotlink.vip/' 
    }

    def run_check():
        current_url = msg_text
        max_hops = 5
        
        for _ in range(max_hops):
            try:
                res = requests.get(current_url, headers=headers, allow_redirects=False, timeout=15)
                
                if res.status_code in [301, 302, 303, 307]:
                    next_link = res.headers.get('Location')
                    if is_target_domain(next_link):
                        current_url = next_link
                        continue 
                    else:
                        return next_link
                
                elif res.status_code == 200:
                    html = res.text
                    link_match = re.search(r'window\.location\.href\s*=\s*["\'](.*?)["\']', html)
                    if not link_match:
                         link_match = re.search(r'content=["\']\d+;\s*url=(.*?)["\']', html)
                    
                    if link_match:
                        found_link = link_match.group(1)
                        if is_target_domain(found_link):
                            current_url = found_link
                            continue
                        else:
                            return found_link
                    else:
                        return "ERROR_COOKIE"
                else:
                    return f"ERROR_HTTP_{res.status_code}"

            except Exception as e:
                return str(e)
        return "ERROR_LOOP"

    result = await asyncio.to_thread(run_check)

    if result.startswith("http"):
        display_link = f"{result}"
        if "drive.google.com" in result:
            display_link = f"📂 **GOOGLE DRIVE:**\n{display_link}"
        await status_msg.edit_text(f"✅ **BẮT ĐƯỢC LINK:**\n{display_link}", parse_mode="Markdown")
    elif result == "ERROR_COOKIE":
        await status_msg.edit_text("❌ Cookie đã chết hoặc bị chặn. Dùng /setcookie để cập nhật!")
    else:
        await status_msg.edit_text(f"❌ Thất bại: {result}")

def register_feature7(app):
    app.add_handler(CommandHandler("setcookie", command_setcookie))
    app.add_handler(CommandHandler("bat", command_bat))
    app.add_handler(CommandHandler("tat", command_tat))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.Regex(r'^/') & filters.Regex(DOMAIN_REGEX), bypass_logic), group=10)
