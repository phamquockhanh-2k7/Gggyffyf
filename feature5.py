import asyncio
import requests
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# ==============================================================================
# 🔐 CẤU HÌNH BẢO MẬT (SYSTEM LOCK)
# ==============================================================================
IS_SYSTEM_ACTIVE = False 

# ==============================================================================
# ⚙️ CẤU HÌNH DATABASE
# ==============================================================================
BASE_URL = "https://bot-telegram-99852-default-rtdb.firebaseio.com"
BROADCAST_DB = f"{BASE_URL}/broadcast_channels"
HISTORY_DB = f"{BASE_URL}/broadcast_history"
RETENTION_PERIOD = 259200 
ALBUM_BUFFER = {}

# ==============================================================================
# 0. HỆ THỐNG KÍCH HOẠT
# ==============================================================================

async def active_system(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global IS_SYSTEM_ACTIVE
    IS_SYSTEM_ACTIVE = True
    await update.message.reply_text("🔓 **SYSTEM UNLOCKED!**\nBot đã tỉnh.", parse_mode="Markdown")

async def lock_system(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global IS_SYSTEM_ACTIVE
    IS_SYSTEM_ACTIVE = False
    await update.message.reply_text("🔒 **SYSTEM LOCKED!**\nBot đã ngủ.", parse_mode="Markdown")

# ==============================================================================
# 1. HÀM PHỤ TRỢ (DỌN DẸP & UNDO)
# ==============================================================================

async def clean_old_history():
    try:
        res = await asyncio.to_thread(requests.get, f"{HISTORY_DB}.json")
        data = res.json()
        if not data: return
        current_time = int(time.time())
        for key, content in data.items():
            if current_time - content.get('time', 0) > RETENTION_PERIOD:
                await asyncio.to_thread(requests.delete, f"{HISTORY_DB}/{key}.json")
    except: pass

async def undo_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not IS_SYSTEM_ACTIVE: return
    msg = update.effective_message
    
    target_data = None
    if msg.reply_to_message:
        reply_id = str(msg.reply_to_message.message_id)
        try:
            res = await asyncio.to_thread(requests.get, f"{HISTORY_DB}/{reply_id}.json")
            target_data = res.json()
            if target_data:
                await asyncio.to_thread(requests.delete, f"{HISTORY_DB}/{reply_id}.json")
        except: pass
    elif context.user_data.get('last_broadcast_history'):
        target_data = {'sent_to': context.user_data.get('last_broadcast_history')}
        context.user_data['last_broadcast_history'] = [] 
    
    if not target_data:
        await msg.reply_text("⚠️ Không tìm thấy dữ liệu để thu hồi.")
        return

    status_msg = await msg.reply_text("🗑 Đang thu hồi...")
    deleted_count = 0
    sent_list = target_data.get('sent_to', [])
    for item in sent_list:
        chat_id = item['chat_id']
        msg_ids = item['msg_ids']
        for mid in msg_ids:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=mid)
                deleted_count += 1
            except: pass
            
    await status_msg.edit_text(f"✅ Đã thu hồi {deleted_count} tin nhắn!")

# ==============================================================================
# 2. QUẢN LÝ NHÓM & MENU
# ==============================================================================

async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not IS_SYSTEM_ACTIVE: return
    msg = update.effective_message
    if not msg: return
    if update.effective_chat.type == "private":
        await msg.reply_text("❌ Forward bài từ Kênh vào đây để thêm.")
        return
    try:
        await asyncio.to_thread(requests.put, f"{BROADCAST_DB}/{update.effective_chat.id}.json", json=update.effective_chat.title or "Group")
        await msg.reply_text(f"✅ Đã thêm!", parse_mode="Markdown")
    except: pass

async def show_delete_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not IS_SYSTEM_ACTIVE: return
    try:
        res = await asyncio.to_thread(requests.get, f"{BROADCAST_DB}.json")
        data = res.json()
        if not data: return await update.message.reply_text("📭 Trống.")
        keyboard = [[InlineKeyboardButton(f"❌ {name}", callback_data=f"DEL_ID_{c_id}")] for c_id, name in data.items()]
        keyboard.append([InlineKeyboardButton("🗑 XÓA TẤT CẢ", callback_data="DEL_ALL"), InlineKeyboardButton("Đóng", callback_data="CLOSE_MENU")])
        await update.message.reply_text(f"📋 Xóa:", reply_markup=InlineKeyboardMarkup(keyboard))
    except: pass

async def handle_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not IS_SYSTEM_ACTIVE: return
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "CLOSE_MENU": return await query.message.delete()
    if data == "DEL_ALL":
        await asyncio.to_thread(requests.delete, f"{BROADCAST_DB}.json")
        return await query.edit_message_text("✅ Đã xóa hết.")
    if data.startswith("DEL_ID_"):
        cid = data.split("DEL_ID_")[1]
        await asyncio.to_thread(requests.delete, f"{BROADCAST_DB}/{cid}.json")
        await query.edit_message_text("✅ Đã xóa.")

async def broadcast_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not IS_SYSTEM_ACTIVE: return
    if not update.message: return
    args = context.args
    if args and args[0].lower() == "on":
        context.user_data['current_mode'] = 'BROADCAST'
        await update.message.reply_text("📡 **ĐÃ BẬT MODE PHÁT SÓNG!**")
        asyncio.create_task(clean_old_history())
    elif args and args[0].lower() == "off":
        context.user_data['current_mode'] = None
        await update.message.reply_text("zzz **ĐÃ TẮT.**")

# ==============================================================================
# 3. XỬ LÝ GỬI TIN & ALBUM (ĐÃ SỬA LỖI IM LẶNG)
# ==============================================================================

async def process_album_later(media_group_id, context, from_chat_id):
    """Xử lý gửi album và BÁO CÁO lại cho admin"""
    await asyncio.sleep(4) 
    
    if media_group_id not in ALBUM_BUFFER: return 
    
    # Lấy danh sách ảnh
    msg_ids = sorted(ALBUM_BUFFER[media_group_id])
    del ALBUM_BUFFER[media_group_id]
    
    # Lấy danh sách đích
    try:
        res = await asyncio.to_thread(requests.get, f"{BROADCAST_DB}.json")
        targets = res.json()
    except: targets = {}
    
    if not targets: return

    sent_log_for_undo = []
    success_count = 0
    fail_count = 0
    
    # Gửi đi
    for target_id in targets.keys():
        try:
            forwarded_msgs = await context.bot.forward_messages(
                chat_id=target_id,
                from_chat_id=from_chat_id,
                message_ids=msg_ids
            )
            new_ids = [m.message_id for m in forwarded_msgs]
            sent_log_for_undo.append({'chat_id': target_id, 'msg_ids': new_ids})
            success_count += 1
        except Exception as e:
            print(f"Lỗi gửi album: {e}")
            fail_count += 1

    # Lưu lịch sử Undo
    history_entry = {"time": int(time.time()), "sent_to": sent_log_for_undo}
    for source_id in msg_ids:
        try:
            await asyncio.to_thread(requests.put, f"{HISTORY_DB}/{source_id}.json", json=history_entry)
        except: pass

    # 👇 ĐÂY LÀ PHẦN MỚI THÊM: Gửi thông báo về cho Admin sau khi xong
    try:
        await context.bot.send_message(
            chat_id=from_chat_id,
            text=f"✅ **Đã gửi Album ({len(msg_ids)} ảnh/video):**\n- Thành công: {success_count} nhóm\n- Thất bại: {fail_count} nhóm",
            parse_mode="Markdown"
        )
    except: pass

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not IS_SYSTEM_ACTIVE: return 
    msg = update.effective_message
    if not msg or update.effective_chat.type != "private": return
    mode = context.user_data.get('current_mode')

    if mode != 'BROADCAST':
        if msg.forward_from_chat:
            fwd_chat = msg.forward_from_chat
            try:
                url = f"{BROADCAST_DB}/{fwd_chat.id}.json"
                await asyncio.to_thread(requests.put, url, json=fwd_chat.title or "Kênh")
                await msg.reply_text(f"🎯 Thêm: **{fwd_chat.title}**", parse_mode="Markdown")
            except: pass
        else:
            await msg.reply_text("💡 **MENU:**\n/bc on - Bật\n/delete - Xóa kênh\n/undo - Thu hồi\n/lockbot - Khóa Bot")
        return

    # --- XỬ LÝ GỬI ALBUM ---
    if msg.media_group_id:
        group_id = msg.media_group_id
        
        # Nếu là ảnh đầu tiên của Album -> Tạo buffer và BÁO HIỆU
        if group_id not in ALBUM_BUFFER:
            ALBUM_BUFFER[group_id] = []
            asyncio.create_task(process_album_later(group_id, context, msg.chat_id))
            # 👇 Báo cho bạn biết là bot đã nhận được album
            await msg.reply_text("⏳ Đang gom Album, vui lòng đợi 4s...")
        
        ALBUM_BUFFER[group_id].append(msg.message_id)
        return
    
    # --- XỬ LÝ GỬI TIN LẺ ---
    try:
        res = await asyncio.to_thread(requests.get, f"{BROADCAST_DB}.json")
        targets = res.json()
    except: targets = {}
    if not targets: return await msg.reply_text("⚠️ List trống.")
    
    status_msg = await msg.reply_text(f"🚀 Đang gửi tin lẻ...")
    sent_log = []
    
    for target_id in targets.keys():
        try:
            sent_msg = await context.bot.forward_message(
                chat_id=target_id,
                from_chat_id=msg.chat_id,
                message_id=msg.message_id
            )
            sent_log.append({'chat_id': target_id, 'msg_ids': [sent_msg.message_id]})
        except: pass
    
    if sent_log:
        entry = {"time": int(time.time()), "sent_to": sent_log}
        await asyncio.to_thread(requests.put, f"{HISTORY_DB}/{msg.message_id}.json", json=entry)
        context.user_data['last_broadcast_history'] = sent_log

    await status_msg.edit_text(f"✅ Xong tin lẻ (Gửi đến {len(sent_log)} nơi).")

# ==============================================================================
# 4. ĐĂNG KÝ
# ==============================================================================
def register_feature5(app):
    app.add_handler(CommandHandler("activeforadmin", active_system))
    app.add_handler(CommandHandler("lockbot", lock_system))
    app.add_handler(CommandHandler("add", add_group))
    app.add_handler(CommandHandler("bc", broadcast_mode))
    app.add_handler(CommandHandler("delete", show_delete_menu))
    app.add_handler(CommandHandler("undo", undo_broadcast))
    app.add_handler(CallbackQueryHandler(handle_delete_callback, pattern="^(DEL_|CLOSE)"))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message), group=2)
