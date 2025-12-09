import requests
import random
import asyncio
from telegram import Update, InputMediaPhoto, InputMediaVideo, ParseMode
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, filters
from feature1 import check_channel_membership, user_files, data_lock # Import từ feature 1

# === Cấu hình ===
API_KEY = "5d2e33c19847dea76f4fdb49695fd81aa669af86"
API_URL = "https://vuotlink.vip/api"

# Bật/tắt tính năng cho từng user
user_api_enabled = {}

# Lưu nhóm media tạm
media_groups = {}


# 🆕 HÀM GỌI API ĐỒNG BỘ (Được gọi bên trong asyncio.to_thread)
def shorten_url_sync(url: str):
    params = {"api": API_KEY, "url": url, "format": "text"}
    try:
        # Sử dụng requests đồng bộ
        response = requests.get(API_URL, params=params, timeout=5)
        return response.text.strip() if response.status_code == 200 else url
    except Exception:
        return url

# ====== Hàm rút gọn link & định dạng caption ======
async def format_text(text: str) -> str:
    lines = text.splitlines()
    new_lines = []
    
    # Danh sách chứa tất cả các tác vụ rút gọn link
    shortening_tasks = [] 
    
    for line in lines:
        words = line.split()
        current_line_tasks = [] # Giữ các tác vụ cho dòng hiện tại
        
        for word in words:
            if word.startswith("http"):
                # Gửi tác vụ rút gọn link vào thread pool
                task = asyncio.to_thread(shorten_url_sync, word)
                current_line_tasks.append((task, word)) # (Task, link_gốc)
            else:
                current_line_tasks.append((None, f"<b>{word}</b>")) # (None, từ_thường)
                
        # Thêm các tác vụ vào danh sách chung và thay thế bằng placeholders tạm thời
        for i, (task, value) in enumerate(current_line_tasks):
            if task:
                shortening_tasks.append(task)
                words[words.index(value)] = f"__LINK_PLACEHOLDER_{len(shortening_tasks) - 1}__" 
            else:
                 words[words.index(value)] = value # Giữ nguyên từ thường đã format
                 
        # Sau khi thay thế, nối lại dòng với placeholders
        new_lines.append(" ".join(words)) 

    # Chạy tất cả các tác vụ rút gọn link bất đồng bộ
    shortened_results = await asyncio.gather(*shortening_tasks, return_exceptions=True)

    # Thay thế placeholders bằng kết quả thực tế
    final_lines = []
    
    for line in new_lines:
        temp_line = line
        for i, result in enumerate(shortened_results):
            if isinstance(result, Exception):
                short_link = "Error" # Xử lý lỗi
            else:
                short_link = result
            
            # Thay thế placeholder bằng link rút gọn (hoặc link gốc nếu rút gọn lỗi)
            temp_line = temp_line.replace(f"__LINK_PLACEHOLDER_{i}__", f"<s>{short_link}</s>")
        final_lines.append(temp_line)


    final_lines.append(
        '\n<b>Báo lỗi + đóng góp video:</b> @nothinginthissss\n'
        '<b>Thông báo:</b> @sachkhongchuu\n'
        '<b>Hướng dẫn vượt link:</b> @HuongDanVuotLink_SachKhongChu\n\n'
        '⚠️<b>Kênh xem không cần vượt:</b> '
        '<a href="https://t.me/sachkhongchuu/299">Ấn vào đây</a>'
    )

    return "\n".join(final_lines)

# ====== Xử lý nhóm ảnh/video ======
async def process_media_group(media_group_id: str, user_chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    # Giảm thời gian chờ xuống 1-2 giây để tăng tốc độ phản hồi
    await asyncio.sleep(random.uniform(1.0, 2.0)) 
    messages = media_groups.pop(media_group_id, [])
    if not messages:
        return

    messages.sort(key=lambda m: m.message_id)
    media = []
    caption = None

    for i, message in enumerate(messages):
        # Lấy caption từ tin nhắn đầu tiên
        if i == 0 and message.caption:
            caption = await format_text(message.caption)

        if message.photo:
            file_id = message.photo[-1].file_id
            # Chỉ gán caption cho item đầu tiên trong media group
            media_item = InputMediaPhoto(file_id, caption=caption if i == 0 else None, parse_mode=ParseMode.HTML)
            media.append(media_item)
        elif message.video:
            file_id = message.video.file_id
            media_item = InputMediaVideo(file_id, caption=caption if i == 0 else None, parse_mode=ParseMode.HTML)
            media.append(media_item)

    if media:
        await context.bot.send_media_group(chat_id=user_chat_id, media=media)

# ====== Lệnh /api ======
async def api_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not await check_channel_membership(update, context):
        return

    user_id = update.message.from_user.id
    args = context.args
    if args and args[0].lower() == "on":
        user_api_enabled[user_id] = True
        await update.message.reply_text("✅ Tính năng API đã bật! Gửi tin nhắn để bot rút gọn link và phản hồi.")
    elif args and args[0].lower() == "off":
        user_api_enabled[user_id] = False
        await update.message.reply_text("❌ Tính năng API đã tắt.")
    else:
        status = "bật" if user_api_enabled.get(user_id, False) else "tắt"
        await update.message.reply_text(f"📋 Trạng thái API: **{status}**\nNhắn `/api on` để bật, `/api off` để tắt.", parse_mode="Markdown")


# 🆕 HÀM LỌC TÙY CHỈNH: Chỉ trả về True nếu API BẬT VÀ KHÔNG TRONG CHẾ ĐỘ TẠO LINK
def is_api_mode_on(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.effective_user:
        return False
    user_id = update.effective_user.id
    
    # 💡 Cơ chế Ưu tiên: Nếu đang tạo link (Feature 1), KHÔNG chạy Feature 2
    with data_lock:
        if user_id in user_files:
            return False 
            
    # Kiểm tra trạng thái API
    return user_api_enabled.get(user_id, False)


# ====== Xử lý tin nhắn ======
async def handle_api_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # LƯU Ý: Bộ lọc is_api_mode_on đã đảm bảo tính năng được bật
    
    if not update.message or not await check_channel_membership(update, context):
        return

    # Khác với feature 1, feature 2 chỉ hoạt động trong chat Private
    chat_type = update.message.chat.type
    if chat_type != "private":
        return

    msg = update.message
    text = msg.text or msg.caption or ""

    # === Xử lý nhóm media (album) ===
    if msg.media_group_id:
        mgid = msg.media_group_id
        if mgid not in media_groups:
            media_groups[mgid] = []
            # Chạy tác vụ xử lý album sau khi chờ
            asyncio.create_task(process_media_group(mgid, msg.chat_id, context)) 
        media_groups[mgid].append(msg)
        return

    # === Ảnh hoặc video có caption ===
    if msg.caption and ("http" in msg.caption):
        caption = await format_text(msg.caption)
        if msg.photo:
            await msg.reply_photo(msg.photo[-1].file_id, caption=caption, parse_mode=ParseMode.HTML)
        elif msg.video:
            await msg.reply_video(msg.video.file_id, caption=caption, parse_mode=ParseMode.HTML)
        return

    # === Tin nhắn text có link ===
    if msg.text and "http" in msg.text:
        caption = await format_text(msg.text)
        await msg.reply_text(caption, parse_mode=ParseMode.HTML)
        return

    # === Tin nhắn forward ===
    if msg.forward_from or msg.forward_from_chat:
        # Nếu là forward, ta chỉ format caption/text nếu có link, nếu không copy nguyên bản
        formatted_caption = await format_text(msg.caption or msg.text or "")
        
        # Nếu không có link nào được format (chỉ có các thẻ <b> và phần footer) 
        # thì ta chỉ gửi phần footer, hoặc gửi thông báo.
        if formatted_caption != (msg.caption or msg.text or ""):
             await msg.copy(chat_id=msg.chat_id, caption=formatted_caption, parse_mode=ParseMode.HTML)
        else:
            await msg.reply_text("📩 Bot đã nhận được tin nhắn forward của bạn (Không có link để xử lý).")
        return

    # === Tin nhắn bình thường ===
    await msg.reply_text("📩 Bot đã nhận được tin nhắn của bạn.")

# ====== Đăng ký vào app chính ======
def register_feature2(app):
    app.add_handler(CommandHandler("api", api_command))
    
    # 💥 Đăng ký Handler chỉ khi is_api_mode_on là True
    api_message_filter = (filters.TEXT | filters.PHOTO | filters.VIDEO | filters.FORWARDED) & ~filters.COMMAND
    
    app.add_handler(MessageHandler(
        api_message_filter & is_api_mode_on,
        handle_api_message
    ))
