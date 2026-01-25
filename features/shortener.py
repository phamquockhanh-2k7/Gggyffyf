import aiohttp
import re
import urllib.parse
import asyncio
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, filters
import config

# Import hàm check channel từ storage.py
from .storage import check_channel_membership 

URL_PATTERN = r'(https?://\S+|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\S*)'

async def get_short_link(long_url, api_url, api_key, original_domain, mask_domain):
    if not long_url.startswith(("http", "https")): long_url = "https://" + long_url
    encoded = urllib.parse.quote(long_url)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{api_url}?api={api_key}&url={encoded}&format=text", timeout=10) as resp:
                if resp.status == 200:
                    return (await resp.text()).strip().replace(original_domain, mask_domain)
                return "Lỗi API"
    except: return "Lỗi Mạng"

async def generate_shortened_content(url):
    t1, t2, t3 = await asyncio.gather(
        get_short_link(url, config.URL_API_VUOTLINK, config.API_KEY_VUOTLINK, config.ORIGIN_DOMAIN_VUOTLINK, config.DOMAIN_MASK_VUOTLINK),
        get_short_link(url, config.URL_API_LINKX, config.API_KEY_LINKX, config.ORIGIN_DOMAIN_LINKX, config.DOMAIN_MASK_LINKX),
        get_short_link(url, config.URL_API_ANON, config.API_KEY_ANON, config.ORIGIN_DOMAIN_ANON, config.DOMAIN_MASK_ANON)
    )
    return (f"**Mua (Rẻ):**\n {t2}\n**Mua:**\n {t3}\n**Vượt:**\n {t1}\n"
            f"➖➖➖➖\nNên dùng LinkX/AnonLink rẻ hơn!\n"
            f"HD Vượt: HuongDanVuotLink.vercel.app\nHD Mua: HuongDanMuaLink.vercel.app\nBackup: LinkDuPhongSOS.vercel.app")

async def api_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not await check_channel_membership(update, context): return
    if context.args and context.args[0].lower() == "on":
        context.user_data['current_mode'] = 'API'
        await update.message.reply_text("🚀 Đã BẬT Auto Rút gọn!")
    elif context.args and context.args[0].lower() == "off":
        context.user_data['current_mode'] = None
        await update.message.reply_text("💤 Đã TẮT.")

async def handle_api_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not await check_channel_membership(update, context): return
    if context.user_data.get('current_mode') != 'API': return
    urls = re.findall(URL_PATTERN, update.message.text or "")
    for url in urls:
        content = await generate_shortened_content(url)
        await update.message.reply_text(f"🔗 Gốc: <code>{url}</code>\n<pre>{content}</pre>", parse_mode="HTML", disable_web_page_preview=True)

def register_feature2(app):
    app.add_handler(CommandHandler("api", api_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_api_message), group=1)
