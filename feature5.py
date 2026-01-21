import asyncio
import requests
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from feature1 import check_channel_membership # Dùng chung hàm check thành viên

# ==============================================================================
# ⚙️ CẤU HÌNH DATABASE
# ==============================================================================
BASE_URL = "https://bot-telegram-99852-default-rtdb.firebaseio.com"
BROADCAST_DB = f"{BASE_URL}/broadcast_channels"

# ==============================================================================
# 1. QUẢN LÝ NHÓM/KÊNH (THÊM/XÓA)
# ==============================================================================

async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gõ lệnh /add trong nhóm/kênh để thêm vào danh sách nhận tin"""
    chat_id = update.effective_chat.id
    chat_title = update.effective_chat.title or "Không tên"
    chat_type = update.effective_chat.type

    # Chỉ cho phép Admin thêm (hoặc trong Private thì thôi)
    if chat_type == "private":
        await update.message.reply_text("❌ Lệnh này phải dùng trong Nhóm hoặc Kênh cần thêm.")
        return

    # Lưu vào Firebase
    try:
        url = f"{BROADCAST_DB}/{chat_id}.json"
        # Lưu tên nhóm để dễ quản lý sau này
        await asyncio.to_thread(requests.put, url, json=chat_title)
        await update.message.reply_text(f"✅ Đã thêm nhóm **{chat_title}** vào danh sách phát sóng!", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi lưu data: {e}")

async def remove_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gõ lệnh /remove để xóa nhóm khỏi danh sách"""
    chat_id = update.effective_chat.id
    try:
        url = f"{BROADCAST_DB}/{chat_id}.json"
        await asyncio.to_thread(requests.delete, url)
        await update.message.reply_text("🗑 Đã xóa nhóm này khỏi danh sách phát sóng.")
    except:
        await update.message.reply_text("❌ Lỗi xóa data.")

async def list_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xem danh sách các nhóm đang lưu (Chỉ Admin xem trong private)"""
    if update.effective_chat.type != "private": return
    
    try:
        res = await asyncio.to_thread(requests.get, f"{BROADCAST_DB}.json")
        data = res.json()
        if not data:
            await update.message.reply_text("📭 Danh sách trống.")
            return
        
        msg = "📋 **DANH SÁCH NHÓM ĐÍCH:**\n"
        for c_id, name in data.items():
            msg += f"- {name} (`{c_id}`)\n"
        await update.message.reply_text(msg, parse_mode="Markdown")
    except:
        await update.message.reply_text("❌ Lỗi lấy dữ liệu.")

# ==============================================================================
# 2. CHẾ ĐỘ PHÁT SÓNG (BẬT/TẮT)
# ==============================================================================

async def broadcast_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bật tắt chế độ chuyển tiếp"""
    if not update.message or not await check_channel_membership(update, context): return
    
    args = context.args
    if args and args[0].lower() == "on":
        context.user_data['current_mode'] = 'BROADCAST'
        await update.message.reply_text("📡 **ĐÃ BẬT CHẾ ĐỘ AUTO FORWARD!**\n\n👉 Bây giờ bạn gửi (hoặc forward) bất cứ tin nhắn nào vào đây, Bot sẽ chuyển tiếp nó đến TẤT CẢ các nhóm đã lưu.")
    elif args and args[0].lower() == "off":
        context.user_data['current_mode'] = None
        await update.message.reply_text("zzz Đã TẮT chế độ Auto Forward.")

# ==============================================================================
# 3. XỬ LÝ CHUYỂN TIẾP (AUTO FORWARD)
# ==============================================================================

async def handle_broadcast_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hàm xử lý chính: Nhận tin -> Forward đi muôn nơi"""
    # 1. Kiểm tra điều kiện
    if not update.message: return
    # Chỉ chạy trong Private (Chat riêng với Bot)
    if update.effective_chat.type != "private": return
    # Chỉ chạy khi mode là BROADCAST
    if context.user_data.get('current_mode') != 'BROADCAST': return

    # 2. Lấy danh sách nhóm đích
    try:
        res = await asyncio.to_thread(requests.get, f"{BROADCAST_DB}.json")
        targets = res.json()
        if not targets:
            await update.message.reply_text("⚠️ Chưa có nhóm nào trong danh sách. Hãy thêm Bot vào nhóm và gõ /add.")
            return
    except:
        return

    # 3. Bắt đầu Forward
    # status_msg = await update.message.reply_text(f"⏳ Đang chuyển tiếp đến {len(targets)} nhóm...")
    success_count = 0
    fail_count = 0
    
    # Lấy ID tin nhắn cần forward (Chính là tin nhắn bạn vừa gửi cho Bot)
    msg_id = update.message.message_id
    from_chat_id = update.message.chat_id

    for target_id in targets.keys():
        try:
            # Dùng forward_message để giữ nguyên nguồn gốc (Forwarded from...)
            await context.bot.forward_message(
                chat_id=target_id,
                from_chat_id=from_chat_id,
                message_id=msg_id
            )
            success_count += 1
            # Nghỉ xíu để tránh bị Telegram chặn vì spam nhanh quá
            await asyncio.sleep(0.3) 
            
        except Exception as e:
            # Nếu lỗi (Bot bị kick, nhóm bị xóa...), in ra log và bỏ qua
            print(f"Lỗi gửi đến {target_id}: {e}")
            fail_count += 1
    
    # Báo cáo kết quả
    await update.message.reply_text(f"✅ Đã chuyển tiếp: {success_count} | ❌ Lỗi: {fail_count}")

# ==============================================================================
# 4. ĐĂNG KÝ
# ==============================================================================
def register_feature5(app):
    # Lệnh quản lý nhóm (Dùng trong nhóm)
    app.add_handler(CommandHandler("add", add_group))
    app.add_handler(CommandHandler("remove", remove_group))
    
    # Lệnh quản lý bot (Dùng riêng)
    app.add_handler(CommandHandler("list", list_groups))
    app.add_handler(CommandHandler("bc", broadcast_mode)) # /bc on hoặc /bc off
    
    # Handler bắt tất cả tin nhắn để forward (chạy cuối cùng)
    # Group=2 để nó chạy độc lập, không ảnh hưởng các feature khác
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_broadcast_content), group=2)
