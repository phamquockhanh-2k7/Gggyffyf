import asyncio
import requests
from telegram import Update
from telegram.ext import ContextTypes, ChatJoinRequestHandler, CommandHandler

# ==============================================================================
# CẤU HÌNH (Dùng Link trực tiếp - KHÔNG CẦN FILE KEY)
# ==============================================================================
BASE_DB_URL = 'https://bot-telegram-99852-default-rtdb.firebaseio.com'

# ==============================================================================
# 1. TỰ ĐỘNG THU THẬP ID KHI CÓ NGƯỜI XIN VÀO NHÓM
# ==============================================================================
async def collect_id_silent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Hàm này chạy ngầm khi có 'Request to Join Group'.
    Nó sẽ lưu thông tin user vào nhánh /IDUser trên Firebase.
    """
    request = update.chat_join_request
    user = request.from_user
    chat = request.chat

    try:
        user_info = {
            'first_name': user.first_name,
            'username': user.username if user.username else "No Username",
            'joined_date': str(request.date),
            'from_source': chat.title  # Lưu tên nhóm nguồn
        }
        
        # Lưu vào Firebase theo ID người dùng
        url = f"{BASE_DB_URL}/IDUser/{user.id}.json"
        
        # Dùng requests.put để lưu (ghi đè nếu đã tồn tại để cập nhật nguồn mới nhất)
        await asyncio.to_thread(requests.put, url, json=user_info)
        
        print(f"✅ [SOS Data] Đã lưu ID: {user.id} (Nguồn: {chat.title})")
        
    except Exception as e:
        print(f"❌ Lỗi lưu trữ SOS: {e}")

# ==============================================================================
# 2. LỆNH ADMIN: XEM BÁO CÁO (/FullIn4)
# ==============================================================================
async def check_full_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin xem thống kê số lượng User đã thu thập"""
    try:
        url = f"{BASE_DB_URL}/IDUser.json"
        res = await asyncio.to_thread(requests.get, url)
        
        if res.status_code != 200 or not res.json():
            await update.message.reply_text("📂 Kho dữ liệu SOS hiện đang TRỐNG.", parse_mode="HTML")
            return

        data = res.json()
        total_count = len(data)
        
        # Thống kê chi tiết theo nguồn
        group_stats = {}
        for uid, info in data.items():
            source = info.get('from_source', 'Không rõ')
            group_stats[source] = group_stats.get(source, 0) + 1
            
        # Sắp xếp từ cao xuống thấp (Nhóm nào nhiều mem hiện lên đầu)
        sorted_stats = sorted(group_stats.items(), key=lambda item: item[1], reverse=True)

        msg = (
            f"📂 <b>BÁO CÁO SOS SYSTEM</b>\n"
            f"➖➖➖➖➖➖➖➖\n"
            f"👥 Tổng ID đã lưu: <b>{total_count}</b>\n\n"
            f"📊 <b>TOP NGUỒN HIỆU QUẢ:</b>\n"
        )
        
        for name, count in sorted_stats:
            msg += f"🔥 {name}: <b>{count}</b> thành viên\n"
            
        await update.message.reply_text(msg, parse_mode="HTML")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi đọc API: {e}")

# ==============================================================================
# 3. LỆNH ADMIN: GỬI TIN NHẮN HÀNG LOẠT (/sendtofullin4)
# ==============================================================================
async def send_to_full_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Reply một tin nhắn bất kỳ và dùng lệnh này để gửi nó cho toàn bộ User trong list SOS.
    """
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ <b>HƯỚNG DẪN:</b>\nHãy Reply (Trả lời) tin nhắn cần gửi quảng cáo và gõ lệnh này.", parse_mode="HTML")
        return

    # Lấy danh sách ID từ Firebase
    url = f"{BASE_DB_URL}/IDUser.json"
    try:
        res = await asyncio.to_thread(requests.get, url)
        if res.status_code != 200 or not res.json():
            await update.message.reply_text("❌ Danh sách trống, không có ai để gửi.")
            return
            
        user_ids = list(res.json().keys())
        total = len(user_ids)
        
        status_msg = await update.message.reply_text(f"🚀 Đang bắt đầu gửi cho {total} người...", parse_mode="HTML")
        
        success = 0
        blocked = 0

        for user_id in user_ids:
            try:
                # Copy tin nhắn gốc gửi sang cho user
                await context.bot.copy_message(
                    chat_id=int(user_id),
                    from_chat_id=update.message.chat_id,
                    message_id=update.message.reply_to_message.message_id
                )
                success += 1
                # Nghỉ cực ngắn để tránh bị Telegram chặn spam
                await asyncio.sleep(0.05) 
            except Exception:
                # Nếu User chặn bot hoặc xóa tài khoản
                blocked += 1

        await status_msg.edit_text(
            f"✅ <b>HOÀN TẤT CHIẾN DỊCH</b>\n"
            f"➖➖➖➖➖➖➖➖\n"
            f"🟢 Thành công: <b>{success}</b>\n"
            f"🔴 Thất bại: {blocked} (Block/Die)",
            parse_mode="HTML"
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi hệ thống: {e}")

# ==============================================================================
# 4. ĐĂNG KÝ
# ==============================================================================
def register_feature4(app):
    # Bắt sự kiện xin vào nhóm (ChatJoinRequest)
    app.add_handler(ChatJoinRequestHandler(collect_id_silent))
    
    # Các lệnh Admin (Chạy được cả trong nhóm và IB riêng)
    app.add_handler(CommandHandler("FullIn4", check_full_info))
    app.add_handler(CommandHandler("sendtofullin4", send_to_full_info))
