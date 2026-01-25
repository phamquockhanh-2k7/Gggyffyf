# ==============================================================================
# FEATURE3: LƯU VIDEO + REF 
# ==============================================================================
import asyncio
import requests
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
from telegram.ext import ContextTypes, CallbackQueryHandler
import config

# Đường dẫn Firebase
FIREBASE_URL = config.FIREBASE_URL

# ==============================================================================
# 1. CÁC HÀM XỬ LÝ DATA (FIREBASE)
# ==============================================================================

async def get_credits(user_id):
    url = f"{FIREBASE_URL}/ref/{user_id}.json"
    res = await asyncio.to_thread(requests.get, url)
    return res.json() if (res.status_code == 200 and res.json() is not None) else None

async def init_user_if_new(user_id):
    current = await get_credits(user_id)
    if current is None:
        url = f"{FIREBASE_URL}/ref/{user_id}.json"
        await asyncio.to_thread(requests.put, url, json=1)
        return 1
    return current

async def add_credit(user_id, amount=1):
    current = await get_credits(user_id) or 0
    url = f"{FIREBASE_URL}/ref/{user_id}.json"
    await asyncio.to_thread(requests.put, url, json=current + amount)

async def deduct_credit(user_id):
    current = await get_credits(user_id) or 0
    if current > 0:
        url = f"{FIREBASE_URL}/ref/{user_id}.json"
        await asyncio.to_thread(requests.put, url, json=current - 1)
        return True
    return False

async def check_daily_task_status(user_id):
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    url = f"{FIREBASE_URL}/daily_check/{user_id}.json"
    res = await asyncio.to_thread(requests.get, url)
    return res.json() == today_str

async def mark_daily_task_done(user_id):
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    url = f"{FIREBASE_URL}/daily_check/{user_id}.json"
    await asyncio.to_thread(requests.put, url, json=today_str)

# ==============================================================================
# 2. XỬ LÝ NHIỆM VỤ
# ==============================================================================

async def open_task_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if await check_daily_task_status(user_id):
        await context.bot.send_message(chat_id=user_id, text="⚠️ <b>Bạn đã nhận hôm nay rồi!</b>\nQuay lại vào sáng ngày mai nhé :3.", parse_mode="HTML")
        return

    msg = (
        "<b>🎁 NHẬN 1 LƯỢT LƯU MIỄN PHÍ</b>\n\n"
        "👇 <b>Yêu cầu tham gia kênh dưới đây:</b>\n"
        "1️⃣ Ấn nút 'Lấy Link Tham Gia' bên dưới để lấy link tham gia kênh.\n"
        "2️⃣ Tham gia kênh và quay lại ấn 'Xác nhận'."
    )
    
    keyboard = [
        [InlineKeyboardButton("👉 Bước 1: Lấy Link Tham Gia", callback_data="task_get_link")],
        [InlineKeyboardButton("✅ Bước 2: Xác nhận đã vào", callback_data="task_confirm")]
    ]
    
    await context.bot.send_message(chat_id=user_id, text=msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def handle_task_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    await query.answer()

    if data == "task_get_link":
        context.user_data['temp_task_clicked'] = True
        msg = (
            "🔗 <b>Tham gia kênh dưới đây:</b>\n\n"
            "Hãy ấn vào nút <b>'🚀 Tham gia ngay'</b> bên dưới để vào kênh.\n"
            "Sau đó ấn <b>'Xác nhận'</b> để nhận lượt lưu."
        )
        keyboard = [
            [InlineKeyboardButton("🚀 Tham gia ngay ", url=config.JOIN_LINK_CHANNEL)],
            [InlineKeyboardButton("✅ Bước 2: Xác nhận đã vào", callback_data="task_confirm")]
        ]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data == "task_confirm":
        if not context.user_data.get('temp_task_clicked'):
            await context.bot.send_message(chat_id=user_id, text="❌ <b>Lỗi:</b> Bạn chưa tham gia kênh <b>'Bước 1'</b>!", parse_mode="HTML")
            return

        if await check_daily_task_status(user_id):
            await query.edit_message_text("⚠️ Bạn đã nhận thưởng hôm nay rồi!")
            return

        await add_credit(user_id, 1)
        await mark_daily_task_done(user_id)
        context.user_data['temp_task_clicked'] = False

        await query.edit_message_text(
            "🎉 <b>XÁC NHẬN THÀNH CÔNG!</b>\n\n"
            "✅ Đã cộng thêm <b>1 lượt lưu</b>.\n"
            "👉 Hãy ấn lại nút <b>Tải Video</b> để sử dụng.",
            parse_mode="HTML"
        )

# ==============================================================================
# 3. LOGIC TẢI VIDEO (CHẾ ĐỘ DEBUG SOI LỖI)
# ==============================================================================

async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    # Lấy ID từ nút bấm
    alias = query.data.replace("dl_", "").strip() 
    
    try:
        credits = await get_credits(user_id)
        if credits is None: credits = 1
        
        if credits <= 0:
            await query.answer(text="❌ Hết lượt tải miễn phí!", show_alert=True)
            return

        await query.answer(text="🔍 Đang tìm dữ liệu...")

        # --- DEBUG MODE BẮT ĐẦU ---
        # 1. Thử tìm trong thư mục /shared/
        url_1 = f"{FIREBASE_URL}/shared/{alias}.json"
        res1 = await asyncio.to_thread(requests.get, url_1)
        data = res1.json()
        debug_msg = f"🔍 <b>DEBUG REPORT:</b>\n🆔 ID: <code>{alias}</code>\n"
        debug_msg += f"🔗 URL 1: <code>.../shared/{alias}.json</code> -> {'✅ CÓ' if data else '❌ KHÔNG'}\n"

        # 2. Nếu không thấy, tìm ở thư mục gốc
        if not data:
            url_2 = f"{FIREBASE_URL}/{alias}.json"
            res2 = await asyncio.to_thread(requests.get, url_2)
            data = res2.json()
            debug_msg += f"🔗 URL 2: <code>.../{alias}.json</code> -> {'✅ CÓ' if data else '❌ KHÔNG'}\n"

        # 3. XỬ LÝ KẾT QUẢ
        if data:
            # Nếu tìm thấy -> Gửi bình thường
            if await deduct_credit(user_id):
                new_credits = credits - 1
                
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

                await context.bot.send_message(chat_id=query.message.chat_id, text=f"✅ Đã gửi bản lưu! (Còn {new_credits} lượt)")

                ref_link = f"https://t.me/{context.bot.username}?start=ref_{user_id}"
                share_text = "--VideoHot--"
                
                keyboard = [
                    [InlineKeyboardButton(f"📥 Tải video (còn {new_credits} lượt)", callback_data=f"dl_{alias}")],
                    [InlineKeyboardButton("🔗 Chia sẻ nhận lượt", url=f"https://t.me/share/url?url={ref_link}&text={share_text}")],
                    [InlineKeyboardButton("🎁 Nhận 1 lượt mỗi ngày", callback_data="task_open")]
                ]
                await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            # 🔥 NẾU LỖI -> GỬI BÁO CÁO DEBUG CHO NGƯỜI DÙNG
            debug_msg += f"\n❌ <b>KẾT LUẬN:</b> Không tìm thấy dữ liệu đâu cả."
            await context.bot.send_message(chat_id=query.message.chat_id, text=debug_msg, parse_mode="HTML")
            
    except Exception as e:
        await context.bot.send_message(chat_id=query.message.chat_id, text=f"❌ Lỗi Code: {e}")

async def delete_msg_job(context: ContextTypes.DEFAULT_TYPE):
    try: await context.bot.delete_message(chat_id=context.job.chat_id, message_id=context.job.data)
    except: pass

async def check_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try: await update.message.delete()
    except: pass
    if not update.message: return
    user_id = update.effective_user.id
    credits = await init_user_if_new(user_id)
    ref_link = f"https://t.me/{context.bot.username}?start=ref_{user_id}"
    share_text = "--Video--"
    
    message_text = (f"👤 **PROFILE**\n🆔: `{user_id}`\n📥 Credit: **{credits}**\n🔗 `{ref_link}`")
    keyboard = [[InlineKeyboardButton("🚀 Chia sẻ ngay", url=f"https://t.me/share/url?url={ref_link}&text={share_text}")]]
    await update.message.reply_text(message_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def cheat_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await add_credit(user_id, 20)
    await update.message.reply_text("Admin: +20 Credits.")

def register_feature3(app):
    app.add_handler(CallbackQueryHandler(download_callback, pattern="^dl_"))
    app.add_handler(CallbackQueryHandler(open_task_menu, pattern="^task_open$"))
    app.add_handler(CallbackQueryHandler(handle_task_actions, pattern="^task_(get_link|confirm)$"))
