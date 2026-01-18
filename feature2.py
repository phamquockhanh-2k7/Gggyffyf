import aiohttp
import re
import urllib.parse
import asyncio
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, filters
from feature1 import check_channel_membership

# ==============================================================================
# ⚙️ CẤU HÌNH API & TÊN MIỀN VERCEL
# ==============================================================================

# 1. OKLINK (Vuotlink) -> Mask thành: GoToLink.vercel.app
API_KEY_1 = "5d2e33c19847dea76f4fdb49695fd81aa669af86"
API_URL_1 = "https://vuotlink.vip/api" # (Lưu ý: Bạn gửi link này là vuotlink.vip chứ ko phải oklink)
DOMAIN_MASK_1 = "GoToLink.vercel.app" # <--- Tên miền Vercel 1

# 2. LINKX -> Mask thành: BuyThisLink.vercel.app
API_KEY_2 = "4a06a2345a0e4ca098f9bf7b37a246439d5912e5"
API_URL_2 = "https://linkx.me/api"
DOMAIN_MASK_2 = "BuyThisLink.vercel.app" # <--- Tên miền Vercel 2

# 3. ANONLINK -> Mask thành: MuaLinkNay.vercel.app
API_KEY_3 = "b0bb16d8f14caaf4bfb6f8a0cceac1a8ee5e9668"
API_URL_3 = "https://anonlink.io/api"
DOMAIN_MASK_3 = "MuaLinkNay.vercel.app" # <--- Tên miền Vercel 3

URL_PATTERN = r'(https?://\S+|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\S*)'

# ==============================================================================
# 🚀 HÀM RÚT GỌN (CÓ MASKING)
# ==============================================================================

async def get_short_link(long_url, api_url, api_key, original_domain, mask_domain):
    """Hàm rút gọn chung cho cả 3 loại"""
    if not long_url.startswith(("http://", "https://")): long_url = "https://" + long_url
    encoded_url = urllib.parse.quote(long_url)
    
    # Gọi API
    req_url = f"{api_url}?api={api_key}&url={encoded_url}&format=text"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(req_url, timeout=10) as resp:
                if resp.status == 200:
                    short_link = (await resp.text()).strip() # Ví dụ: https://vuotlink.vip/123
                    
                    # 👉 XỬ LÝ MASKING TẠI ĐÂY
                    # Thay thế domain gốc (vuotlink.vip) bằng domain Vercel (GoToLink...)
                    masked_link = short_link.replace(original_domain, mask_domain)
                    
                    return masked_link
                else:
                    return "Lỗi API"
    except: 
        return "Lỗi Mạng"

# ==============================================================================
# 🎮 XỬ LÝ LỆNH VÀ TIN NHẮN
# ==============================================================================

async def api_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not await check_channel_membership(update, context): return
    args = context.args
    if args and args[0].lower() == "on":
        context.user_data['current_mode'] = 'API'
        await update.message.reply_text("🚀 Đã BẬT chế độ rút gọn đa năng!")
    elif args and args[0].lower() == "off":
        context.user_data['current_mode'] = None
        await update.message.reply_text("💤 Đã TẮT chế độ rút gọn.")

async def handle_api_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not await check_channel_membership(update, context): return
    
    # Chỉ chạy khi đã BẬT chế độ /api on
    if context.user_data.get('current_mode') != 'API': return

    text = update.message.text or ""
    urls = re.findall(URL_PATTERN, text)
    if not urls: return

    # Thông báo đang xử lý (vì chạy 3 cái hơi lâu)
    # processing_msg = await update.message.reply_text("⏳ Đang tạo 3 link mask...")

    for url in urls:
        # Chạy song song 3 tác vụ rút gọn
        t1, t2, t3 = await asyncio.gather(
            # Link 1: Vuotlink -> GoToLink
            get_short_link(url, API_URL_1, API_KEY_1, "vuotlink.vip", DOMAIN_MASK_1),
            
            # Link 2: LinkX -> BuyThisLink
            get_short_link(url, API_URL_2, API_KEY_2, "linkx.me", DOMAIN_MASK_2),
            
            # Link 3: AnonLink -> MuaLinkNay
            get_short_link(url, API_URL_3, API_KEY_3, "anonlink.io", DOMAIN_MASK_3)
        )

        # Xóa tin nhắn chờ (nếu có)
        # try: await processing_msg.delete()
        # except: pass

        # Tạo nội dung trả về
        label_1 = "**Link vượt: **"          
        label_2 = "**Link mua: (rẻ hơn )**" 
        label_3 = "**Link mua:**"            
        
        footer = (
            "\n➖➖➖➖➖➖\n"
            "<b>😘Nếu mua link hãy chọn linkx hoặc anonlink để mua giá rẻ hơn, nếu vượt link hãy dùng oklink, có thể mua nhưng sẽ đắt hơn!</b>\n\n"
            "<b>Cách vượt Link:</b> https://t.me/upbaiviet_robot?start=BQADAQADaAoAArCTQEdcuTQeEAQaWxYE\n\n"
            "<b>Cách Mua link:</b> https://t.me/upbaiviet_robot?start=BQADAQADdAoAArCTQEd1zU69QpPMShYE"
        )
        
        content_to_copy = (
            f"{label_2}\n {t2}\n" # LinkX (BuyThisLink)
            f"{label_3}\n {t3}\n" # AnonLink (MuaLinkNay)
            f"{label_1}\n {t1}"   # Vuotlink (GoToLink)
            f"{footer}" 
        )
        
        # Gửi dạng Markdown (để copy) nhưng footer dạng HTML
        await update.message.reply_text(f"🔗 Gốc: {url}", disable_web_page_preview=True)
        
        # Vì bạn muốn trộn Markdown và HTML nên gửi làm 2 tin hoặc dùng HTML toàn bộ
        # Ở đây tôi dùng HTML toàn bộ cho đẹp và dễ copy
        
        final_msg = (
            f"<b>{label_2.replace('**','')}</b>\n{t2}\n"
            f"<b>{label_3.replace('**','')}</b>\n{t3}\n"
            f"<b>{label_1.replace('**','')}</b>\n{t1}\n"
            f"{footer}"
        )
        
        await update.message.reply_text(f"```\n{final_msg}\n```", parse_mode="HTML")
        await asyncio.sleep(0.5)

def register_feature2(app):
    app.add_handler(CommandHandler("api", api_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_api_message), group=1)
