import asyncio
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# ==============================================================================
# ⚙️ CẤU HÌNH DATABASE
# ==============================================================================
BASE_URL = "https://bot-telegram-99852-default-rtdb.firebaseio.com"
BROADCAST_DB = f"{BASE_URL}/broadcast_channels"

# ==============================================================================
# 1. QUẢN LÝ THÊM NHÓM (Cả lệnh /add và Forward)
# ==============================================================================

async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gõ lệnh /add trực tiếp trong nhóm"""
    msg = update.effective_message
    if not msg: return

    chat_id = update.effective_chat.id
    chat_title = update.effective_chat.title or "Không tên"
    chat_type = update.effective_chat.type

    if chat_type == "private":
        await msg.reply_text("❌ Lệnh này phải dùng trong Nhóm.\n💡 Với Kênh (Channel), hãy Forward 1 bài từ Kênh đó vào đây để thêm.")
        return

    try:
        url = f"{BROADCAST_DB}/{chat_id}.json"
        await asyncio.to_thread(requests.put, url, json=chat_title)
        await msg.reply_text(f"✅ Đã thêm nhóm **{chat_title}** (ID: `{chat_id}`)!", parse_mode="Markdown")
    except Exception as e:
        await msg.reply_text(f"❌ Lỗi: {e}")

# ==============================================================================
# 2. MENU XÓA (TÍNH NĂNG MỚI)
# ==============================================================================

async def show_delete_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hiện bảng nút bấm để xóa"""
    # Lấy danh sách từ Firebase
    try:
        res = await asyncio.to_thread(requests.get, f"{BROADCAST_DB}.json")
        data = res.json()
        
        if not data:
            await update.message.reply_text("📭 Danh sách trống, không có gì để xóa.")
            return

        keyboard = []
        # Tạo từng nút cho từng nhóm
        for c_id, name in data.items():
            # Callback data format: DEL_ID_<chat_id>
            btn_text = f"❌ {name}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"DEL_ID_{c_id}")])
        
        # Nút xóa tất cả
        keyboard.append([InlineKeyboardButton("🗑 XÓA TẤT CẢ (DELETE ALL)", callback_data="DEL_ALL")])
        # Nút đóng
        keyboard.append([InlineKeyboardButton("Đóng Menu", callback_data="CLOSE_MENU")])

        await update.message.reply_text(
            f"📋 **QUẢN LÝ XÓA:**\nHiện có {len(data)} nhóm/kênh đang lưu.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi tải dữ liệu: {e}")

async def handle_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý khi bấm nút xóa"""
    query = update.callback_query
    await query.answer() # Báo cho Telegram biết đã nhận lệnh
    
    data = query.data
    
    # 1. Xử lý đóng menu
    if data == "CLOSE_MENU":
        await query.message.delete()
        return

    # 2. Xử lý xóa TẤT CẢ
    if data == "DEL_ALL":
        try:
            await asyncio.to_thread(requests.delete, f"{BROADCAST_DB}.json")
            await query.edit_message_text("✅ Đã xóa sạch toàn bộ danh sách phát sóng!")
        except:
            await query.edit_message_text("❌ Lỗi khi xóa tất cả.")
        return

    # 3. Xử lý xóa 1 Nhóm cụ thể
    if data.startswith("DEL_ID_"):
        chat_id_to_del = data.split("DEL_ID_")[1]
        try:
            # Xóa trên Firebase
            await asyncio.to_thread(requests.delete, f"{BROADCAST_DB}/{chat_id_to_del}.json")
            
            # --- CẬP NHẬT LẠI MENU (Load lại danh sách mới) ---
            res = await asyncio.to_thread(requests.get, f"{BROADCAST_DB}.json")
            new_data = res.json()
            
            if not new_data:
                await query.edit_message_text("✅ Đã xóa mục cuối cùng. Danh sách giờ trống rỗng.")
                return

            # Vẽ lại phím
            new_keyboard = []
            for c_id, name in new_data.items():
                new_keyboard.append([InlineKeyboardButton(f"❌ {name}", callback_data=f"DEL_ID_{c_id}")])
            new_keyboard.append([InlineKeyboardButton("🗑 XÓA TẤT CẢ", callback_data="DEL_ALL")])
            new_keyboard.append([InlineKeyboardButton("Đóng Menu", callback_data="CLOSE_MENU")])
            
            await query.edit_message_text(
                f"✅ Đã xóa thành công!\nCòn lại {len(new_data)} nhóm:",
                reply_markup=InlineKeyboardMarkup(new_keyboard)
            )
        except Exception as e:
            await query.message.reply_text(f"Lỗi: {e}")

# ==============================================================================
# 3. CHẾ ĐỘ PHÁT SÓNG
# ==============================================================================

async def broadcast_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    args = context.args
    
    if args and args[0].lower() == "on":
        context.user_data['current_mode'] = 'BROADCAST'
        await update.message.reply_text("📡 **ĐÃ BẬT MODE PHÁT SÓNG!**\n👉 Mọi tin nhắn/forward bạn gửi bây giờ sẽ được CHUYỂN TIẾP (Forward) đi.")
    elif args and args[0].lower() == "off":
        context.user_data['current_mode'] = None
        await update.message.reply_text("zzz **ĐÃ TẮT MODE PHÁT SÓNG.**\n💡 Bây giờ bạn có thể Forward bài từ Kênh vào đây để thêm Kênh đó vào danh sách.")

async def list_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xem danh sách dạng text (backup)"""
    if update.effective_chat.type != "private": return
    try:
        res = await asyncio.to_thread(requests.get, f"{BROADCAST_DB}.json")
        data = res.json()
        if not data:
            await update.message.reply_text("📭 Danh sách trống.")
            return
        text = "📋 **DANH SÁCH:**\n"
        for c_id, name in data.items():
            text += f"- {name} (`{c_id}`)\n"
        await update.message.reply_text(text, parse_mode="Markdown")
    except: pass

# ==============================================================================
# 4. XỬ LÝ TIN NHẮN (LOGIC CHÍNH)
# ==============================================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or update.effective_chat.type != "private": return
    
    mode = context.user_data.get('current_mode')

    # --- MODE TẮT: THÊM KÊNH BẰNG FORWARD ---
    if mode != 'BROADCAST':
        if msg.forward_from_chat:
            fwd_chat = msg.forward_from_chat
            chat_id = fwd_chat.id
            title = fwd_chat.title or "Không tên"
            try:
                url = f"{BROADCAST_DB}/{chat_id}.json"
                await asyncio.to_thread(requests.put, url, json=title)
                await msg.reply_text(f"🎯 **BẮT ĐƯỢC KÊNH!**\n✅ Thêm: **{title}**\n🆔 `{chat_id}`", parse_mode="Markdown")
            except Exception as e:
                await msg.reply_text(f"❌ Lỗi: {e}")
        else:
            await msg.reply_text("💡 **MENU:**\n/bc on - Bật chuyển tiếp\n/delete - Mở menu xóa\nHoặc Forward bài từ kênh vào đây để thêm.")
        return

    # --- MODE BẬT: CHUYỂN TIẾP (FORWARD) ---
    # Lấy danh sách đích
    try:
        res = await asyncio.to_thread(requests.get, f"{BROADCAST_DB}.json")
        targets = res.json()
        if not targets:
            await msg.reply_text("⚠️ Danh sách trống. Hãy tắt bc (/bc off) rồi thêm kênh trước.")
            return
    except: return

    status_msg = await msg.reply_text(f"⏳ Đang Forward đến {len(targets)} nơi...")
    success = 0
    fail = 0
    
    # ID tin nhắn gốc cần forward (Tại khung chat bot)
    msg_id = msg.message_id
    from_chat_id = msg.chat_id

    for target_id in targets.keys():
        try:
            # ✅ SỬ DỤNG FORWARD_MESSAGE ĐỂ GIỮ NGUYÊN NGUỒN (Forwarded from...)
            await context.bot.forward_message(
                chat_id=target_id,
                from_chat_id=from_chat_id,
                message_id=msg_id
            )
            success += 1
            await asyncio.sleep(0.1) # Delay nhẹ tránh spam
        except Exception:
            fail += 1
    
    await status_msg.edit_text(f"✅ Forward xong: {success}\n❌ Lỗi: {fail}")

# ==============================================================================
# 5. ĐĂNG KÝ
# ==============================================================================
def register_feature5(app):
    app.add_handler(CommandHandler("add", add_group))
    app.add_handler(CommandHandler("list", list_groups))
    app.add_handler(CommandHandler("bc", broadcast_mode))
    
    # Lệnh Delete mới
    app.add_handler(CommandHandler("delete", show_delete_menu))
    app.add_handler(CallbackQueryHandler(handle_delete_callback, pattern="^(DEL_|CLOSE)"))
    
    # Bắt tất cả tin nhắn
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message), group=2)
