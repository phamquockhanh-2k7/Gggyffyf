# ==============================================================================
# FEATURE4: BOT NGẦM BẮT USER , CÁC LỆNH /FULLIN4 /SENDTOFULLIN4
# ==============================================================================
import asyncio
import requests
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ChatJoinRequestHandler, CommandHandler, CallbackQueryHandler
from telegram.error import Forbidden, BadRequest, RetryAfter, NetworkError
import config

# ==============================================================================
# CẤU HÌNH
# ==============================================================================
BASE_DB_URL = config.FIREBASE_URL
CHECKPOINT_DB = f"{BASE_DB_URL}/broadcast_checkpoint.json"

# ==============================================================================
# 1. TỰ ĐỘNG THU THẬP ID
# ==============================================================================
async def collect_id_silent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    request = update.chat_join_request
    user = request.from_user
    chat = request.chat
    try:
        user_info = {
            'first_name': user.first_name,
            'username': user.username if user.username else "No Username",
            'joined_date': str(request.date),
            'from_source': chat.title 
        }
        url = f"{BASE_DB_URL}/IDUser/{user.id}.json"
        await asyncio.to_thread(requests.put, url, json=user_info)
    except Exception: pass

# ==============================================================================
# 2. XEM BÁO CÁO
# ==============================================================================
async def check_full_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        url = f"{BASE_DB_URL}/IDUser.json"
        res = await asyncio.to_thread(requests.get, url)
        if res.status_code != 200 or not res.json():
            await update.message.reply_text("📂 Data trống.")
            return
        data = res.json()
        total_count = len(data)
        group_stats = {}
        for uid, info in data.items():
            source = info.get('from_source', 'Không rõ')
            group_stats[source] = group_stats.get(source, 0) + 1
        sorted_stats = sorted(group_stats.items(), key=lambda item: item[1], reverse=True)
        msg = f"📂 <b>BÁO CÁO SOS</b>\n➖➖➖➖\n👥 Tổng ID: <b>{total_count}</b>\n\n📊 <b>NGUỒN:</b>\n"
        for name, count in sorted_stats:
            msg += f"🔥 {name}: <b>{count}</b>\n"
        await update.message.reply_text(msg, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {e}")

# ==============================================================================
# 3. GỬI TIN NHẮN (CÓ CHECKPOINT)
# ==============================================================================

# Biến toàn cục để lưu task đang chạy (tránh bị dọn rác bộ nhớ)
active_tasks = set()

async def save_checkpoint(index, total_sent, total_blocked):
    """Lưu tiến độ vào Firebase"""
    data = {"index": index, "success": total_sent, "blocked": total_blocked}
    await asyncio.to_thread(requests.put, CHECKPOINT_DB, json=data)

async def clear_checkpoint():
    """Xóa checkpoint khi xong"""
    await asyncio.to_thread(requests.delete, CHECKPOINT_DB)

async def background_sender(context, chat_id, message_to_copy, user_ids, start_index=0, init_success=0, init_blocked=0):
    success = init_success
    blocked = init_blocked
    total = len(user_ids)
    
    # Chỉ lấy danh sách từ vị trí start_index trở đi
    target_ids = user_ids[start_index:]
    
    start_time = time.time()
    last_update_time = time.time()
    
    status_msg = await context.bot.send_message(
        chat_id=chat_id, 
        text=f"🚀 <b>Đang chạy...</b>\nTiếp tục từ: {start_index}/{total}",
        parse_mode="HTML"
    )

    for i, user_id in enumerate(target_ids):
        real_index = start_index + i  # Chỉ số thực tế trong danh sách gốc
        
        try:
            try: target_id = int(user_id)
            except: 
                blocked += 1
                continue

            await context.bot.copy_message(
                chat_id=target_id,
                from_chat_id=message_to_copy.chat_id,
                message_id=message_to_copy.message_id
            )
            success += 1
            await asyncio.sleep(0.8) # Delay an toàn

        except RetryAfter as e:
            await asyncio.sleep(e.retry_after + 2)
            try:
                await context.bot.copy_message(chat_id=target_id, from_chat_id=message_to_copy.chat_id, message_id=message_to_copy.message_id)
                success += 1
            except: blocked += 1
        except (Forbidden, BadRequest, NetworkError, Exception):
            blocked += 1
        
        # --- CẬP NHẬT TRẠNG THÁI & LƯU CHECKPOINT (20s/lần) ---
        current_time = time.time()
        if (current_time - last_update_time >= 20) or (real_index + 1) == total:
            # 1. Lưu Checkpoint (Quan trọng nhất)
            await save_checkpoint(real_index + 1, success, blocked)
            
            # 2. Sửa tin nhắn báo cáo
            try:
                percent = int((real_index + 1) / total * 100)
                bar = "█" * (percent // 10) + "░" * (10 - (percent // 10))
                await status_msg.edit_text(
                    f"🚀 <b>ĐANG GỬI... ({percent}%)</b>\n"
                    f"[{bar}]\n"
                    f"➖➖➖➖➖➖\n"
                    f"✅ Thành công: <b>{success}</b>\n"
                    f"🚫 Thất bại: <b>{blocked}</b>\n"
                    f"📍 Vị trí: <b>{real_index + 1}/{total}</b>\n"
                    f"💾 <i>Đã lưu Checkpoint...</i>",
                    parse_mode="HTML"
                )
                last_update_time = current_time
            except: pass

    # Xong hết thì xóa checkpoint
    await clear_checkpoint()
    duration = int(time.time() - start_time)
    await status_msg.edit_text(
        f"✅ <b>HOÀN TẤT TOÀN BỘ!</b>\n⏱ Thời gian chạy đợt này: {duration}s\n✅ Tổng Success: {success}\n🔴 Tổng Fail: {blocked}",
        parse_mode="HTML"
    )

async def send_to_full_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    
    # Check xem có dữ liệu gửi dở không?
    try:
        cp_res = await asyncio.to_thread(requests.get, CHECKPOINT_DB)
        checkpoint = cp_res.json()
    except: checkpoint = None

    # Nếu có checkpoint -> Hỏi ý kiến
    if checkpoint:
        keyboard = [
            [InlineKeyboardButton(f"▶️ Tiếp tục từ {checkpoint['index']}", callback_data="RESUME_BROADCAST")],
            [InlineKeyboardButton("🔄 Chạy mới từ đầu", callback_data="NEW_BROADCAST")]
        ]
        await msg.reply_text(
            f"⚠️ <b>PHÁT HIỆN TIẾN TRÌNH CŨ!</b>\n\n"
            f"Lần trước Bot đã dừng ở người thứ <b>{checkpoint['index']}</b>.\n"
            f"Bạn có muốn chạy tiếp không?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        # Lưu tin nhắn gốc vào user_data để dùng sau
        context.user_data['broadcast_msg'] = msg.reply_to_message
        return

    # Nếu không có checkpoint -> Chạy mới
    if not msg.reply_to_message:
        await msg.reply_text("⚠️ Hãy Reply tin nhắn cần gửi.")
        return
    
    await start_broadcast_process(update, context, msg.reply_to_message, start_from=0)

async def handle_broadcast_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data
    
    if choice == "NEW_BROADCAST":
        # Xóa checkpoint cũ
        await clear_checkpoint()
        if not context.user_data.get('broadcast_msg'):
            await query.edit_message_text("❌ Mất dữ liệu tin nhắn gốc. Vui lòng Reply lại lệnh.")
            return
        await query.delete_message()
        await start_broadcast_process(update, context, context.user_data['broadcast_msg'], start_from=0)
        
    elif choice == "RESUME_BROADCAST":
        try:
            cp_res = await asyncio.to_thread(requests.get, CHECKPOINT_DB)
            cp = cp_res.json()
            if not cp: 
                await query.edit_message_text("❌ Lỗi dữ liệu checkpoint.")
                return
            
            await query.delete_message()
            # Nếu tin nhắn gốc bị mất (do restart bot), báo lỗi
            msg_to_send = context.user_data.get('broadcast_msg')
            if not msg_to_send:
                await context.bot.send_message(chat_id=query.message.chat_id, text="⚠️ Bot đã khởi động lại nên mất tin nhắn gốc. Vui lòng Reply tin nhắn cần gửi và chọn 'Chạy mới' hoặc set up lại.")
                return

            await start_broadcast_process(update, context, msg_to_send, start_from=cp['index'], i_success=cp['success'], i_blocked=cp['blocked'])
        except Exception as e:
            await context.bot.send_message(chat_id=query.message.chat_id, text=f"Lỗi: {e}")

async def start_broadcast_process(update, context, message_to_copy, start_from=0, i_success=0, i_blocked=0):
    url = f"{BASE_DB_URL}/IDUser.json"
    try:
        chat_id = update.effective_chat.id
        init_msg = await context.bot.send_message(chat_id, "⏳ Đang tải danh sách...")
        
        res = await asyncio.to_thread(requests.get, url)
        if res.status_code != 200 or not res.json():
            await init_msg.edit_text("❌ List trống.")
            return
            
        user_ids = list(res.json().keys())
        user_ids.reverse() 
        
        await init_msg.delete()

        # Tạo Task và lưu vào set để không bị GC
        task = asyncio.create_task(
            background_sender(context, chat_id, message_to_copy, user_ids, start_from, i_success, i_blocked)
        )
        active_tasks.add(task)
        task.add_done_callback(active_tasks.discard)

    except Exception as e:
        print(f"Lỗi: {e}")

# ==============================================================================
# 4. ĐĂNG KÝ
# ==============================================================================
def register_feature4(app):
    app.add_handler(ChatJoinRequestHandler(collect_id_silent))
    app.add_handler(CommandHandler("FullIn4", check_full_info))
    app.add_handler(CommandHandler("sendtofullin4", send_to_full_info))
    app.add_handler(CallbackQueryHandler(handle_broadcast_decision, pattern="^(NEW_BROADCAST|RESUME_BROADCAST)$"))
