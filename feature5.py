import asyncio
import requests
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters

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
    # Sử dụng effective_message để lấy tin nhắn từ cả Nhóm và Kênh
    msg = update.effective_message
    if not msg: return

    chat_id = update.effective_chat.id
    chat_title = update.effective_chat.title or "Không tên"
    chat_type = update.effective_chat.type

    # Lệnh này phải dùng trong Nhóm hoặc Kênh
    if chat_type == "private":
        await msg.reply_text("❌ Lệnh này phải dùng trong Nhóm hoặc Kênh cần thêm.")
        return

    # Lưu vào Firebase
    try:
        url = f"{BROADCAST_DB}/{chat_id}.json"
        await asyncio.to_thread(requests.put, url, json=chat_title)
        await msg.reply_text(f"✅ Đã thêm **{chat_title}** (ID: `{chat_id}`) vào danh sách phát sóng!", parse_mode="Markdown")
    except Exception as e:
        await msg.reply_text(f"❌ Lỗi lưu data: {e}")

async def remove_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gõ lệnh /remove để xóa nhóm khỏi danh sách"""
    msg = update.effective_message
    if not msg: return
    
    chat_id = update.effective_chat.id
    try:
        url = f"{BROADCAST_DB}/{chat_id}.json"
        await asyncio.to_thread(requests.delete, url)
        await msg.reply_text("🗑 Đã xóa nơi này khỏi danh sách phát sóng.")
    except:
        await msg.reply_text("❌ Lỗi xóa data.")

async def list_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xem danh sách các nhóm đang lưu"""
    msg = update.effective_message
    if not msg: return

    # Chỉ hoạt động trong chat riêng
    if update.effective_chat.type != "private": return

    try:
        res = await asyncio.to_thread(requests.get, f"{BROADCAST_DB}.json")
        data = res.json()
        if not data:
            await msg.reply_text("📭 Danh sách trống.")
            return
        
        text = "📋 **DANH SÁCH NHÓM/KÊNH ĐÍCH:**\n"
        for c_id, name in data.items():
            text += f"- {name} (`{c_id}`)\n"
        await msg.reply_text(text, parse_mode="Markdown")
    except:
        await msg.reply_text("❌ Lỗi lấy dữ liệu.")

# ==============================================================================
# 2. CHẾ ĐỘ PHÁT SÓNG (BẬT/TẮT)
# ==============================================================================

async def broadcast_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bật tắt chế độ chuyển tiếp"""
    msg = update.effective_message
    if not msg: return
    
    args = context.args
    if args and args[0].lower() == "on":
        context.user_data['current_mode'] = 'BROADCAST'
        await msg.reply_text("📡 **ĐÃ BẬT CHẾ ĐỘ AUTO FORWARD!**\n\n👉 Bây giờ hãy Forward bài viết vào đây, Bot sẽ chuyển tiếp đi tất cả các nhóm.")
    elif args and args[0].lower() == "off":
        context.user_data['current_mode'] = None
        await msg.reply_text("zzz Đã TẮT chế độ Auto Forward.")

# ==============================================================================
# 3. XỬ LÝ CHUYỂN TIẾP (AUTO FORWARD)
# ==============================================================================

async def handle_broadcast_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hàm xử lý chính: Nhận tin -> Forward đi muôn nơi"""
    msg = update.effective_message
    if not msg: return
    
    # Chỉ chạy trong Private
    if update.effective_chat.type != "private": return
    
    # Chỉ chạy khi mode là BROADCAST
    if context.user_data.get('current_mode') != 'BROADCAST': return
    
    # Lấy danh sách nhóm đích
    try:
        res = await asyncio.to_thread(requests.get, f"{BROADCAST_DB}.json")
        targets = res.json()
        if not targets:
            await msg.reply_text("⚠️ Danh sách trống. Hãy thêm Bot vào nhóm/kênh và gõ /add.")
            return
    except:
        return

    status_msg = await msg.reply_text(f"⏳ Đang xử lý gửi đến {len(targets)} nơi...")
    success_count = 0
    fail_count = 0
    
    msg_id = msg.message_id
    from_chat_id = msg.chat_id

    for target_id in targets.keys():
        try:
            # ⚠️ Bot phải là Admin ở nhóm/kênh đích mới gửi được
            await context.bot.forward_message(
                chat_id=target_id,
                from_chat_id=from_chat_id,
                message_id=msg_id
            )
            success_count += 1
            await asyncio.sleep(0.1) 
            
        except Exception as e:
            print(f"Lỗi gửi ID {target_id}: {e}")
            fail_count += 1
    
    await status_msg.edit_text(f"✅ Thành công: {success_count}\n❌ Thất bại: {fail_count}\n(Nếu thất bại ở Kênh, hãy kiểm tra Bot đã là Admin chưa)")

# ==============================================================================
# 4. ĐĂNG KÝ
# ==============================================================================
def register_feature5(app):
    app.add_handler(CommandHandler("add", add_group))
    app.add_handler(CommandHandler("remove", remove_group))
    app.add_handler(CommandHandler("list", list_groups))
    app.add_handler(CommandHandler("bc", broadcast_mode))
    
    # Bắt tất cả tin nhắn
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_broadcast_content), group=2)
