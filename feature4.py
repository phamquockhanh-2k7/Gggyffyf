import asyncio
import requests
from telegram import Update
from telegram.ext import ContextTypes, ChatJoinRequestHandler, CommandHandler

# ==============================================================================
# CẤU HÌNH KẾT NỐI (Dùng Link trực tiếp - KHÔNG CẦN FILE KEY)
# ==============================================================================

# Link gốc của bạn (Lưu ý: Không có dấu / ở cuối)
BASE_DB_URL = 'https://bot-telegram-99852-default-rtdb.firebaseio.com'

# ==============================================================================
# HÀM THU THẬP ID (LẶNG LẼ)
# ==============================================================================
async def collect_id_silent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lưu ID người xin vào nhóm qua REST API"""
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
        
        # Tạo đường dẫn cập nhật: /IDUser/{user_id}.json
        url = f"{BASE_DB_URL}/IDUser/{user.id}.json"
        
        # Dùng requests.put để lưu (hoặc ghi đè nếu đã có)
        await asyncio.to_thread(requests.put, url, json=user_info)
        
        print(f"✅ [SOS Data] Đã lưu ID: {user.id} (Nguồn: {chat.title})")
        
    except Exception as e:
        print(f"❌ Lỗi lưu trữ SOS: {e}")

# ==============================================================================
# LỆNH: BÁO CÁO CHI TIẾT (/FullIn4)
# ==============================================================================
async def check_full_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lấy dữ liệu từ API về để đếm"""
    try:
        # Lấy toàn bộ nhánh /IDUser
        url = f"{BASE_DB_URL}/IDUser.json"
        res = await asyncio.to_thread(requests.get, url)
        
        if res.status_code != 200 or not res.json():
            await update.message.reply_text("📂 Kho dữ liệu SOS hiện đang TRỐNG.", parse_mode="HTML")
            return

        data = res.json() # Dạng Dictionary { "id1": {...}, "id2": {...} }
        total_count = len(data)
        
        # Thống kê nhóm
        group_stats = {}
        for uid, info in data.items():
            source = info.get('from_source', 'Không rõ')
            group_stats[source] = group_stats.get(source, 0) + 1

        msg = (
            f"📂 <b>BÁO CÁO SOS (REST API)</b>\n"
            f"➖➖➖➖➖➖➖➖\n"
            f"👥 Tổng ID: <b>{total_count}</b>\n\n"
            f"📊 <b>CHI TIẾT:</b>\n"
        )
        for name, count in group_stats.items():
            msg += f"├─ {name}: <b>{count}</b>\n"
            
        await update.message.reply_text(msg, parse_mode="HTML")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi đọc API: {e}")

# ==============================================================================
# LỆNH: GỬI TIN NHẮN BROADCAST (/sendtofullin4)
# ==============================================================================
async def send_to_full_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ Hãy Reply tin nhắn cần gửi và gõ lệnh.", parse_mode="HTML")
        return

    # Lấy danh sách ID
    url = f"{BASE_DB_URL}/IDUser.json"
    try:
        res = await asyncio.to_thread(requests.get, url)
        if res.status_code != 200 or not res.json():
            await update.message.reply_text("❌ Danh sách trống.")
            return
            
        user_ids = list(res.json().keys()) # Lấy danh sách ID
        
        status_msg = await update.message.reply_text(f"🚀 Đang gửi cho {len(user_ids)} người...", parse_mode="HTML")
        
        success = 0
        blocked = 0

        for user_id in user_ids:
            try:
                await context.bot.copy_message(
                    chat_id=int(user_id),
                    from_chat_id=update.message.chat_id,
                    message_id=update.message.reply_to_message.message_id
                )
                success += 1
                await asyncio.sleep(0.05) # Chống spam
            except:
                blocked += 1

        await status_msg.edit_text(f"✅ HOÀN TẤT\n🟢 Thành công: {success}\n🔴 Thất bại: {blocked}")

    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi kết nối: {e}")

# ==============================================================================
# ĐĂNG KÝ
# ==============================================================================
# ...(Giữ nguyên các hàm import và hàm xử lý logic bên trên)...
# CHỈ SỬA ĐOẠN CUỐI CÙNG NÀY THÔI:

# ==============================================================================
# ĐĂNG KÝ
# ==============================================================================
def register_feature4(app):
    # Sự kiện này bắt buộc phải chạy ở nhóm (để bắt người xin vào nhóm) nên KHÔNG thêm filter Private
    app.add_handler(ChatJoinRequestHandler(collect_id_silent))
    
    # Nhưng lệnh xem báo cáo thì PHẢI là tin nhắn riêng (để không lộ thông tin trong nhóm)
    app.add_handler(CommandHandler("FullIn4", check_full_info, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("sendtofullin4", send_to_full_info, filters=filters.ChatType.PRIVATE))
