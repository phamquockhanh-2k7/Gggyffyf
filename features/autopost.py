import asyncio
import requests
import datetime
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, CallbackQueryHandler, filters
import config

# Database URL
DB_URL = f"{config.FIREBASE_URL}/autopost_storage"

# Khởi tạo Scheduler (Lên lịch) - Múi giờ Việt Nam
scheduler = AsyncIOScheduler(timezone=pytz.timezone('Asia/Ho_Chi_Minh'))

# ==============================================================================
# 1. CÁC HÀM XỬ LÝ DATABASE
# ==============================================================================
async def get_storage():
    try:
        res = await asyncio.to_thread(requests.get, f"{DB_URL}.json")
        return res.json() or {}
    except: return {}

async def update_channel_data(chat_id, data):
    await asyncio.to_thread(requests.patch, f"{DB_URL}/{chat_id}.json", json=data)

# ==============================================================================
# 2. QUẢN LÝ KÊNH (THÊM/MENU)
# ==============================================================================

async def handle_add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg.forward_from_chat: return
    
    chat = msg.forward_from_chat
    chat_id = str(chat.id)
    chat_title = chat.title or f"Channel {chat_id}"
    
    current_db = await get_storage()
    
    if chat_id in current_db:
        await msg.reply_text(f"⚠️ Kênh **{chat_title}** đã có trong hệ thống rồi.")
    else:
        # Khởi tạo dữ liệu kênh mới
        new_data = {
            "name": chat_title,
            "limit": 25,       # Mặc định đăng 25 bài/ngày
            "current_index": 0,# Vị trí bắt đầu
            "files": []        # Kho chứa
        }
        await update_channel_data(chat_id, new_data)
        await msg.reply_text(f"✅ Đã thêm kho: **{chat_title}**\nID: `{chat_id}`", parse_mode="Markdown")

async def menu_kho(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage = await get_storage()
    if not storage:
        await update.message.reply_text("📭 Kho trống. Hãy Forward tin từ kênh vào đây để thêm.")
        return

    keyboard = []
    # Tạo nút cho từng kênh
    for cid, data in storage.items():
        name = data.get('name', cid)
        keyboard.append([InlineKeyboardButton(f"📂 {name}", callback_data=f"KHO_SELECT_{cid}")])
    
    keyboard.append([InlineKeyboardButton("❌ Đóng", callback_data="KHO_CLOSE")])
    await update.message.reply_text("🏭 **QUẢN LÝ KHO TÀI NGUYÊN:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ==============================================================================
# 3. XỬ LÝ CALLBACK (NÚT BẤM)
# ==============================================================================
async def handle_kho_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "KHO_CLOSE":
        await query.message.delete()
        context.user_data['autopost_mode'] = None
        return

    # --- CHỌN KÊNH ---
    if data.startswith("KHO_SELECT_"):
        cid = data.split("_")[-1]
        storage = await get_storage()
        if cid not in storage: return await query.edit_message_text("❌ Kênh này không còn tồn tại.")
        
        c_data = storage[cid]
        files = c_data.get('files', []) or []
        total = len(files)
        curr = c_data.get('current_index', 0)
        limit = c_data.get('limit', 25)
        remains = total - curr
        
        status_text = (
            f"📺 **KÊNH:** {c_data.get('name')}\n"
            f"🆔 `{cid}`\n"
            f"📊 **Trạng thái:**\n"
            f"- Tổng kho: {total}\n"
            f"- Đã đăng: {curr}\n"
            f"- Còn lại: **{remains}**\n"
            f"- Limit ngày: **{limit}**\n"
        )
        
        kb = [
            [InlineKeyboardButton("📥 Nạp thêm (Add)", callback_data=f"KHO_ADD_{cid}")],
            [InlineKeyboardButton("⚙️ Chỉnh Limit", callback_data=f"KHO_LIMIT_{cid}"), 
             InlineKeyboardButton("🔄 Reset Index", callback_data=f"KHO_RESET_{cid}")],
            [InlineKeyboardButton("🔙 Quay lại", callback_data="KHO_BACK")]
        ]
        await query.edit_message_text(status_text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif data == "KHO_BACK":
        await query.message.delete()
        await menu_kho(query.message, context)

    # --- CÁC CHỨC NĂNG CON ---
    elif data.startswith("KHO_ADD_"):
        cid = data.split("_")[-1]
        context.user_data['autopost_mode'] = {'action': 'adding', 'channel_id': cid, 'buffer': []}
        await query.edit_message_text(f"📥 **ĐANG MỞ KHO {cid}**\n\nHãy gửi Ảnh/Video vào đây (Gửi bao nhiêu cũng được).\nGõ `/xong` khi hoàn tất.")

    elif data.startswith("KHO_RESET_"):
        cid = data.split("_")[-1]
        await update_channel_data(cid, {"current_index": 0})
        await query.answer("✅ Đã Reset về 0!", show_alert=True)
        # Quay về menu chính
        await menu_kho(query.message, context)

    elif data.startswith("KHO_LIMIT_"):
        cid = data.split("_")[-1]
        context.user_data['autopost_mode'] = {'action': 'setting_limit', 'channel_id': cid}
        await query.edit_message_text(f"⚙️ **Cài đặt số lượng đăng mỗi ngày**\n\nNhập số lượng mới (Ví dụ: 25):")

# ==============================================================================
# 4. XỬ LÝ TIN NHẮN (NẠP FILE & NHẬP SỐ)
# ==============================================================================
async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get('autopost_mode')
    if not mode: 
        # Nếu không ở chế độ nạp, check xem có phải forward thêm kênh không
        if update.message.forward_from_chat:
            await handle_add_channel(update, context)
        return

    msg = update.message
    cid = mode['channel_id']

    # --- XỬ LÝ NẠP FILE ---
    if mode['action'] == 'adding':
        entry = None
        if msg.photo: entry = {"id": msg.photo[-1].file_id, "type": "photo"}
        elif msg.video: entry = {"id": msg.video.file_id, "type": "video"}
        
        if entry:
            mode['buffer'].append(entry)
    
    # --- XỬ LÝ SET LIMIT ---
    elif mode['action'] == 'setting_limit':
        try:
            val = int(msg.text)
            await update_channel_data(cid, {"limit": val})
            await msg.reply_text(f"✅ Đã chỉnh Limit kênh {cid} thành: **{val}** bài/ngày.", parse_mode="Markdown")
            context.user_data['autopost_mode'] = None
        except:
            await msg.reply_text("❌ Vui lòng nhập số nguyên.")

async def command_xong(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get('autopost_mode')
    if not mode or mode['action'] != 'adding': return await update.message.reply_text("⚠️ Bạn không ở trong chế độ nạp kho.")
    
    cid = mode['channel_id']
    new_files = mode['buffer']
    
    if not new_files:
        context.user_data['autopost_mode'] = None
        return await update.message.reply_text("❌ Chưa gửi file nào. Đã hủy.")

    await update.message.reply_text(f"⏳ Đang lưu {len(new_files)} file vào Database...")
    
    # Lấy data cũ rồi append
    try:
        current_data = (await asyncio.to_thread(requests.get, f"{DB_URL}/{cid}.json")).json()
        current_files = current_data.get('files', []) or []
        
        # Thêm mới vào
        updated_files = current_files + new_files
        
        await update_channel_data(cid, {"files": updated_files})
        await update.message.reply_text(f"✅ **NẠP THÀNH CÔNG!**\nTổng kho hiện tại: {len(updated_files)}", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {e}")
    
    context.user_data['autopost_mode'] = None

# ==============================================================================
# 5. LOGIC ĐĂNG BÀI (CORE) & BÁO CÁO
# ==============================================================================

async def check_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage = await get_storage()
    if not storage: return await update.message.reply_text("📭 Không có dữ liệu.")
    
    msg = "📊 **TÌNH TRẠNG KHO:**\n\n"
    for cid, data in storage.items():
        name = data.get('name', cid)
        total = len(data.get('files', []) or [])
        curr = data.get('current_index', 0)
        remains = total - curr
        
        icon = "✅" if remains > 50 else "⚠️"
        msg += f"{icon} **{name}:** {curr}/{total} (Còn {remains})\n"
        
    await update.message.reply_text(msg, parse_mode="Markdown")

async def posting_logic(app):
    """Hàm chạy ngầm để đăng bài lúc 0h"""
    print("⏰ Đang chạy Auto Post...")
    storage = await get_storage()
    if not storage: return

    for cid, data in storage.items():
        files = data.get('files', []) or []
        curr = data.get('current_index', 0)
        limit = data.get('limit', 25)
        name = data.get('name', cid)
        
        # Kiểm tra xem còn hàng không
        if curr >= len(files):
            print(f"❌ {name}: HẾT HÀNG!")
            continue
            
        # Lấy danh sách cần đăng hôm nay
        end_index = min(curr + limit, len(files))
        batch = files[curr : end_index]
        
        # Chia thành các Album nhỏ (Telegram giới hạn 10 item/album)
        chunks = [batch[i:i + 10] for i in range(0, len(batch), 10)]
        
        success_count = 0
        
        for chunk in chunks:
            media_group = []
            for item in chunk:
                if item['type'] == 'photo':
                    media_group.append(InputMediaPhoto(item['id']))
                elif item['type'] == 'video':
                    media_group.append(InputMediaVideo(item['id']))
            
            try:
                if media_group:
                    await app.bot.send_media_group(chat_id=cid, media=media_group)
                    success_count += len(chunk)
                    await asyncio.sleep(5) # Nghỉ 5s giữa các album
            except Exception as e:
                print(f"Lỗi đăng kênh {name}: {e}")
        
        # Cập nhật Index mới
        new_index = curr + success_count
        await update_channel_data(cid, {"current_index": new_index})
        print(f"✅ {name}: Đã đăng {success_count} bài.")

async def send_all_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 Đang kích hoạt đăng bài thủ công...")
    await posting_logic(context.application)
    await update.message.reply_text("✅ Đã chạy xong quy trình đăng bài.")
    await check_status(update, context) 

# ==============================================================================
# 6. SCHEDULER & REGISTER
# ==============================================================================

def register_feature6(app):
    # Lệnh Admin
    app.add_handler(CommandHandler("kho", menu_kho))
    app.add_handler(CommandHandler("xong", command_xong))
    app.add_handler(CommandHandler("check", check_status))
    app.add_handler(CommandHandler("sendall", send_all_command))
    
    # Handler
    app.add_handler(CallbackQueryHandler(handle_kho_callback, pattern="^KHO_"))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_input), group=3)
    
    # Khởi động Scheduler (00:00 mỗi ngày)
    scheduler.add_job(posting_logic, 'cron', hour=0, minute=0, args=[app])
    if not scheduler.running:
        scheduler.start()
