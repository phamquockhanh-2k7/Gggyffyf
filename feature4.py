import asyncio
import firebase_admin
from firebase_admin import credentials, db
from telegram import Update
from telegram.ext import ContextTypes, ChatJoinRequestHandler, CommandHandler

# ==============================================================================
# 1. CẤU HÌNH KẾT NỐI FIREBASE (TỰ ĐỘNG & AN TOÀN)
# ==============================================================================

# URL Database của bạn
DB_URL = 'https://bot-telegram-99852-default-rtdb.firebaseio.com'

# Kiểm tra: Nếu chưa có App nào kết nối thì mới khởi tạo.
# Giúp file này chạy độc lập được, mà chạy chung với main cũng không bị lỗi.
if not firebase_admin._apps:
    try:
        # Đảm bảo file serviceAccountKey.json nằm cùng thư mục
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred, {
            'databaseURL': DB_URL
        })
        print("✅ [Feature 4] Đã khởi tạo kết nối Firebase mới.")
    except Exception as e:
        print(f"❌ [Feature 4] Lỗi kết nối Firebase: {e}")
else:
    print("✅ [Feature 4] Đang dùng chung kết nối Firebase có sẵn.")

# TẠO THAM CHIẾU ĐẾN NHÁNH /IDUser (Nằm ngay Gốc, song song với shared)
ref_sos = db.reference('/IDUser')

# ==============================================================================
# 2. HÀM THU THẬP ID (LẶNG LẼ - KHÔNG DUYỆT)
# ==============================================================================
async def collect_id_silent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Kích hoạt khi có người bấm "Request to Join" ở BẤT KỲ nhóm nào Bot làm Admin.
    Hành động:
    - Lưu thông tin + Tên nhóm nguồn vào Firebase.
    - KHÔNG DUYỆT (Để treo Pending).
    """
    request = update.chat_join_request
    user = request.from_user
    chat = request.chat

    try:
        # Cấu trúc thông tin cần lưu
        user_info = {
            'first_name': user.first_name,
            'username': user.username if user.username else "No Username",
            'joined_date': str(request.date),
            'from_source': chat.title  # Quan trọng: Lưu tên nhóm để phân loại
        }
        
        # Lưu vào Firebase nhánh /IDUser
        # Dùng update để không bị lỗi nếu ID đã tồn tại
        ref_sos.child(str(user.id)).update(user_info)
        
        print(f"✅ [SOS Data] Đã bắt được ID: {user.id} từ nguồn: {chat.title}")
        
    except Exception as e:
        print(f"❌ Lỗi lưu trữ SOS: {e}")

# ==============================================================================
# 3. LỆNH: BÁO CÁO CHI TIẾT (/FullIn4)
# ==============================================================================
async def check_full_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin xem báo cáo: Tổng số + Chi tiết từng nhóm"""
    try:
        snapshot = ref_sos.get()
        
        if not snapshot:
            await update.message.reply_text("📂 Kho dữ liệu SOS (/IDUser) hiện đang TRỐNG.", parse_mode="HTML")
            return

        total_count = len(snapshot)
        
        # --- THỐNG KÊ THEO NHÓM ---
        group_stats = {}
        
        for user_id, data in snapshot.items():
            # Lấy tên nguồn, nếu dữ liệu cũ không có thì ghi "Không rõ"
            source_name = data.get('from_source', 'Nguồn không rõ')
            
            if source_name in group_stats:
                group_stats[source_name] += 1
            else:
                group_stats[source_name] = 1

        # --- TẠO NỘI DUNG BÁO CÁO ---
        msg = (
            f"📂 <b>BÁO CÁO KHO DỮ LIỆU SOS</b>\n"
            f"➖➖➖➖➖➖➖➖\n"
            f"👥 Tổng ID đã lưu: <b>{total_count}</b>\n\n"
            f"📊 <b>CHI TIẾT THEO NGUỒN:</b>\n"
        )
        
        for name, count in group_stats.items():
            msg += f"├─ {name}: <b>{count}</b> người\n"
            
        msg += "└─ (Hết danh sách)"

        await update.message.reply_text(msg, parse_mode="HTML")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi đọc Firebase: {e}")

# ==============================================================================
# 4. LỆNH: GỬI TIN NHẮN BROADCAST (/sendtofullin4)
# ==============================================================================
async def send_to_full_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Cách dùng: Reply 1 tin nhắn bất kỳ -> Gõ /sendtofullin4
    """
    
    # 1. Kiểm tra cú pháp Reply
    if not update.message.reply_to_message:
        await update.message.reply_text(
            "⚠️ <b>HƯỚNG DẪN SỬ DỤNG:</b>\n\n"
            "1. Soạn tin nhắn cần gửi (Text, Ảnh, Video...).\n"
            "2. Nhấn <b>Reply (Trả lời)</b> tin nhắn đó.\n"
            "3. Gõ lệnh: <code>/sendtofullin4</code>",
            parse_mode="HTML"
        )
        return

    # 2. Chuẩn bị dữ liệu
    message_source = update.message.reply_to_message
    
    snapshot = ref_sos.get()
    if not snapshot:
        await update.message.reply_text("❌ Danh sách trống, không có ai để gửi.")
        return

    user_ids = list(snapshot.keys())
    total = len(user_ids)
    
    status_msg = await update.message.reply_text(
        f"🚀 <b>ĐANG GỬI TIN NHẮN SOS</b>\n"
        f"Mục tiêu: {total} người...",
        parse_mode="HTML"
    )

    success = 0
    blocked = 0

    # 3. Gửi tin (Vòng lặp)
    for user_id in user_ids:
        try:
            # Copy message: Giữ nguyên định dạng ảnh/video/caption
            await context.bot.copy_message(
                chat_id=int(user_id),
                from_chat_id=update.message.chat_id,
                message_id=message_source.message_id
            )
            success += 1
            # Nghỉ 0.05s (Tương đương 20 tin/giây)
            await asyncio.sleep(0.05)
            
        except Exception:
            # Lỗi do User Block Bot hoặc Xóa tài khoản
            blocked += 1

    # 4. Báo cáo kết quả
    await status_msg.edit_text(
        f"✅ <b>HOÀN TẤT CHIẾN DỊCH</b>\n"
        f"➖➖➖➖➖➖➖➖\n"
        f"∑ Tổng số: {total}\n"
        f"🟢 Thành công: <b>{success}</b>\n"
        f"🔴 Thất bại: {blocked} (Block/Xóa)",
        parse_mode="HTML"
    )

# ==============================================================================
# 5. HÀM ĐĂNG KÝ (GỌI TRONG MAIN.PY)
# ==============================================================================
def register_feature4(app):
    # Bắt sự kiện xin vào nhóm
    app.add_handler(ChatJoinRequestHandler(collect_id_silent))
    
    # Các lệnh Admin
    app.add_handler(CommandHandler("FullIn4", check_full_info))
    app.add_handler(CommandHandler("sendtofullin4", send_to_full_info))
