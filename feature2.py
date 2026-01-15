import aiohttp
import re
import urllib.parse
import asyncio
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, filters
from feature1 import check_channel_membership

# --- CẤU HÌNH API ---

# 1. Oklink (Vuotlink)
API_KEY_1 = "5d2e33c19847dea76f4fdb49695fd81aa669af86"
API_URL_1 = "https://oklink.cfd/api"

# 2. LinkX (ĐÃ SỬA: Dùng API rút gọn chuẩn)
API_KEY_2 = "4a06a2345a0e4ca098f9bf7b37a246439d5912e5"
API_URL_2 = "https://linkx.me/api"  # Đổi từ /note-api thành /api

# 3. AnonLink
API_KEY_3 = "b0bb16d8f14caaf4bfb6f8a0cceac1a8ee5e9668"
API_URL_3 = "https://anonlink.io/api"

# Regex tìm link
URL_PATTERN = r'(https?://\S+|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\S*)'

async def get_short_oklink(long_url: str) -> str:
    """Rút gọn bằng Oklink"""
    if not long_url.startswith(("http://", "https://")): long_url = "https://" + long_url
    encoded_url = urllib.parse.quote(long_url)
    url = f"{API_URL_1}?api={API_KEY_1}&url={encoded_url}&format=text"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                return (await resp.text()).strip() if resp.status == 200 else "Lỗi Oklink"
    except: return "Lỗi kết nối Oklink"

async def get_short_linkx(long_url: str) -> str:
    """Rút gọn bằng LinkX (Chuẩn Shortener)"""
    if not long_url.startswith(("http://", "https://")): long_url = "https://" + long_url
    encoded_url = urllib.parse.quote(long_url)
    
    # SỬA LỖI Ở ĐÂY: Dùng tham số 'url' thay vì 'content'
    url = f"{API_URL_2}?api={API_KEY_2}&url={encoded_url}&format=text"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                return (await resp.text()).strip() if resp.status == 200 else "Lỗi LinkX"
    except: return "Lỗi kết nối LinkX"

async def get_short_anonlink(long_url: str) -> str:
    """Rút gọn bằng AnonLink"""
    if not long_url.startswith(("http://", "https://")): long_url = "https://" + long_url
    encoded_url = urllib.parse.quote(long_url)
    url = f"{API_URL_3}?api={API_KEY_3}&url={encoded_url}&format=text"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                return (await resp.text()).strip() if resp.status == 200 else "Lỗi AnonLink"
    except: return "Lỗi kết nối AnonLink"

async def api_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bật tắt tính năng"""
    if not update.message or not await check_channel_membership(update, context): return
    args = context.args
    if args and args[0].lower() == "on":
        context.user_data['current_mode'] = 'API'
        await update.message.reply_text("🚀 **Đã BẬT** chế độ rút gọn 3 Server (Oklink, LinkX, AnonLink)!")
    elif args and args[0].lower() == "off":
        context.user_data['current_mode'] = None
        await update.message.reply_text("💤 **Đã TẮT** chế độ rút gọn link.")

async def handle_api_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý và trả về 3 link"""
    if not update.message or not await check_channel_membership(update, context): return
    if context.user_data.get('current_mode') != 'API': return

    text = update.message.text or ""
    urls = re.findall(URL_PATTERN, text)
    if not urls: return

    if len(urls) > 1:
        processing_msg = await update.message.reply_text("🔄 Đang xử lý danh sách link...")
    else:
        processing_msg = None

    final_results = []
    
    for url in urls:
        # Chạy song song 3 tác vụ bất đồng bộ
        task1 = asyncio.create_task(get_short_oklink(url))
        task2 = asyncio.create_task(get_short_linkx(url))
        task3 = asyncio.create_task(get_short_anonlink(url))
        
        # Chờ cả 3 xong
        l1, l2, l3 = await asyncio.gather(task1, task2, task3)

        res_block = (
            f"🔗 **Gốc:** `{url}`\n"
            f"1️⃣ **Oklink:** {l1}\n"
            f"2️⃣ **LinkX:** {l2}\n"
            f"3️⃣ **AnonLink:** {l3}"
        )
        final_results.append(res_block)

    if final_results:
        if processing_msg: await processing_msg.delete()
        
        footer = "\n➖➖➖➖➖\n📢 *Bot Rút Gọn Link Đa Năng*"
        response_text = "✅ **KẾT QUẢ RÚT GỌN:**\n\n" + "\n\n".join(final_results) + footer
        await update.message.reply_text(response_text, disable_web_page_preview=True, parse_mode="Markdown")

def register_feature2(app):
    app.add_handler(CommandHandler("api", api_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_api_message), group=1)
