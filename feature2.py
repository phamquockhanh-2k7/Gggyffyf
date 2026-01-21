import aiohttp
import re
import urllib.parse
import asyncio
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, filters
# Lưu ý: Import này chỉ dùng cho các hàm handler, tránh dùng ở cấp độ toàn cục nếu không cần thiết
from feature1 import check_channel_membership

# ==============================================================================
# ⚙️ CẤU HÌNH API & TÊN MIỀN VERCEL
# ==============================================================================

API_KEY_1 = "5d2e33c19847dea76f4fdb49695fd81aa669af86"
API_URL_1 = "https://vuotlink.vip/api" 
DOMAIN_MASK_1 = "GoToLink.vercel.app" 

API_KEY_2 = "4a06a2345a0e4ca098f9bf7b37a246439d5912e5"
API_URL_2 = "https://linkx.me/api"
DOMAIN_MASK_2 = "BuyThisLink.vercel.app" 

API_KEY_3 = "b0bb16d8f14caaf4bfb6f8a0cceac1a8ee5e9668"
API_URL_3 = "https://anonlink.io/api"
DOMAIN_MASK_3 = "MuaLinkNay.vercel.app" 

URL_PATTERN = r'(https?://\S+|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\S*)'

# ==============================================================================
# 🚀 HÀM RÚT GỌN & TẠO NỘI DUNG (CORE LOGIC)
# ==============================================================================

async def get_short_link(long_url, api_url, api_key, original_domain, mask_domain):
    """Hàm rút gọn đơn lẻ"""
    if not long_url.startswith(("http://", "https://")): long_url = "https://" + long_url
    encoded_url = urllib.parse.quote(long_url)
    req_url = f"{api_url}?api={api_key}&url={encoded_url}&format=text"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(req_url, timeout=10) as resp:
                if resp.status == 200:
                    short_link = (await resp.text()).strip()
                    return short_link.replace(original_domain, mask_domain)
                return "Lỗi API"
    except: return "Lỗi Mạng"

async def generate_shortened_content(url):
    """
    Hàm này chạy song song 3 API và trả về nội dung text đã định dạng.
    Feature 1 sẽ gọi hàm này.
    """
    t1, t2, t3 = await asyncio.gather(
        get_short_link(url, API_URL_1, API_KEY_1, "vuotlink.vip", DOMAIN_MASK_1),
        get_short_link(url, API_URL_2, API_KEY_2, "linkx.me", DOMAIN_MASK_2),
        get_short_link(url, API_URL_3, API_KEY_3, "anonlink.io", DOMAIN_MASK_3)
    )

    # Nội dung định dạng chuẩn theo yêu cầu của bạn
    raw_content = (
        f"**Link mua: (rẻ hơn )**\n {t2}\n"
        f"**Link mua:**\n {t3}\n"
        f"**Link vượt: **\n {t1}\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"**😘Nếu mua link hãy chọn linkx hoặc anonlink để mua giá rẻ hơn, nếu vượt link hãy dùng oklink, có thể mua nhưng sẽ đắt hơn! **\n\n"
        f"**Cách vượt Link: ** HuongDanVuotLink.vercel.app\n\n"
        f"**Cách Mua link: ** HuongDanMuaLink.vercel.app \n\n**⫸Lưu lại link này để tránh lạc mất nhau: **LinkDuPhongSOS.vercel.app 🥰"
    )
    return raw_content

# ==============================================================================
# 🎮 HANDLERS (XỬ LÝ TIN NHẮN)
# ==============================================================================

async def api_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not await check_channel_membership(update, context): return
    args = context.args
    if args and args[0].lower() == "on":
        context.user_data['current_mode'] = 'API'
        await update.message.reply_text("🚀 Đã BẬT chế độ rút gọn đa năng! (Ấn link Start sẽ tự rút gọn luôn)")
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
        # Gọi hàm chung để lấy nội dung
        content = await generate_shortened_content(url)
        
        await update.message.reply_text(f"🔗 Link gốc: {url}", disable_web_page_preview=True)
        await update.message.reply_text(f"<pre>{content}</pre>", parse_mode="HTML")
        await asyncio.sleep(0.5)

def register_feature2(app):
    app.add_handler(CommandHandler("api", api_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_api_message), group=1)
