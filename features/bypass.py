import requests
import asyncio
import re
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, filters
import config

# Danh sách người dùng đang BẬT chế độ Bypass
BYPASS_USERS = set()

async def command_bat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    BYPASS_USERS.add(user_id)
    await update.message.reply_text("🟢 **ĐÃ BẬT BYPASS PRO!**\nGửi link vào đây, tôi sẽ giả lập Chrome để xử lý.", parse_mode="Markdown")

async def command_tat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in BYPASS_USERS:
        BYPASS_USERS.remove(user_id)
    await update.message.reply_text("🔴 **ĐÃ TẮT BYPASS!**", parse_mode="Markdown")

async def bypass_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg_text = update.message.text.strip()
    
    if user_id not in BYPASS_USERS: return
    if "vuotlink.vip" not in msg_text: return

    status_msg = await update.message.reply_text("🕵️‍♂️ Đang giả lập Chrome VIP để vào link...")

    # --- 🛠 CẤU HÌNH GIẢ LẬP TRÌNH DUYỆT (QUAN TRỌNG) ---
    # Phải giống hệt cái trình duyệt fen lấy Cookie
    headers = {
        'Authority': 'vuotlink.vip',
        'Method': 'GET',
        'Scheme': 'https',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
        'Cache-Control': 'max-age=0',
        'Cookie': config.VUOTLINK_PRO_COOKIE,  # <--- Cookie VIP
        'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }

    try:
        # allow_redirects=True: Để nó tự nhảy qua các bước trung gian nếu có
        response = await asyncio.to_thread(requests.get, msg_text, headers=headers, allow_redirects=False, timeout=15)
        
        # --- TRƯỜNG HỢP 1: SERVER TRẢ VỀ MÃ CHUYỂN HƯỚNG (301, 302) ---
        if response.status_code in [301, 302, 303, 307]:
            final_link = response.headers.get('Location')
            await status_msg.edit_text(f"✅ **LINK GỐC (Header):**\n\n`{final_link}`", parse_mode="Markdown")
            return

        # --- TRƯỜNG HỢP 2: SERVER TRẢ VỀ 200 (CÓ THỂ LÀ HTML REDIRECT) ---
        if response.status_code == 200:
            html_content = response.text
            
            # Debug: In ra tiêu đề trang xem nó đang ở đâu
            page_title = "Không tìm thấy tiêu đề"
            title_match = re.search(r'<title>(.*?)</title>', html_content, re.IGNORECASE)
            if title_match:
                page_title = title_match.group(1)
            
            # Tìm link trong thẻ meta refresh (ví dụ: content="0;url=xyz")
            meta_refresh = re.search(r'content=["\']\d+;\s*url=(.*?)["\']', html_content, re.IGNORECASE)
            
            # Tìm link window.location trong Javascript
            js_redirect = re.search(r'window\.location\.href\s*=\s*["\'](.*?)["\']', html_content, re.IGNORECASE)
            
            final_link = None
            if meta_refresh:
                final_link = meta_refresh.group(1)
            elif js_redirect:
                final_link = js_redirect.group(1)
            
            if final_link:
                await status_msg.edit_text(f"✅ **LINK GỐC (HTML):**\n\n`{final_link}`", parse_mode="Markdown")
            else:
                # Nếu không thấy link, báo lỗi kèm Tiêu đề trang để debug
                await status_msg.edit_text(f"❌ **THẤT BẠI!** (Status 200)\n\nBot đang kẹt ở trang: **{page_title}**\n\n👉 Có thể Cookie hết hạn hoặc bị Cloudflare chặn.")
        
        else:
            await status_msg.edit_text(f"❌ Lỗi HTTP: {response.status_code}")

    except Exception as e:
        await status_msg.edit_text(f"❌ Lỗi kết nối: {e}")

def register_feature7(app):
    app.add_handler(CommandHandler("bat", command_bat))
    app.add_handler(CommandHandler("tat", command_tat))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(r"vuotlink\.vip"), bypass_logic), group=10)
