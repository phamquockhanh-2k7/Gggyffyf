import aiohttp
import re
import urllib.parse
import asyncio
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, filters
from feature1 import check_channel_membership

# --- CẤU HÌNH API ---
API_KEY_1 = "5d2e33c19847dea76f4fdb49695fd81aa669af86"
API_URL_1 = "https://oklink.cfd/api"

API_KEY_2 = "4a06a2345a0e4ca098f9bf7b37a246439d5912e5"
API_URL_2 = "https://linkx.me/api"

API_KEY_3 = "b0bb16d8f14caaf4bfb6f8a0cceac1a8ee5e9668"
API_URL_3 = "https://anonlink.io/api"

URL_PATTERN = r'(https?://\S+|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\S*)'

# --- CÁC HÀM RÚT GỌN (GIỮ NGUYÊN) ---
async def get_short_oklink(long_url: str) -> str:
    if not long_url.startswith(("http://", "https://")): long_url = "https://" + long_url
    encoded_url = urllib.parse.quote(long_url)
    url = f"{API_URL_1}?api={API_KEY_1}&url={encoded_url}&format=text"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                return (await resp.text()).strip() if resp.status == 200 else "Lỗi"
    except: return "Lỗi"

async def get_short_linkx(long_url: str) -> str:
    if not long_url.startswith(("http://", "https://")): long_url = "https://" + long_url
    encoded_url = urllib.parse.quote(long_url)
    url = f"{API_URL_2}?api={API_KEY_2}&url={encoded_url}&format=text"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                return (await resp.text()).strip() if resp.status == 200 else "Lỗi"
    except: return "Lỗi"

async def get_short_anonlink(long_url: str) -> str:
    if not long_url.startswith(("http://", "https://")): long_url = "https://" + long_url
    encoded_url = urllib.parse.quote(long_url)
    url = f"{API_URL_3}?api={API_KEY_3}&url={encoded_url}&format=text"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                return (await resp.text()).strip() if resp.status == 200 else "Lỗi"
    except: return "Lỗi"

async def api_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not await check_channel_membership(update, context): return
    args = context.args
    if args and args[0].lower() == "on":
        context.user_data['current_mode'] = 'API'
        await update.message.reply_text("🚀 Đã BẬT chế độ rút gọn!")
    elif args and args[0].lower() == "off":
        context.user_data['current_mode'] = None
        await update.message.reply_text("💤 Đã TẮT chế độ rút gọn.")

async def handle_api_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not await check_channel_membership(update, context): return
    if context.user_data.get('current_mode') != 'API': return

    text = update.message.text or ""
    urls = re.findall(URL_PATTERN, text)
    if not urls: return

    for url in urls:
        # Chạy song song 3 API
        t1, t2, t3 = await asyncio.gather(
            get_short_oklink(url), 
            get_short_linkx(url), 
            get_short_anonlink(url)
        )

        # --- GỬI TIN NHẮN 1: LINK GỐC ---
        await update.message.reply_text(f"🔗 Gốc: {url}", disable_web_page_preview=True)

        # --- CHUẨN BỊ TIN NHẮN 2: NỘI DUNG COPY ---
        label_1 = "Link vượt: "         
        label_2 = "Link mua: (rẻ hơn )" 
        label_3 = "Link mua:"           

        # 👇 Đây là đoạn Footer bạn cần 👇
        footer = "\n➖➖➖➖➖➖\n😘Nếu mua link hãy chọn linkx hoặc anonlink để mua giá rẻ hơn, nếu vượt link hãy dùng oklink, có thể mua nhưng sẽ đắt hơn!"

        # Ghép Link + Footer vào nội dung copy
        content_to_copy = (
            f"{label_2}\n {t2}\n"
            f"{label_3}\n {t3}\n"
            f"{label_1}\n {t1}"
            f"{footer}" 
        )

        # --- GỬI TIN NHẮN 2: DẠNG CODE ---
        # Bọc trong ``` để hiện dạng khung code
        await update.message.reply_text(f"```\n{content_to_copy}\n```", parse_mode="Markdown")
        
        await asyncio.sleep(0.5)

def register_feature2(app):
    app.add_handler(CommandHandler("api", api_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_api_message), group=1)
