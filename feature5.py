import asyncio
import requests
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# ==============================================================================
# 🔐 CẤU HÌNH BẢO MẬT (SYSTEM LOCK)
# ==============================================================================
# Mặc định là False (Bot ngủ/Phế). 
# Khi nào gõ /activeforadmin mới thành True.
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
# 0. HỆ THỐNG KÍCH HOẠT (QUAN TRỌNG NHẤT)
# ==============================================================================

async def active_system(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh đánh thức Bot: /activeforadmin"""
    global IS_SYSTEM_ACTIVE
    IS_SYSTEM_ACTIVE = True
    # Phản hồi nhẹ để bạn biết là nó đã tỉnh
    await update.message.reply_text("🔓 **SYSTEM UNLOCKED!**\nBot đã tỉnh. Giờ bạn có thể dùng mọi tính năng.", parse_mode="Markdown")

async def lock_system(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh khóa Bot: /lockbot"""
    global IS_SYSTEM_ACTIVE
    IS_SYSTEM_ACTIVE = False
    await update.message.reply_text("🔒 **SYSTEM LOCKED!**\nBot đã ngủ. (Phế 100%)", parse_mode="Markdown")

# ==============================================================================
# 1. CÁC TÍNH NĂNG CŨ (ĐÃ THÊM CHECK BẢO MẬT)
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
    if not IS_SYSTEM_ACTIVE: return # ⛔ NẾU CHƯA KÍCH HOẠT THÌ CÂM
    
    msg = update.effective_message
    
    # --- LOGIC UNDO ---
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

async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not IS_SYSTEM_ACTIVE: return # ⛔ BẢO MẬT
    
    msg = update.effective_message
    if not msg: return
    if update.effective_chat.type == "private":
        await msg.reply_text("❌ Dùng trong Nhóm hoặc Forward bài từ Kênh vào đây.")
        return
    try:
        await asyncio.to_thread(requests.put, f"{BROADCAST_DB}/{update.effective_chat.id}.json", json=update.effective_chat.title or "Group")
        await msg.reply_text(f"✅ Đã thêm!", parse_mode="Markdown")
    except: pass

async def show_delete_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not IS_SYSTEM_ACTIVE: return # ⛔ BẢO MẬT
    
    try:
        res = await asyncio.to_thread(requests.get, f"{BROADCAST_DB}.json")
        data = res.json()
        if not data: return await update.message.reply_text("📭 Trống.")
        keyboard = [[InlineKeyboardButton(f"❌ {name}", callback_data=f"DEL_ID_{c_id}")] for c_id, name in data.items()]
        keyboard.append([InlineKeyboardButton("🗑 XÓA TẤT CẢ", callback_data="DEL_ALL"), InlineKeyboardButton("Đóng", callback_data="CLOSE_MENU")])
        await update.message.reply_text(f"📋 Xóa:", reply_markup=InlineKeyboardMarkup(keyboard))
    except: pass

async def handle_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not IS_SYSTEM_ACTIVE: return # ⛔ BẢO MẬT
    
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
    if not IS_SYSTEM_ACTIVE: return # ⛔ BẢO MẬT
    
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
# 2. XỬ LÝ GỬI TIN & ALBUM
# ==============================================================================

async def process_album_later(media_group_id, context, from_chat_id):
    await asyncio.sleep(4) # Chờ 4s cho an toàn
    if media_group_id not in ALBUM_BUFFER: return 
    
    msg_ids = sorted(ALBUM_BUFFER[media_group_id])
    del ALBUM_BUFFER[media_group_id]
    
    try:
        res = await asyncio.to_thread(requests.get, f"{BROADCAST_DB}.json")
        targets = res.json()
    except: targets = {}
    if not targets: return

    sent_log_for_undo = []
    
    for target_id in targets.keys():
        try:
            forwarded_msgs = await context.bot.forward_messages(
                chat_id=target_id,
                from_chat_id=from_chat_id,
                message_ids=msg_ids
            )
            new_ids = [m.message_id for m in forwarded_msgs]
            sent_log_for_undo.append({'chat_id': target_id, 'msg_ids': new_ids})
        except Exception as e:
            print(f"Lỗi gửi album: {e}")

    history_entry = {"time": int(time.time()), "sent_to": sent_log_for_undo}
    for source_id in msg_ids:
        try:
            await asyncio.to_thread(requests.put, f"{HISTORY_DB}/{source_id}.json", json=history_entry)
        except: pass

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ⛔ BẢO MẬT TUYỆT ĐỐI: NẾU CHƯA ACTIVE THÌ RETURN LUÔN
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
            await msg.reply_text("💡 **MENU:**\n/bc on - Bật\n/delete - Xóa kênh\n/undo - Thu hồi\n/lockbot - Khóa Bot\nForward từ kênh vào đây để thêm.")
        return

    # XỬ LÝ GỬI
    if msg.media_group_id:
        group_id = msg.media_group_id
        if group_id not in ALBUM_BUFFER:
            ALBUM_BUFFER[group_id] = []
            asyncio.create_task(process_album_later(group_id, context, msg.chat_id))
        ALBUM_BUFFER[group_id].append(msg.message_id)
        return
    
    try:
        res = await asyncio.to_thread(requests.get, f"{BROADCAST_DB}.json")
        targets = res.json()
    except: targets = {}
    if not targets: return await msg.reply_text("⚠️ List trống.")
    
    status_msg = await msg.reply_text(f"🚀 Đang gửi...")
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

    await status_msg.edit_text("✅ Xong tin lẻ.")

# ==============================================================================
# 3. ĐĂNG KÝ (ĐÃ THÊM LỆNH MỚI)
# ==============================================================================
def register_feature5(app):
    # Lệnh mở khóa (Chạy được kể cả khi bot đang ngủ)
    app.add_handler(CommandHandler("activeforadmin", active_system))
    
    # Lệnh khóa lại
    app.add_handler(CommandHandler("lockbot", lock_system))

    # Các lệnh chức năng (Bên trong đã có check IS_SYSTEM_ACTIVE)
    app.add_handler(CommandHandler("add", add_group))
    app.add_handler(CommandHandler("bc", broadcast_mode))
    app.add_handler(CommandHandler("delete", show_delete_menu))
    app.add_handler(CommandHandler("undo", undo_broadcast))
    app.add_handler(CallbackQueryHandler(handle_delete_callback, pattern="^(DEL_|CLOSE)"))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message), group=2)
