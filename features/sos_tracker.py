# ==============================================================================
# FEATURE: SOS TRACKER & IMMORTAL BROADCAST (MASS DM)
# ==============================================================================
import asyncio
import requests
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ChatJoinRequestHandler, CommandHandler, CallbackQueryHandler
from telegram.error import Forbidden, BadRequest, RetryAfter, NetworkError
import config
import db

BATCH_LIMIT = 800     # Gửi xong 800 người thì nghỉ (Vượt qua mốc 900 an toàn)
REST_TIME = 120       # Thời gian nghỉ giải lao (120 giây = 2 phút)
SAVE_STEP = 50        # Cứ xong 50 người là lưu Checkpoint 1 lần
DELAY_MSG = 1.2       # Tốc độ gửi (1.2 giây/tin) - Chậm mà chắc

# Biến toàn cục để giữ task chạy ngầm không bị Garbage Collector dọn mất
active_tasks = set()

# ==============================================================================
# 1. TỰ ĐỘNG THU THẬP ID (KHI USER JOIN)
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
        await db.add_user(user.id, user_info)
    except Exception: pass

# ==============================================================================
# 2. XEM BÁO CÁO DATA (Lệnh /FullIn4)
# ==============================================================================
async def check_full_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        data = await db.get_all_users()
        if not data:
            await update.message.reply_text("📂 Data trống.")
            return
            
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
# 3. HỆ THỐNG GỬI TIN BẤT TỬ (CORE LOGIC)
# ==============================================================================

async def save_checkpoint(index, total_sent, total_blocked):
    """Lưu tiến độ vào Supabase"""
    data = {"index": index, "success": total_sent, "blocked": total_blocked}
    try:
        await db.set_storage_code("broadcast_checkpoint", data)
    except Exception as e:
        print(f"⚠️ Lỗi lưu Checkpoint (Bot vẫn chạy tiếp): {e}")

async def clear_checkpoint():
    """Xóa checkpoint khi xong"""
    try:
        await db._delete("storage_codes", "code=eq.broadcast_checkpoint")
    except: pass

async def background_sender(context, chat_id, message_to_copy, user_ids, start_index=0, init_success=0, init_blocked=0):
    success = init_success
    blocked = init_blocked
    
    # Cắt danh sách: Chỉ lấy từ người thứ start_index trở đi
    target_ids = user_ids[start_index:]
    total_remaining = len(target_ids)
    
    start_time = time.time()
    last_update_time = time.time()
    
    # Gửi tin nhắn khởi động
    status_msg = await context.bot.send_message(
        chat_id=chat_id, 
        text=f"🚀 <b>BẮT ĐẦU CHIẾN DỊCH!</b>\nTiếp tục từ STT: {start_index}\nTổng còn lại: {total_remaining}",
        parse_mode="HTML"
    )

    # --- VÒNG LẶP CHÍNH ---
    for i, user_id in enumerate(target_ids):
        
        # 1. KIỂM TRA MỐC NGHỈ (Batching)
        if i > 0 and i % BATCH_LIMIT == 0:
            try:
                await status_msg.edit_text(
                    f"☕ <b>ĐÃ ĐẠT MỐC {i}!</b>\n😴 Đang nghỉ {REST_TIME} giây để hồi sức...\n✅ Success: {success} | 🚫 Blocked: {blocked}",
                    parse_mode="HTML"
                )
                print(f"💤 Đạt mốc {i}, ngủ {REST_TIME}s...")
                await asyncio.sleep(REST_TIME) # Ngủ theo cấu hình (2 phút)
                
                await status_msg.edit_text(f"▶️ <b>Hết giờ nghỉ! Đang chạy tiếp...</b>", parse_mode="HTML")
            except: pass

        # 2. GỬI TIN NHẮN
        real_current_index = start_index + i + 1 # Vị trí thực tế trong toàn bộ Data
        
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
            await asyncio.sleep(DELAY_MSG) # Delay từng tin

        except RetryAfter as e:
            # Nếu bị Telegram chặn Flood, nghỉ thêm 5s rồi thử lại
            print(f"⚠️ Flood Wait: {e.retry_after}s")
            await asyncio.sleep(e.retry_after + 5)
            try:
                await context.bot.copy_message(chat_id=target_id, from_chat_id=message_to_copy.chat_id, message_id=message_to_copy.message_id)
                success += 1
            except: blocked += 1
        except (Forbidden, BadRequest, NetworkError):
            blocked += 1 # Chặn bot thì bỏ qua, KHÔNG XÓA DATA
        except Exception:
            blocked += 1

        # 3. CẬP TRẠNG THÁI & LƯU CHECKPOINT
        if i % SAVE_STEP == 0 or (i + 1) == total_remaining:
            
            # Lưu Checkpoint (Quan trọng)
            await save_checkpoint(real_current_index, success, blocked)
            
            # Cập nhật báo cáo (Mỗi 15s một lần để đỡ spam API)
            current_time = time.time()
            if current_time - last_update_time > 15: 
                try:
                    percent = int(real_current_index / (start_index + total_remaining) * 100)
                    await status_msg.edit_text(
                        f"🚀 <b>ĐANG GỬI... ({percent}%)</b>\n"
                        f"📍 Vị trí: <b>{real_current_index}</b>\n"
                        f"✅ Thành công: <b>{success}</b>\n"
                        f"🚫 Thất bại: <b>{blocked}</b>\n"
                        f"🔜 Mốc nghỉ tiếp theo: {((i // BATCH_LIMIT) + 1) * BATCH_LIMIT}",
                        parse_mode="HTML"
                    )
                    last_update_time = current_time
                except: pass

    # --- KẾT THÚC ---
    await clear_checkpoint()
    duration = int(time.time() - start_time)
    await status_msg.edit_text(
        f"✅ <b>HOÀN TẤT CHIẾN DỊCH!</b>\n"
        f"⏱ Thời gian: {duration}s\n"
        f"✅ Tổng gửi: {success}\n"
        f"🔴 Tổng lỗi: {blocked}",
        parse_mode="HTML"
    )

# ==============================================================================
# 4. XỬ LÝ LỆNH & LOGIC KHỞI ĐỘNG (sendtofullin4)
# ==============================================================================

async def send_to_full_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    
    # Check Checkpoint
    try:
        checkpoint = await db.get_storage_code("broadcast_checkpoint")
    except: checkpoint = None

    # Có checkpoint -> Hỏi ý kiến
    if checkpoint:
        keyboard = [
            [InlineKeyboardButton(f"▶️ Tiếp tục từ {checkpoint['index']}", callback_data="RESUME_BROADCAST")],
            [InlineKeyboardButton("🔄 Chạy mới từ đầu", callback_data="NEW_BROADCAST")]
        ]
        await msg.reply_text(
            f"⚠️ <b>PHÁT HIỆN TIẾN TRÌNH CŨ!</b>\n\n"
            f"Lần trước dừng ở người thứ <b>{checkpoint['index']}</b>.\n"
            f"Bạn muốn làm gì?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        context.user_data['broadcast_msg'] = msg.reply_to_message
        return

    # Không có -> Chạy mới
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
            await query.edit_message_text("❌ Mất dữ liệu gốc. Hãy Reply lại lệnh.")
            return
        await query.delete_message()
        await start_broadcast_process(update, context, context.user_data['broadcast_msg'], start_from=0)
        
    elif choice == "RESUME_BROADCAST":
        try:
            cp = await db.get_storage_code("broadcast_checkpoint")
            if not cp:
                await query.edit_message_text("❌ Lỗi dữ liệu checkpoint.")
                return
            
            await query.delete_message()
            
            msg_to_send = context.user_data.get('broadcast_msg')
            if not msg_to_send:
                await context.bot.send_message(chat_id=query.message.chat_id, text="⚠️ Bot restart nên mất tin gốc. Vui lòng Reply tin nhắn và chọn 'Chạy mới'.")
                return

            await start_broadcast_process(update, context, msg_to_send, start_from=cp['index'], i_success=cp['success'], i_blocked=cp['blocked'])
        except Exception as e:
            await context.bot.send_message(chat_id=query.message.chat_id, text=f"Lỗi: {e}")

async def start_broadcast_process(update, context, message_to_copy, start_from=0, i_success=0, i_blocked=0):
    try:
        chat_id = update.effective_chat.id
        init_msg = await context.bot.send_message(chat_id, "⏳ Đang tải danh sách ID...")
        
        data = await db.get_all_users()
        if not data:
            await init_msg.edit_text("❌ List trống.")
            return
            
        user_ids = list(data.keys())
        user_ids.reverse() # Gửi người mới trước
        
        await init_msg.delete()

        # Tạo Task chạy ngầm
        task = asyncio.create_task(
            background_sender(context, chat_id, message_to_copy, user_ids, start_from, i_success, i_blocked)
        )
        active_tasks.add(task)
        task.add_done_callback(active_tasks.discard)

    except Exception as e:
        print(f"Lỗi khởi động: {e}")

# ==============================================================================
# 4.5. LỆNH BẮN TỈA: GỬI TIN CHO 1 NGƯỜI CỤ THỂ (/sendto)
# ==============================================================================
async def command_sendto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    
    # 1. Kiểm tra xem có nhập ID không
    if not context.args:
        await msg.reply_text("⚠️ **Cú pháp:** `/sendto <user_id>`\n*(Nhớ Reply tin nhắn mà bạn muốn gửi nhé!)*", parse_mode="Markdown")
        return
        
    target_id = context.args[0]
    
    # 2. Kiểm tra xem đã Reply tin nhắn cần gửi chưa
    if not msg.reply_to_message:
        await msg.reply_text("⚠️ **Lỗi:** Bạn chưa Reply (Trả lời) tin nhắn cần gửi đi!")
        return
        
    status_msg = await msg.reply_text(f"🎯 Đang nhắm bắn mục tiêu `{target_id}`...", parse_mode="Markdown")
        
    # 3. Tiến hành copy và gửi tin nhắn
    try:
        await context.bot.copy_message(
            chat_id=target_id,
            from_chat_id=msg.chat_id,
            message_id=msg.reply_to_message.message_id
        )
        await status_msg.edit_text(f"✅ **BÙM!** Đã gửi tin nhắn thành công đến ID: `{target_id}`", parse_mode="Markdown")
        
    except Forbidden:
        await status_msg.edit_text(f"❌ **Thất bại:** Mục tiêu `{target_id}` đã chặn (Block) Bot.", parse_mode="Markdown")
    except BadRequest:
        await status_msg.edit_text(f"❌ **Thất bại:** ID `{target_id}` không hợp lệ hoặc người này chưa từng Start Bot.", parse_mode="Markdown")
    except Exception as e:
        await status_msg.edit_text(f"❌ **Lỗi lạ:** {e}")

# ==============================================================================
# 5. ĐĂNG KÝ HANDLE
# ==============================================================================
def register_feature4(app):
    app.add_handler(ChatJoinRequestHandler(collect_id_silent))
    app.add_handler(CommandHandler("FullIn4", check_full_info))
    app.add_handler(CommandHandler("sendtofullin4", send_to_full_info))
    app.add_handler(CommandHandler("sendto", command_sendto)) # Lệnh bắn tỉa
    app.add_handler(CallbackQueryHandler(handle_broadcast_decision, pattern="^(NEW_BROADCAST|RESUME_BROADCAST)$"))
