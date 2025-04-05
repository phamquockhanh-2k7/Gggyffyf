import requests
from telegram import Bot, Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import Application, MessageHandler, CommandHandler, filters, CallbackContext
import asyncio
import nest_asyncio
import random
from keep_alive import keep_alive

nest_asyncio.apply()

BOT_TOKEN = "8064426886:AAHNez92dmsVQBB6yQp65k_pjPwiJT-SBEI"
API_KEY = "5d2e33c19847dea76f4fdb49695fd81aa669af86"
API_URL = "https://vuotlink.vip/api"

bot = Bot(token=BOT_TOKEN)
media_groups = {}
processing_tasks = {}

async def start(update: Update, context: CallbackContext):
    if not update.message:
        return  
    if update.effective_chat.type != "private":
        return  
    await update.message.reply_text(
        "**👋 Chào mừng bạn!**"

"
        "**🔗 Gửi link bất kỳ để rút gọn.**"
"
        "**📷 Chuyển tiếp bài viết kèm ảnh/video, bot sẽ giữ nguyên caption & rút gọn link trong caption.**"
"
        "**💬 Mọi thắc mắc, hãy liên hệ admin.**",
        parse_mode="Markdown"
    )

async def format_text(text: str) -> str:
    """Rút gọn link, in đậm nội dung, và gạch ngang link"""
    lines = text.splitlines()
    new_lines = []
    for line in lines:
        words = line.split()
        new_words = []
        for word in words:
            if word.startswith("http"):
                params = {"api": API_KEY, "url": word, "format": "text"}
                response = requests.get(API_URL, params=params)
                short_link = response.text.strip() if response.status_code == 200 else word
                word = f"<s>{short_link}</s>"
            else:
                word = f"<b>{word}</b>"
            new_words.append(word)
        new_lines.append(" ".join(new_words))

    new_lines.append(
        '\n<b>Báo lỗi + đóng góp video tại đây</b> @nothinginthissss (có lỗi sẽ đền bù)\n'
        '<b>Theo dõi thông báo tại đây</b> @sachkhongchuu\n'
        '<b>CÁCH XEM LINK(lỗi bot không gửi video):</b> @HuongDanVuotLink_SachKhongChu\n\n'
        '⚠️<b>Kênh xem không cần vượt :</b> <a href="https://t.me/sachkhongchuu/299">ấn vào đây</a>'
    )

    return "\n".join(new_lines)

async def process_media_group(media_group_id: str, user_chat_id: int):
    """Xử lý bài viết có nhiều ảnh/video mà không bị chia nhỏ"""
    await asyncio.sleep(random.uniform(3, 5))  # Thêm delay ngẫu nhiên 3-5 giây
    messages = media_groups.pop(media_group_id, [])
    if not messages:
        return

    messages.sort(key=lambda m: m.message_id)
    media = []
    caption = None

    for i, message in enumerate(messages):
        if i == 0 and message.caption:
            caption = await format_text(message.caption)

        if message.photo:
            file_id = message.photo[-1].file_id
            media.append(InputMediaPhoto(media=file_id, caption=caption if i == 0 else None, parse_mode="HTML"))
        elif message.video:
            file_id = message.video.file_id
            media.append(InputMediaVideo(media=file_id, caption=caption if i == 0 else None, parse_mode="HTML"))

    if media:
        await bot.send_media_group(chat_id=user_chat_id, media=media)

async def shorten_link(update: Update, context: CallbackContext):
    if not update.message:
        return  
    if update.effective_chat.type != "private":
        return  

    if update.message.media_group_id:
        mgid = update.message.media_group_id

        if mgid not in media_groups:
            media_groups[mgid] = []
            processing_tasks[mgid] = asyncio.create_task(process_media_group(mgid, update.effective_chat.id))

        media_groups[mgid].append(update.message)
        return

    elif update.message.text and update.message.text.startswith("http"):
        params = {"api": API_KEY, "url": update.message.text.strip(), "format": "text"}
        response = requests.get(API_URL, params=params)
        if response.status_code == 200:
            short_link = response.text.strip()
            message = (
                "📢 <b>Bạn có link rút gọn mới</b>\n"
                f"🔗 <b>Link gốc:</b> <s>{update.message.text}</s>\n"
                f"🔍 <b>Link rút gọn:</b> <s>{short_link}</s>\n\n"
                '⚠️<b>Kênh xem không cần vượt :</b> <a href="https://t.me/sachkhongchuu/299">ấn vào đây</a>'
            )
            await update.message.reply_text(message, parse_mode="HTML")

    elif update.message.forward_origin:
        caption = update.message.caption or ""
        new_caption = await format_text(caption)
        await update.message.copy(chat_id=update.effective_chat.id, caption=new_caption, parse_mode="HTML")

async def main():
    keep_alive()  # Giữ bot chạy
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, shorten_link))
    app.add_handler(MessageHandler(filters.FORWARDED, shorten_link))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, shorten_link))

    print("✅ Bot đang chạy...")

    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
