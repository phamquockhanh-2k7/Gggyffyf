import asyncio
import requests
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
from telegram.ext import ContextTypes, CallbackQueryHandler

# Đường dẫn Firebase
FIREBASE_URL = "https://bot-telegram-99852-default-rtdb.firebaseio.com"

# ==============================================================================
# ⚙️ CẤU HÌNH NHIỆM VỤ HÀNG NGÀY
# ==============================================================================
# Link kênh bạn muốn họ tham gia
LINK_NHIEM_VU = "https://t.me/LINK_KENH_CUA_BAN" 

# Biến tạm lưu trạng thái đã bấm nút 1 chưa (Lưu trên RAM)
temp_click_tracker = {}

# ==============================================================================
# 1. CÁC HÀM XỬ LÝ FIREBASE (DATA)
# ==============================================================================

async def get_credits(user_id):
    """Lấy số lượt tải hiện có"""
    url = f"{FIREBASE_URL}/ref/{user_id}.json"
    res = await asyncio.to_thread(requests.get, url)
    return res.json() if (res.status_code == 200 and res.json() is not None) else None

async def init_user_if_new(user_id):
    """Tặng 1 lượt cho người mới"""
    current = await get_credits(user_id)
    if current is None:
        url = f"{FIREBASE_URL}/ref/{user_id}.json"
        await asyncio.to_thread(requests.put, url, json=1)
        return 1
    return current

async def add_credit(user_id, amount=1):
    """Cộng lượt tải"""
    current = await get_credits(user_id) or 0
    url = f"{FIREBASE_URL}/ref/{user_id}.json"
    await asyncio.to_thread(requests.put, url, json=current + amount)

async def deduct_credit(user_id):
    """Trừ 1 lượt tải"""
    current = await get_credits(user_id) or 0
    if current > 0:
        url = f"{FIREBASE_URL}/ref/{user_id}.json"
        await asyncio.to_thread(requests.put, url, json=current - 1)
        return True
    return False

async def check_daily_task_status(user_id):
    """Kiểm tra xem hôm nay đã nhận thưởng chưa (True/False)"""
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    url = f"{FIREBASE_URL}/daily_check/{user_id}.json"
    res = await asyncio.to_thread(requests.get, url)
    return res.json() == today_str

async def mark_daily_task_done(user_id):
    """Đánh dấu hôm nay đã nhận"""
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    url = f"{FIREBASE_URL}/daily_check/{user_id}.json"
    await asyncio.to_thread(requests.put, url, json=today_str)

# ==============================================================================
# 2. HỆ THỐNG XỬ LÝ NHIỆM VỤ (TASK)
# ==============================================================================

async def open_task_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mở menu nhiệm vụ khi bấm nút 'Nhận 1 lượt mỗi ngày'"""
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    # Kiểm tra hôm nay làm chưa
    if await check_daily_task_status(user_id):
        await context.bot.send_message(
            chat_id=user_id,
            text="⚠️ <b>HẾT LƯỢT HÔM NAY!</b>\n\nBạn đã nhận thưởng nhiệm vụ ngày hôm nay rồi. Vui lòng quay lại vào ngày mai.",
            parse_mode="HTML"
        )
        return

    # Nếu chưa làm -> Hiện bảng nhiệm vụ hack tâm lý
    msg = (
        "<b>🎁 NHIỆM VỤ HÀNG NGÀY</b>\n\n"
        "Tham gia kênh tài trợ dưới đây để nhận ngay <b>1 lượt lưu video</b> miễn phí.\n\n"
        "👇 <b>Làm theo 2 bước sau:</b>"
    )
    keyboard = [
        [InlineKeyboardButton("👉 Bước 1: Lấy Link Kênh", callback_data="task_get_link")],
        [InlineKeyboardButton("✅ Bước 2: Xác nhận đã vào", callback_data="task_confirm")]
    ]
    
    # Gửi tin nhắn mới (không edit tin cũ để giữ video)
    await context.bot.send_message(chat_id=user_id, text=msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def handle_task_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý Bước 1 và Bước 2"""
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    
    await query.answer()

    # --- BƯỚC 1: LẤY LINK ---
    if data == "task_get_link":
        temp_click_tracker[user_id] = True # Đánh dấu RAM
        
        msg = (
            f"🔗 <b>LINK THAM GIA:</b>\n👉 {LINK_NHIEM_VU}\n\n"
            "⚠️ <b>Lưu ý:</b> Hãy bấm tham gia kênh, sau đó quay lại đây bấm <b>'Bước 2: Xác nhận'</b>."
        )
        keyboard = [[InlineKeyboardButton("✅ Bước 2: Xác nhận đã vào", callback_data="task_confirm")]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    # --- BƯỚC 2: XÁC NHẬN ---
    elif data == "task_confirm":
        # Check RAM (Có bấm Bước 1 chưa?)
        if not temp_click_tracker.get(user_id):
            await context.bot.send_message(chat_id=user_id, text="❌ <b>Lỗi:</b> Bạn chưa lấy link! Hãy bấm <b>'Bước 1'</b> trước.", parse_mode="HTML")
            
            # Gửi lại bảng menu gốc cho họ làm lại
            keyboard = [
                [InlineKeyboardButton("👉 Bước 1: Lấy Link Kênh", callback_data="task_get_link")],
                [InlineKeyboardButton("✅ Bước 2: Xác nhận đã vào", callback_data="task_confirm")]
            ]
            await context.bot.send_message(chat_id=user_id, text="👇 <b>Làm lại:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            return

        # Check DB (Hôm nay nhận chưa?)
        if await check_daily_task_status(user_id):
            await query.edit_message_text("⚠️ Bạn đã nhận thưởng hôm nay rồi!")
            return

        # THÀNH CÔNG
        await add_credit(user_id, 1)
        await mark_daily_task_done(user_id)
        temp_click_tracker.pop(user_id, None) # Xóa RAM

        await query.edit_message_text(
            "🎉 <b>CHÚC MỪNG!</b>\n\n"
            "✅ Đã cộng thêm <b>1 lượt lưu</b>.\n"
            "Hãy bấm lại nút <b>Tải Video</b> lúc nãy để sử dụng.",
            parse_mode="HTML"
        )

# ==============================================================================
# 3. LOGIC TẢI VIDEO & HIỂN THỊ 3 NÚT
# ==============================================================================

async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý khi nhấn nút Tải video"""
    query = update.callback_query
    user_id = query.from_user.id
    alias = query.data.split("_")[1]
    
    try:
        credits = await get_credits(user_id)
        if credits is None: credits = 1
        
        # Nếu hết lượt
        if credits <= 0:
            await query.answer(text="❌ Hết lượt tải miễn phí!", show_alert=True)
            
            # Link Ref để chia sẻ
            ref_link = f"https://t.me/{context.bot.username}?start=ref_{user_id}"
            share_text = "--🔥FreeVideo18+--"
            
            msg = (
                "<b>⛔️ BẠN ĐÃ HẾT LƯỢT LƯU!</b>\n\n"
                "Bạn có 2 cách để kiếm thêm lượt:\n"
                "1️⃣ Chia sẻ link giới thiệu cho bạn bè.\n"
                "2️⃣ Làm nhiệm vụ hàng ngày (Nhận 1 lượt/ngày)."
            )
            
            # Menu khi hết lượt (Cũng hiện 2 lựa chọn)
            keyboard = [
                [InlineKeyboardButton("🔗 Chia sẻ nhận lượt", url=f"https://t.me/share/url?url={ref_link}&text={share_text}")],
                [InlineKeyboardButton("🎁 Nhận 1 lượt mỗi ngày", callback_data="task_open")]
            ]
            
            await context.bot.send_message(chat_id=query.message.chat_id, text=msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            return

        # Nếu còn lượt -> Gửi Video
        await query.answer(text="✅ Đang gửi video...")

        shared_url = f"{FIREBASE_URL}/shared/{alias}.json"
        res = await asyncio.to_thread(requests.get, shared_url)
        data = res.json()

        if res.status_code == 200 and data:
            if await deduct_credit(user_id):
                new_credits = credits - 1
                
                # ... (Đoạn code gửi file/media giữ nguyên như cũ) ...
                media_group, text_content, docs_to_send = [], [], []
                for item in data:
                    f_id, f_type = item["file_id"], item["type"]
                    if f_type == "photo": media_group.append(InputMediaPhoto(f_id))
                    elif f_type == "video": media_group.append(InputMediaVideo(f_id))
                    elif f_type == "text": text_content.append(f_id)
                    elif f_type == "document": docs_to_send.append(f_id)

                if text_content: await context.bot.send_message(chat_id=query.message.chat_id, text="\n\n".join(text_content))
                if media_group:
                    for i in range(0, len(media_group), 10):
                        await context.bot.send_media_group(chat_id=query.message.chat_id, media=media_group[i:i+10])
                for doc_id in docs_to_send: await context.bot.send_document(chat_id=query.message.chat_id, document=doc_id)

                # --- ✅ CẬP NHẬT MENU 3 NÚT SAU KHI GỬI XONG ---
                await context.bot.send_message(chat_id=query.message.chat_id, text=f"✅ Đã gửi bản lưu! (Bạn còn {new_credits} lượt)")

                ref_link = f"https://t.me/{context.bot.username}?start=ref_{user_id}"
                share_text = "--🔥FreeVideo18+--"
                
                keyboard = [
                    # Nút 1: Tải tiếp (nếu bấm lại)
                    [InlineKeyboardButton(f"📥 Tải video (còn {new_credits} lượt)", callback_data=f"dl_{alias}")],
                    # Nút 2: Chia sẻ (Cũ)
                    [InlineKeyboardButton("🔗 Chia sẻ nhận thêm lượt", url=f"https://t.me/share/url?url={ref_link}&text={share_text}")],
                    # Nút 3: Nhiệm vụ hàng ngày (MỚI)
                    [InlineKeyboardButton("🎁 Nhận 1 lượt mỗi ngày", callback_data="task_open")]
                ]
                await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await context.bot.send_message(chat_id=query.message.chat_id, text="❌ Data lỗi.")
            
    except Exception as e:
        print(f"Lỗi: {e}")

# ==============================================================================
# CÁC HÀM PHỤ KHÁC (GIỮ NGUYÊN)
# ==============================================================================
async def delete_msg_job(context: ContextTypes.DEFAULT_TYPE):
    try: await context.bot.delete_message(chat_id=context.job.chat_id, message_id=context.job.data)
    except: pass

async def check_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /profile"""
    try: await update.message.delete()
    except: pass
    if not update.message: return
    
    user_id = update.effective_user.id
    credits = await init_user_if_new(user_id)
    ref_link = f"https://t.me/{context.bot.username}?start=ref_{user_id}"
    share_text = "--🔥FreeVideo--"
    
    message_text = (
        f"👤 **PROFILE**\n🆔: `{user_id}`\n📥 Credit: **{credits}**\n\n"
        f"🔗 **Link Ref:**\n`{ref_link}`"
    )
    keyboard = [[InlineKeyboardButton("🚀 Chia sẻ ngay", url=f"https://t.me/share/url?url={ref_link}&text={share_text}")]]
    await update.message.reply_text(message_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def cheat_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await add_credit(user_id, 20)
    await update.message.reply_text("Admin: +20 Credits.")

# ==============================================================================
# 4. ĐĂNG KÝ HANDLER
# ==============================================================================
def register_feature3(app):
    # Xử lý nút Tải Video
    app.add_handler(CallbackQueryHandler(download_callback, pattern="^dl_"))
    
    # Xử lý nút Mở Menu Nhiệm vụ (Nút 3)
    app.add_handler(CallbackQueryHandler(open_task_menu, pattern="^task_open$"))
    
    # Xử lý Bước 1 & Bước 2 (Lấy Link & Xác nhận)
    app.add_handler(CallbackQueryHandler(handle_task_actions, pattern="^task_(get_link|confirm)$"))
