import aiohttp
import re
import urllib.parse
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, filters
from feature1 import check_channel_membership

# --- CẤU HÌNH API ---
API_KEY = "5d2e33c19847dea76f4fdb49695fd81aa669af86"
API_URL = "https://oklink.cfd/api"

# Pattern Regex để tìm link (nhận diện cả abc.com và http://abc.com)
URL_PATTERN = r'(https?://\S+|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\S*)'

async def get_short_link(long_url: str) -> str:
    """Gọi API rút gọn link theo định dạng TEXT từ tài liệu"""
    # Chuẩn hóa link: Nếu thiếu http/https thì thêm vào để API không lỗi
    if not long_url.startswith(("http://", "https://")):
        long_url = "https://" + long_url
    
    # Encode URL để tránh lỗi ký tự đặc biệt
    encoded_url = urllib.parse.quote(long_url)
    
    # Xây dựng URL gọi API theo mẫu format=text
    final_api_call = f"{API_URL}?api={API_KEY}&url={encoded_url}&format=text"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(final_api_call, timeout=10) as response:
                if response.status == 200:
                    result = await response.text()
                    return result.strip() if result else long_url
                return long_url
    except Exception as e:
        print(f"Lỗi API: {e}")
        return long_url

async def api_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh bật/tắt chế độ rút gọn: /api on hoặc /api off"""
    if not update.message or not await check_channel_membership(update, context): return
    
    args = context.args
    if args and args[0].lower() == "on":
        context.user_data['current_mode'] = 'API'
        await update.message.reply_text("🚀 **Đã BẬT** chế độ rút gọn link tự động!\n*(Nhận diện mọi định dạng abc.com)*")
    elif args and args[0].lower() == "off":
        context.user_data['current_mode'] = None
        await update.message.reply_text("💤 **Đã TẮT** chế độ rút gọn link.")

async def handle_api_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Chỉ quét link trong văn bản và trả về kết quả rút gọn"""
    if not update.message or not await check_channel_membership(update, context): return
    if context.user_data.get('current_mode') != 'API': return

    text = update.message.text or ""
    # Tìm tất cả link có trong tin nhắn
    urls = re.findall(URL_PATTERN, text)
    
    if not urls: return

    # Thông báo đang xử lý nếu có nhiều link
    processing_msg = None
    if len(urls) > 1:
        processing_msg = await update.message.reply_text("🔄 Đang rút gọn danh sách link...")

    shortened_results = []
    for url in urls:
        short = await get_short_link(url)
        shortened_results.append(short)

    if shortened_results:
        # Xóa thông báo "đang xử lý" nếu có
        if processing_msg: await processing_msg.delete()
        
        # Gửi danh sách link rút gọn cuối cùng
        response_text = "🔗 Link đã rút gọn:\n\n" + "\n".join(shortened_results)
        await update.message.reply_text(response_text, disable_web_page_preview=True)

def register_feature2(app):
    app.add_handler(CommandHandler("api", api_command))
    # Chạy ở Group 1 để không ảnh hưởng đến logic lưu trữ của Feature 1
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_api_message), group=1)
