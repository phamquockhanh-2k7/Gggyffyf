# ==============================================================================
# FEATURE 4: BROADCAST BẤT TỬ (ANTI-CRASH & ANTI-FLOOD)
# ==============================================================================
import asyncio
import requests
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ChatJoinRequestHandler, CommandHandler, CallbackQueryHandler
from telegram.error import Forbidden, BadRequest, RetryAfter, NetworkError
import config

# ==============================================================================
# ⚙️ CẤU HÌNH CHIẾN DỊCH
# ==============================================================================
BASE_DB_URL = config.FIREBASE_URL
CHECKPOINT_DB = f"{BASE_DB_URL}/broadcast_checkpoint.json"

BATCH_LIMIT = 800     # Gửi xong 800 người thì nghỉ dài
REST_TIME = 120       # Nghỉ 2 phút
SAVE_STEP = 50        # Lưu checkpoint mỗi 50 người
DELAY_MSG = 1.2       # Tăng delay lên 1.2s để giảm nguy cơ dính Flood

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
        # Thêm verify=False để tránh lỗi SSL ở một số server (tùy chọn)
        await asyncio.to_thread(requests.put, url, json=user_info, timeout=5)
    except Exception: pass

# ==============================================================================
# 2. XEM BÁO CÁO
# ==============================================================================
async def check_full_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        url = f"{BASE_DB_URL}/IDUser.json"
        res = await asyncio.to_thread(requests.get, url, timeout=10)
        
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
        await update.message.reply_text(f"❌ Lỗi kết nối: {e}")

# ==============================================================================
# 3. CORE GỬI TIN NHẮN (ĐÃ FIX LỖI SSL CRASH)
# ==============================================================================

active_tasks = set()

# 🔥 HÀM NÀY ĐÃ ĐƯỢC BỌC GIÁP (TRY-EXCEPT ALL)
async def save_checkpoint(index, total_sent, total_blocked):
    """Lưu tiến độ vào Firebase (Không bao giờ crash bot)"""
    data = {"index": index, "success": total_sent, "blocked": total_blocked}
    try:
        # Timeout 10s. Nếu lỗi SSL/Mạng -> Bỏ qua luôn
        await asyncio.to_thread(requests.put, CHECKPOINT_DB, json=data, timeout=10)
    except Exception as e:
        # Chỉ in lỗi ra log để biết, KHÔNG ĐƯỢC để lỗi này làm dừng vòng lặp
        print(f"⚠️ LỖI LƯU CHECKPOINT (Bot vẫn chạy tiếp): {e}")

async def clear_checkpoint():
    try:
        await asyncio.to_thread(requests.delete, CHECKPOINT_DB, timeout=10)
    except: pass

async def background_sender(context, chat_id, message_to_copy, user_ids, start_index=0, init_success=0, init_blocked=0):
    success = init_success
    blocked = init_blocked
    
    target_ids = user_ids[start_index:]
    total_remaining = len(target_ids)
    
    start_time = time.time()
    last_update_time = time.time()
    
    status_msg = await context.bot.send_message(
        chat_id=chat_id, 
        text=f"🚀 <b>BẮT ĐẦU CHIẾN DỊCH!</b>\nTiếp tục từ STT: {start_index}\nTổng còn lại: {total_remaining}",
        parse_mode="HTML"
    )

    for i, user_id in enumerate(target_ids):
        
        # 1. KIỂM TRA MỐC NGHỈ (Batching)
        if i > 0 and i % BATCH_LIMIT == 0:
            try:
                await status_msg.edit_text(
                    f"☕ <b>ĐÃ ĐẠT MỐC {i}!</b>\n😴 Nghỉ {REST_TIME}s hồi sức...\n✅ OK: {success} | 🚫 Fail: {blocked}",
                    parse_mode="HTML"
                )
                print(f"💤 Ngủ {REST_TIME}s...")
                await asyncio.sleep(REST_TIME)
                await status_msg.edit_text(f"▶️ <b>Tiếp tục chạy...</b>", parse_mode="HTML")
            except: pass

        # 2. GỬI TIN NHẮN
        real_current_index = start_index + i + 1 
        
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
            await asyncio.sleep(DELAY_MSG) 

        except RetryAfter as e:
            # Xử lý lỗi Flood control (đòn 1)
            wait_t = e.retry_after + 5
            print(f"⚠️ Flood Wait: Nghỉ {wait_t}s")
            await asyncio.sleep(wait_t)
            try: # Thử lại 1 lần
                await context.bot.copy_message(chat_id=target_id, from_chat_id=message_to_copy.chat_id, message_id=message_to_copy.message_id)
                success += 1
            except: blocked += 1
        except (Forbidden, BadRequest, NetworkError):
            blocked += 1
        except Exception as e:
            print(f"Lỗi lạ: {e}")
            blocked += 1

        # 3. CẬP NHẬT TRẠNG THÁI & LƯU CHECKPOINT
        if i % SAVE_STEP == 0 or (i + 1) == total_remaining:
            
            # 🔥 GỌI HÀM ĐÃ BỌC GIÁP
            await save_checkpoint(real_current_index, success, blocked)
            
            current_time = time.time()
            if current_time - last_update_time > 15: # Giãn thời gian update UI ra 15s
                try:
                    percent = int(real_current_index / (start_index + total_remaining) * 100)
                    await status_msg.edit_text(
                        f"🚀 <b>ĐANG GỬI... ({percent}%)</b>\n"
                        f"📍 Vị trí: <b>{real_current_index}</b>\n"
                        f"✅ OK: <b>{success}</b> | 🚫 Fail: <b>{blocked}</b>",
                        parse_mode="HTML"
                    )
                    last_update_time = current_time
                except: pass

    # --- KẾT THÚC ---
    await clear_checkpoint()
    duration = int(time.time() - start_time)
    await status_msg.edit_text(
        f"✅ <b>XONG!</b>\n⏱ {duration}s\n✅ {success} | 🔴 {blocked}",
        parse_mode="HTML"
    )

# ==============================================================================
# 4. LOGIC KHỞI ĐỘNG
# ==============================================================================

async def send_to_full_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    
    try:
        # Bọc lỗi kết nối khi lấy checkpoint
        cp_res = await asyncio.to_thread(requests.get, CHECKPOINT_DB, timeout=5)
        checkpoint = cp_res.json()
    except: checkpoint = None

    if checkpoint:
        keyboard = [
            [InlineKeyboardButton(f"▶️ Tiếp tục từ {checkpoint['index']}", callback_data="RESUME_BROADCAST")],
            [InlineKeyboardButton("🔄 Chạy mới", callback_data="NEW_BROADCAST")]
        ]
        await msg.reply_text(
            f"⚠️ <b>PHÁT HIỆN TIẾN TRÌNH CŨ!</b>\nDừng ở: <b>{checkpoint['index']}</b>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        context.user_data['broadcast_msg'] = msg.reply_to_message
        return

    if not msg.reply_to_message:
        await msg.reply_text("⚠️ Hãy Reply tin nhắn cần gửi.")
        return
    
    await start_broadcast_process(update, context, msg.reply_to_message, start_from=0)

async def handle_broadcast_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data
    
    if choice == "NEW_BROADCAST":
        await clear_checkpoint()
        if not context.user_data.get('broadcast_msg'):
            await query.edit_message_text("❌ Mất tin nhắn gốc. Reply lại.")
            return
        await query.delete_message()
        await start_broadcast_process(update, context, context.user_data['broadcast_msg'], start_from=0)
        
    elif choice == "RESUME_BROADCAST":
        try:
            cp_res = await asyncio.to_thread(requests.get, CHECKPOINT_DB, timeout=5)
            cp = cp_res.json()
            if not cp: 
                await query.edit_message_text("❌ Lỗi data.")
                return
            await query.delete_message()
            
            msg_to_send = context.user_data.get('broadcast_msg')
            if not msg_to_send:
                await context.bot.send_message(chat_id=query.message.chat_id, text="⚠️ Mất tin nhắn gốc. Hãy chạy mới.")
                return

            await start_broadcast_process(update, context, msg_to_send, start_from=cp['index'], i_success=cp['success'], i_blocked=cp['blocked'])
        except Exception as e:
            await context.bot.send_message(chat_id=query.message.chat_id, text=f"Lỗi: {e}")

async def start_broadcast_process(update, context, message_to_copy, start_from=0, i_success=0, i_blocked=0):
    url = f"{BASE_DB_URL}/IDUser.json"
    try:
        chat_id = update.effective_chat.id
        init_msg = await context.bot.send_message(chat_id, "⏳ Đang tải list...")
        
        res = await asyncio.to_thread(requests.get, url, timeout=20)
        if res.status_code != 200 or not res.json():
            await init_msg.edit_text("❌ List trống.")
            return
            
        user_ids = list(res.json().keys())
        user_ids.reverse()
        
        await init_msg.delete()

        task = asyncio.create_task(
            background_sender(context, chat_id, message_to_copy, user_ids, start_from, i_success, i_blocked)
        )
        active_tasks.add(task)
        task.add_done_callback(active_tasks.discard)

    except Exception as e:
        print(f"Lỗi khởi động: {e}")

# ==============================================================================
# 5. ĐĂNG KÝ (Nhớ check tên file main)
# ==============================================================================
def register_feature5(app):
    app.add_handler(ChatJoinRequestHandler(collect_id_silent))
    app.add_handler(CommandHandler("FullIn4", check_full_info))
    app.add_handler(CommandHandler("sendtofullin44", send_to_full_info))
    app.add_handler(CallbackQueryHandler(handle_broadcast_decision, pattern="^(NEW_BROADCAST|RESUME_BROADCAST)$"))
