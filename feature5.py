import asyncio
import requests
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# ==============================================================================
# ⚙️ CẤU HÌNH DATABASE & BUFFER
# ==============================================================================
BASE_URL = "https://bot-telegram-99852-default-rtdb.firebaseio.com"
BROADCAST_DB = f"{BASE_URL}/broadcast_channels"
HISTORY_DB = f"{BASE_URL}/broadcast_history"
RETENTION_PERIOD = 259200 # 3 ngày

# 📦 BỘ NHỚ ĐỆM ĐỂ GOM ALBUM
# Cấu trúc: { 'media_group_id': [msg_id_1, msg_id_2, ...] }
ALBUM_BUFFER = {}

# ==============================================================================
# 1. HÀM PHỤ TRỢ (DỌN DẸP & UNDO)
# ==============================================================================

async def clean_old_history():
    """Xóa lịch sử cũ quá 3 ngày"""
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
    msg = update.effective_message
    
    # --- LOGIC TÌM DỮ LIỆU CẦN XÓA ---
    target_data = None
    
    # Cách 1: Reply vào tin nhắn
    if msg.reply_to_message:
        reply_id = str(msg.reply_to_message.message_id)
        # Tìm xem tin này có trong DB không
        try:
            res = await asyncio.to_thread(requests.get, f"{HISTORY_DB}/{reply_id}.json")
            target_data = res.json()
            # Nếu tìm thấy, xóa luôn bản ghi trong DB
            if target_data:
                await asyncio.to_thread(requests.delete, f"{HISTORY_DB}/{reply_id}.json")
        except: pass
    
    # Cách 2: Lấy cái mới nhất trong RAM
    elif context.user_data.get('last_broadcast_history'):
        target_data = {'sent_to': context.user_data.get('last_broadcast_history')}
        context.user_data['last_broadcast_history'] = [] # Xóa RAM
    
    # --- THỰC HIỆN XÓA ---
    if not target_data:
        await msg.reply_text("⚠️ Không tìm thấy dữ liệu để thu hồi (Hoặc đã quá hạn). Hãy Reply vào tin nhắn gốc.")
        return

    status_msg = await msg.reply_text("🗑 Đang thu hồi...")
    deleted_count = 0
    
    # sent_to bây giờ là danh sách các gói tin. 
    # Mỗi gói tin có thể chứa nhiều msg_ids (nếu là album)
    # Cấu trúc sent_to: [ {'chat_id': 123, 'msg_ids': [1, 2, 3]}, ... ]
    
    sent_list = target_data.get('sent_to', [])
    for item in sent_list:
        chat_id = item['chat_id']
        msg_ids = item['msg_ids'] # Đây là 1 list các ID (vì là album)
        
        for mid in msg_ids:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=mid)
                deleted_count += 1
            except: pass
            
    await status_msg.edit_text(f"✅ Đã thu hồi {deleted_count} tin nhắn/ảnh thành công!")

# ==============================================================================
# 2. CÁC HÀM QUẢN LÝ (ADD/DELETE/BC...) - GIỮ NGUYÊN
# ==============================================================================

async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg: return
    if update.effective_chat.type == "private":
        await msg.reply_text("❌ Lệnh này dùng trong Nhóm. Với Kênh, hãy Forward bài vào đây.")
        return
    try:
        await asyncio.to_thread(requests.put, f"{BROADCAST_DB}/{update.effective_chat.id}.json", json=update.effective_chat.title or "Group")
        await msg.reply_text(f"✅ Đã thêm!", parse_mode="Markdown")
    except: pass

async def show_delete_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        res = await asyncio.to_thread(requests.get, f"{BROADCAST_DB}.json")
        data = res.json()
        if not data: return await update.message.reply_text("📭 Trống.")
        keyboard = [[InlineKeyboardButton(f"❌ {name}", callback_data=f"DEL_ID_{c_id}")] for c_id, name in data.items()]
        keyboard.append([InlineKeyboardButton("🗑 XÓA TẤT CẢ", callback_data="DEL_ALL"), InlineKeyboardButton("Đóng", callback_data="CLOSE_MENU")])
        await update.message.reply_text(f"📋 Xóa:", reply_markup=InlineKeyboardMarkup(keyboard))
    except: pass

async def handle_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    if not update.message: return
    args = context.args
    if args and args[0].lower() == "on":
        context.user_data['current_mode'] = 'BROADCAST'
        await update.message.reply_text("📡 **ĐÃ BẬT MODE PHÁT SÓNG (Hỗ trợ Album)!**")
        asyncio.create_task(clean_old_history())
    elif args and args[0].lower() == "off":
        context.user_data['current_mode'] = None
        await update.message.reply_text("zzz **ĐÃ TẮT.**")

# ==============================================================================
# 3. XỬ LÝ GỬI TIN (LOGIC GOM ALBUM)
# ==============================================================================

async def process_album_later(media_group_id, context, from_chat_id):
    """Hàm chạy sau 2s để gửi cả chùm album"""
    await asyncio.sleep(4) # Chờ 2 giây để gom đủ ảnh
    
    if media_group_id not in ALBUM_BUFFER: return # Đã xử lý rồi thì thôi
    
    # Lấy danh sách msg_id trong album và sắp xếp
    msg_ids = sorted(ALBUM_BUFFER[media_group_id])
    del ALBUM_BUFFER[media_group_id] # Xóa khỏi bộ nhớ đệm
    
    # Lấy danh sách đích
    try:
        res = await asyncio.to_thread(requests.get, f"{BROADCAST_DB}.json")
        targets = res.json()
    except: targets = {}
    
    if not targets: return

    # --- BẮT ĐẦU GỬI ---
    sent_log_for_undo = [] # Log để Undo
    
    for target_id in targets.keys():
        try:
            # 🔥 QUAN TRỌNG: Dùng forward_messages (số nhiều) để gửi cả chùm
            forwarded_msgs = await context.bot.forward_messages(
                chat_id=target_id,
                from_chat_id=from_chat_id,
                message_ids=msg_ids
            )
            
            # Lưu lại ID của các tin nhắn mới gửi bên đích
            new_ids = [m.message_id for m in forwarded_msgs]
            
            sent_log_for_undo.append({
                'chat_id': target_id,
                'msg_ids': new_ids 
            })
        except Exception as e:
            print(f"Lỗi gửi album đến {target_id}: {e}")

    # --- LƯU LỊCH SỬ UNDO CHO TẤT CẢ ẢNH TRONG ALBUM ---
    # Để user reply vào ảnh nào trong album gốc cũng undo được
    history_entry = {
        "time": int(time.time()),
        "sent_to": sent_log_for_undo
    }
    
    # Map từng ID gốc vào cùng 1 bản ghi lịch sử
    for source_id in msg_ids:
        try:
            url = f"{HISTORY_DB}/{source_id}.json"
            await asyncio.to_thread(requests.put, url, json=history_entry)
        except: pass

    # Lưu RAM cái cuối cùng
    # (Vì chạy ngầm nên ta không access được context.user_data của user main thread dễ dàng, 
    # nhưng tính năng reply undo vẫn hoạt động tốt nhờ Firebase)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or update.effective_chat.type != "private": return
    mode = context.user_data.get('current_mode')

    # --- MODE TẮT ---
    if mode != 'BROADCAST':
        if msg.forward_from_chat:
            fwd_chat = msg.forward_from_chat
            try:
                url = f"{BROADCAST_DB}/{fwd_chat.id}.json"
                await asyncio.to_thread(requests.put, url, json=fwd_chat.title or "Kênh")
                await msg.reply_text(f"🎯 Thêm: **{fwd_chat.title}**", parse_mode="Markdown")
            except: pass
        else:
            await msg.reply_text("💡 **MENU:**\n/bc on - Bật\n/delete - Xóa kênh\n/undo - Thu hồi\nHoặc Forward từ kênh vào đây để thêm.")
        return

    # --- MODE BẬT: XỬ LÝ ALBUM HOẶC TIN LẺ ---
    
    # 1. KIỂM TRA CÓ PHẢI ALBUM KHÔNG?
    if msg.media_group_id:
        group_id = msg.media_group_id
        
        # Nếu chưa có trong buffer, tạo mới và hẹn giờ gửi
        if group_id not in ALBUM_BUFFER:
            ALBUM_BUFFER[group_id] = []
            asyncio.create_task(process_album_later(group_id, context, msg.chat_id))
        
        # Thêm msg_id vào buffer
        ALBUM_BUFFER[group_id].append(msg.message_id)
        return # Dừng ở đây, đợi đủ bộ rồi hàm process_album_later sẽ gửi
    
    # 2. XỬ LÝ TIN LẺ (KHÔNG PHẢI ALBUM) - GỬI LUÔN
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
            sent_log.append({
                'chat_id': target_id,
                'msg_ids': [sent_msg.message_id] # Lưu dạng list để đồng bộ format với album
            })
        except: pass
    
    # Lưu lịch sử
    if sent_log:
        entry = {"time": int(time.time()), "sent_to": sent_log}
        await asyncio.to_thread(requests.put, f"{HISTORY_DB}/{msg.message_id}.json", json=entry)
        context.user_data['last_broadcast_history'] = sent_log

    await status_msg.edit_text("✅ Xong tin lẻ.")

# ==============================================================================
# 4. ĐĂNG KÝ
# ==============================================================================
def register_feature5(app):
    app.add_handler(CommandHandler("add", add_group))
    app.add_handler(CommandHandler("bc", broadcast_mode))
    app.add_handler(CommandHandler("delete", show_delete_menu))
    app.add_handler(CommandHandler("undo", undo_broadcast))
    app.add_handler(CallbackQueryHandler(handle_delete_callback, pattern="^(DEL_|CLOSE)"))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message), group=2)
