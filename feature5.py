import asyncio
import requests
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# ==============================================================================
# ⚙️ CẤU HÌNH DATABASE
# ==============================================================================
BASE_URL = "https://bot-telegram-99852-default-rtdb.firebaseio.com"
BROADCAST_DB = f"{BASE_URL}/broadcast_channels"
HISTORY_DB = f"{BASE_URL}/broadcast_history" # Nơi lưu lịch sử gửi tin

# Thời gian lưu trữ lịch sử: 3 ngày (tính bằng giây)
# 3 ngày * 24 giờ * 60 phút * 60 giây = 259200
RETENTION_PERIOD = 259200 

# ==============================================================================
# 1. HÀM PHỤ TRỢ (DỌN DẸP & LƯU TRỮ)
# ==============================================================================

async def clean_old_history():
    """Hàm chạy ngầm: Quét và xóa các lịch sử cũ hơn 3 ngày"""
    try:
        res = await asyncio.to_thread(requests.get, f"{HISTORY_DB}.json")
        data = res.json()
        if not data: return

        current_time = int(time.time())
        delete_count = 0

        for msg_id, content in data.items():
            # Nếu tin nhắn đã quá 3 ngày
            if current_time - content.get('time', 0) > RETENTION_PERIOD:
                await asyncio.to_thread(requests.delete, f"{HISTORY_DB}/{msg_id}.json")
                delete_count += 1
        
        if delete_count > 0:
            print(f"🧹 Đã dọn dẹp {delete_count} bản ghi lịch sử cũ.")
    except Exception as e:
        print(f"Lỗi dọn dẹp: {e}")

# ==============================================================================
# 2. QUẢN LÝ THÊM NHÓM
# ==============================================================================

async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg: return
    chat_id = update.effective_chat.id
    chat_title = update.effective_chat.title or "Không tên"
    
    if update.effective_chat.type == "private":
        await msg.reply_text("❌ Lệnh này phải dùng trong Nhóm.\n💡 Với Kênh, hãy Forward 1 bài từ Kênh đó vào đây.")
        return

    try:
        await asyncio.to_thread(requests.put, f"{BROADCAST_DB}/{chat_id}.json", json=chat_title)
        await msg.reply_text(f"✅ Đã thêm **{chat_title}** (ID: `{chat_id}`)!", parse_mode="Markdown")
    except Exception as e:
        await msg.reply_text(f"❌ Lỗi: {e}")

# ==============================================================================
# 3. TÍNH NĂNG THU HỒI (UNDO) - NÂNG CẤP
# ==============================================================================

async def undo_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    1. Nếu Reply vào tin nhắn: Xóa tin nhắn đó ở các nhóm.
    2. Nếu không Reply: Xóa tin nhắn gửi gần nhất (trong phiên chạy).
    """
    msg = update.effective_message
    
    # TRƯỜNG HỢP 1: THU HỒI THEO CHỈ ĐỊNH (REPLY)
    if msg.reply_to_message:
        target_source_id = str(msg.reply_to_message.message_id)
        
        # Tìm trong Database
        try:
            res = await asyncio.to_thread(requests.get, f"{HISTORY_DB}/{target_source_id}.json")
            history_data = res.json()
            
            if not history_data:
                await msg.reply_text("⚠️ Không tìm thấy dữ liệu phát sóng của tin nhắn này (Hoặc đã quá 3 ngày).")
                return

            status_msg = await msg.reply_text("🗑 Đang xử lý xóa...")
            deleted_count = 0
            
            # Duyệt danh sách các nơi đã gửi để xóa
            sent_list = history_data.get('sent_to', [])
            for item in sent_list:
                try:
                    await context.bot.delete_message(chat_id=item['chat_id'], message_id=item['msg_id'])
                    deleted_count += 1
                except: pass
            
            # Xóa xong thì xóa luôn data trong DB để đỡ rác
            await asyncio.to_thread(requests.delete, f"{HISTORY_DB}/{target_source_id}.json")
            await status_msg.edit_text(f"✅ Đã thu hồi tin nhắn được Reply tại {deleted_count} nhóm.")
            return

        except Exception as e:
            await msg.reply_text(f"❌ Lỗi truy xuất: {e}")
            return

    # TRƯỜNG HỢP 2: THU HỒI CÁI MỚI NHẤT (NẾU KHÔNG REPLY)
    last_sent_msgs = context.user_data.get('last_broadcast_history')
    if last_sent_msgs:
        status_msg = await msg.reply_text(f"🗑 Đang thu hồi tin nhắn gần nhất...")
        deleted_count = 0
        for item in last_sent_msgs:
            try:
                await context.bot.delete_message(chat_id=item['chat_id'], message_id=item['msg_id'])
                deleted_count += 1
            except: pass
        context.user_data['last_broadcast_history'] = []
        await status_msg.edit_text(f"✅ Đã thu hồi {deleted_count} tin nhắn gần nhất.")
    else:
        await msg.reply_text("💡 **HƯỚNG DẪN UNDO:**\nReply (Trả lời) vào tin nhắn bạn muốn xóa rồi gõ `/undo`.")

# ==============================================================================
# 4. MENU XÓA KÊNH & LIST
# ==============================================================================

async def show_delete_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        res = await asyncio.to_thread(requests.get, f"{BROADCAST_DB}.json")
        data = res.json()
        if not data:
            await update.message.reply_text("📭 Danh sách trống.")
            return

        keyboard = []
        for c_id, name in data.items():
            keyboard.append([InlineKeyboardButton(f"❌ {name}", callback_data=f"DEL_ID_{c_id}")])
        keyboard.append([InlineKeyboardButton("🗑 XÓA TẤT CẢ", callback_data="DEL_ALL")])
        keyboard.append([InlineKeyboardButton("Đóng Menu", callback_data="CLOSE_MENU")])

        await update.message.reply_text(f"📋 **QUẢN LÝ XÓA:** ({len(data)} nhóm)", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except: pass

async def handle_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "CLOSE_MENU":
        await query.message.delete()
        return

    if data == "DEL_ALL":
        await asyncio.to_thread(requests.delete, f"{BROADCAST_DB}.json")
        await query.edit_message_text("✅ Đã xóa sạch!")
        return

    if data.startswith("DEL_ID_"):
        chat_id_to_del = data.split("DEL_ID_")[1]
        try:
            await asyncio.to_thread(requests.delete, f"{BROADCAST_DB}/{chat_id_to_del}.json")
            res = await asyncio.to_thread(requests.get, f"{BROADCAST_DB}.json")
            new_data = res.json()
            if not new_data:
                await query.edit_message_text("✅ Đã xóa mục cuối cùng.")
                return
            new_keyboard = []
            for c_id, name in new_data.items():
                new_keyboard.append([InlineKeyboardButton(f"❌ {name}", callback_data=f"DEL_ID_{c_id}")])
            new_keyboard.append([InlineKeyboardButton("🗑 XÓA TẤT CẢ", callback_data="DEL_ALL")])
            new_keyboard.append([InlineKeyboardButton("Đóng Menu", callback_data="CLOSE_MENU")])
            await query.edit_message_text(f"✅ Đã xóa! Còn {len(new_data)} nhóm:", reply_markup=InlineKeyboardMarkup(new_keyboard))
        except: pass

async def list_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private": return
    try:
        res = await asyncio.to_thread(requests.get, f"{BROADCAST_DB}.json")
        data = res.json()
        text = "📋 **DANH SÁCH:**\n" + "\n".join([f"- {name} (`{c_id}`)" for c_id, name in data.items()]) if data else "📭 Trống."
        await update.message.reply_text(text, parse_mode="Markdown")
    except: pass

async def broadcast_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    args = context.args
    if args and args[0].lower() == "on":
        context.user_data['current_mode'] = 'BROADCAST'
        await update.message.reply_text("📡 **ĐÃ BẬT MODE PHÁT SÓNG!**")
        # Mỗi lần bật mode thì tiện tay dọn dẹp data cũ luôn
        asyncio.create_task(clean_old_history())
    elif args and args[0].lower() == "off":
        context.user_data['current_mode'] = None
        await update.message.reply_text("zzz **ĐÃ TẮT MODE PHÁT SÓNG.**")

# ==============================================================================
# 5. XỬ LÝ TIN NHẮN (CORE LOGIC)
# ==============================================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or update.effective_chat.type != "private": return
    mode = context.user_data.get('current_mode')

    # --- MODE TẮT: SETUP KÊNH ---
    if mode != 'BROADCAST':
        if msg.forward_from_chat:
            fwd_chat = msg.forward_from_chat
            try:
                url = f"{BROADCAST_DB}/{fwd_chat.id}.json"
                await asyncio.to_thread(requests.put, url, json=fwd_chat.title or "Kênh")
                await msg.reply_text(f"🎯 Đã thêm: **{fwd_chat.title}**", parse_mode="Markdown")
            except: await msg.reply_text("❌ Lỗi lưu.")
        else:
            await msg.reply_text("💡 **MENU:**\n/bc on - Bật gửi tin\n/delete - Xóa kênh\n/undo - Thu hồi tin (Reply vào tin cần xóa)\n\nHoặc Forward từ kênh vào đây để thêm.")
        return

    # --- MODE BẬT: GỬI TIN & LƯU DB ---
    try:
        res = await asyncio.to_thread(requests.get, f"{BROADCAST_DB}.json")
        targets = res.json()
        if not targets:
            await msg.reply_text("⚠️ Danh sách trống.")
            return
    except: return

    status_msg = await msg.reply_text(f"⏳ Đang Forward đến {len(targets)} nơi...")
    
    sent_log = [] # Lưu danh sách {'chat_id': x, 'msg_id': y}
    success = 0
    fail = 0

    # ID tin nhắn gốc trong bot (Key để lưu vào DB)
    source_msg_id = msg.message_id
    from_chat_id = msg.chat_id

    for target_id in targets.keys():
        try:
            sent_msg = await context.bot.forward_message(
                chat_id=target_id,
                from_chat_id=from_chat_id,
                message_id=msg.message_id
            )
            # Lưu lại ID tin đã gửi
            sent_log.append({
                'chat_id': target_id,
                'msg_id': sent_msg.message_id
            })
            success += 1
            await asyncio.sleep(0.1)
        except:
            fail += 1
    
    # --- LƯU VÀO FIREBASE ĐỂ UNDO SAU NÀY ---
    if sent_log:
        history_entry = {
            "time": int(time.time()), # Lưu thời gian gửi
            "sent_to": sent_log       # Lưu danh sách các nơi đã nhận
        }
        try:
            # Dùng ID tin nhắn gốc làm Key để dễ tìm
            await asyncio.to_thread(requests.put, f"{HISTORY_DB}/{source_msg_id}.json", json=history_entry)
        except Exception as e:
            print(f"Lỗi lưu lịch sử: {e}")

    # Lưu vào RAM để undo nhanh nếu ko reply
    context.user_data['last_broadcast_history'] = sent_log

    await status_msg.edit_text(f"✅ Xong: {success} | ❌ Lỗi: {fail}\n💡 Reply tin nhắn này gõ **/undo** để thu hồi.")

# ==============================================================================
# 6. ĐĂNG KÝ
# ==============================================================================
def register_feature5(app):
    app.add_handler(CommandHandler("add", add_group))
    app.add_handler(CommandHandler("list", list_groups))
    app.add_handler(CommandHandler("bc", broadcast_mode))
    app.add_handler(CommandHandler("delete", show_delete_menu))
    app.add_handler(CommandHandler("undo", undo_broadcast))
    app.add_handler(CallbackQueryHandler(handle_delete_callback, pattern="^(DEL_|CLOSE)"))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message), group=2)
