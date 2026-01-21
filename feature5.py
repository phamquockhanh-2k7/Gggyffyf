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
    """Cách 1: Gõ lệnh /add trực tiếp trong nhóm (Vẫn giữ để dùng cho Nhóm)"""
    msg = update.effective_message
    if not msg: return

    chat_id = update.effective_chat.id
    chat_title = update.effective_chat.title or "Không tên"
    chat_type = update.effective_chat.type

    if chat_type == "private":
        await msg.reply_text("❌ Hãy dùng lệnh này trong Nhóm.\n💡 Với Kênh (Channel), hãy Forward 1 bài từ Kênh đó vào đây để thêm.")
        return

    try:
        url = f"{BROADCAST_DB}/{chat_id}.json"
        await asyncio.to_thread(requests.put, url, json=chat_title)
        await msg.reply_text(f"✅ Đã thêm nhóm **{chat_title}** (ID: `{chat_id}`)!", parse_mode="Markdown")
    except Exception as e:
        await msg.reply_text(f"❌ Lỗi: {e}")

async def remove_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gõ lệnh /remove để xóa"""
    msg = update.effective_message
    chat_id = update.effective_chat.id
    try:
        url = f"{BROADCAST_DB}/{chat_id}.json"
        await asyncio.to_thread(requests.delete, url)
        await msg.reply_text("🗑 Đã xóa nơi này khỏi danh sách phát sóng.")
    except:
        await msg.reply_text("❌ Lỗi xóa data.")

async def list_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xem danh sách"""
    if update.effective_chat.type != "private": return
    try:
        res = await asyncio.to_thread(requests.get, f"{BROADCAST_DB}.json")
        data = res.json()
        if not data:
            await update.message.reply_text("📭 Danh sách trống.")
            return
        
        text = "📋 **DANH SÁCH NHÓM/KÊNH ĐÍCH:**\n"
        for c_id, name in data.items():
            text += f"- {name} (`{c_id}`)\n"
        await update.message.reply_text(text, parse_mode="Markdown")
    except:
        await update.message.reply_text("❌ Lỗi dữ liệu.")

# ==============================================================================
# 2. CHẾ ĐỘ PHÁT SÓNG
# ==============================================================================

async def broadcast_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    args = context.args
    
    if args and args[0].lower() == "on":
        context.user_data['current_mode'] = 'BROADCAST'
        await update.message.reply_text("📡 **ĐÃ BẬT MODE PHÁT SÓNG!**\n👉 Mọi tin nhắn/forward bạn gửi bây giờ sẽ được chuyển đi các kênh đích.")
    elif args and args[0].lower() == "off":
        context.user_data['current_mode'] = None
        await update.message.reply_text("zzz **ĐÃ TẮT MODE PHÁT SÓNG.**\n💡 Bây giờ bạn có thể Forward bài từ Kênh vào đây để thêm Kênh đó vào danh sách.")

# ==============================================================================
# 3. XỬ LÝ TIN NHẮN (THÔNG MINH HƠN)
# ==============================================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hàm xử lý đa năng: Vừa thêm kênh (khi tắt) vừa phát sóng (khi bật)"""
    msg = update.effective_message
    if not msg or update.effective_chat.type != "private": return
    
    mode = context.user_data.get('current_mode')

    # =======================================================
    # TRƯỜNG HỢP 1: ĐANG TẮT MODE (/bc off) -> TÍNH NĂNG THÊM KÊNH
    # =======================================================
    if mode != 'BROADCAST':
        # Kiểm tra xem có phải tin nhắn Forward từ Kênh/Nhóm không?
        if msg.forward_from_chat:
            fwd_chat = msg.forward_from_chat
            chat_id = fwd_chat.id
            title = fwd_chat.title or "Không tên"
            
            # Lưu vào Firebase
            try:
                url = f"{BROADCAST_DB}/{chat_id}.json"
                await asyncio.to_thread(requests.put, url, json=title)
                await msg.reply_text(f"🎯 **ĐÃ BẮT ĐƯỢC ID KÊNH!**\n\n✅ Đã thêm: **{title}**\n🆔 ID: `{chat_id}`\n\n(Lần sau bật /bc on là gửi được vào đây nhé)", parse_mode="Markdown")
            except Exception as e:
                await msg.reply_text(f"❌ Lỗi lưu: {e}")
        else:
            # Nếu nhắn tin bình thường thì hướng dẫn
            await msg.reply_text("💡 **HƯỚNG DẪN:**\n\n1️⃣ **Thêm Kênh:** Forward 1 bài từ Kênh vào đây (khi đang tắt /bc).\n2️⃣ **Phát sóng:** Gõ `/bc on` rồi gửi nội dung.")
        return

    # =======================================================
    # TRƯỜNG HỢP 2: ĐANG BẬT MODE (/bc on) -> TÍNH NĂNG PHÁT SÓNG
    # =======================================================
    
    # Lấy danh sách đích
    try:
        res = await asyncio.to_thread(requests.get, f"{BROADCAST_DB}.json")
        targets = res.json()
        if not targets:
            await msg.reply_text("⚠️ Danh sách trống. Hãy tắt bc (`/bc off`) rồi forward bài từ kênh vào đây để thêm.")
            return
    except:
        return

    status_msg = await msg.reply_text(f"⏳ Đang gửi đến {len(targets)} nơi...")
    success = 0
    fail = 0
    
    for target_id in targets.keys():
        try:
            # Copy tin nhắn gửi đi (An toàn hơn Forward nếu nguồn bị xóa)
            await context.bot.copy_message(
                chat_id=target_id,
                from_chat_id=msg.chat_id,
                message_id=msg.message_id
            )
            success += 1
            await asyncio.sleep(0.1)
        except Exception:
            fail += 1
    
    await status_msg.edit_text(f"✅ Gửi xong: {success}\n❌ Lỗi: {fail}\n(Nếu lỗi Kênh: Nhớ set Bot làm Admin nhé)")

# ==============================================================================
# 4. ĐĂNG KÝ
# ==============================================================================
def register_feature5(app):
    app.add_handler(CommandHandler("add", add_group))
    app.add_handler(CommandHandler("remove", remove_group))
    app.add_handler(CommandHandler("list", list_groups))
    app.add_handler(CommandHandler("bc", broadcast_mode))
    
    # Bắt tất cả tin nhắn
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message), group=2)
