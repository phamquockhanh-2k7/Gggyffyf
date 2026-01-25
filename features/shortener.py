import aiohttp
import re
import urllib.parse
import asyncio
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, filters
from .storage import check_channel_membership
import config 

URL_PATTERN = r'(https?://\S+|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\S*)'

async def get_short_link(long_url, api_url, api_key, original_domain, mask_domain):
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
    t1, t2, t3 = await asyncio.gather(
        get_short_link(url, config.URL_API_VUOTLINK, config.API_KEY_VUOTLINK, config.ORIGIN_DOMAIN_VUOTLINK, config.DOMAIN_MASK_VUOTLINK),
        get_short_link(url, config.URL_API_LINKX, config.API_KEY_LINKX, config.ORIGIN_DOMAIN_LINKX, config.DOMAIN_MASK_LINKX),
        get_short_link(url, config.URL_API_ANON, config.API_KEY_ANON, config.ORIGIN_DOMAIN_ANON, config.DOMAIN_MASK_ANON)
    )

    raw_content = (
        f"**Link mua: (rẻ hơn )**\n {t2}\n"
        f"**Link mua:**\n {t3}\n"
        f"**Link vượt: **\n {t1}\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"**😘Nếu mua link hãy chọn linkx hoặc anonlink để mua giá rẻ hơn, nếu vượt link hãy dùng oklink, có thể mua nhưng sẽ đắt hơn! **\n\n"
        f"**Cách vượt Link: ** HuongDanVuotLink.vercel.app\n\n"
        f"**Cách Mua link: ** HuongDanMuaLink.vercel.app \n\n**⫸Lưu lại link này để tránh lạc mất nhau: **LinkDuPhongSOS.vercel.app 🥰\n\n"
        f"**👉Copy link: ** `LinkDuPhongSOS.vercel.app` "
    )
    return raw_content

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
        content = await generate_shortened_content(url)
        await update.message.reply_text(f"🔗 Link gốc: <code>{url}</code>", disable_web_page_preview=True)
        await update.message.reply_text(f"<pre>{content}</pre>", parse_mode="HTML")
        await asyncio.sleep(0.5)

def register_feature2(app):
    app.add_handler(CommandHandler("api", api_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_api_message), group=1)
