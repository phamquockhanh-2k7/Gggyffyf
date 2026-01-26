# ================================================================================================
# FEATURE6: POSTER BOT ĐĂNG BÀI SỐ LƯỢNG LỚN EVERY DAY , CÁC LỆNH : /KHO , /XONG , /CHECK / SENDALL
# ================================================================================================
import asyncio
import requests
import datetime
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, CallbackQueryHandler, filters
import config

# Database URL
DB_URL = f"{config.FIREBASE_URL}/autopost_storage"
SETTINGS_URL = f"{config.FIREBASE_URL}/autopost_settings"

# Khởi tạo Scheduler (Lên lịch) - Múi giờ Việt Nam
TIMEZONE = pytz.timezone('Asia/Ho_Chi_Minh')
scheduler = AsyncIOScheduler(timezone=TIMEZONE)

# ==============================================================================
# 1. CÁC HÀM XỬ LÝ DATABASE & SCHEDULE
# ==============================================================================
async def get_storage():
    try:
        res = await asyncio.to_thread(requests.get, f"{DB_URL}.json")
        return res.json() or {}
    except: return {}

async def update_channel_data(chat_id, data):
    await asyncio.to_thread(requests.patch, f"{DB_URL}/{chat_id}.json", json=data)

async def get_schedule_time():
    """Lấy giờ đăng từ Firebase, mặc định là 00:00"""
    try:
        res = await asyncio.to_thread(requests.get, f"{SETTINGS_URL}/schedule.json")
        data = res.json()
        if data and 'hour' in data and 'minute' in data:
            return int(data['hour']), int(data['minute'])
        return 0, 0 # Mặc định 0h sáng
    except: return 0, 0

async def save_schedule_time(hour, minute):
    """Lưu giờ đăng vào Firebase"""
    await asyncio.to_thread(requests.put, f"{SETTINGS_URL}/schedule.json", json={"hour": hour, "minute": minute})

def reschedule_job(app, hour, minute):
    """Hàm cập nhật lại lịch chạy mà không cần restart bot"""
    job_id = "daily_autopost"
    
    # Xóa job cũ nếu có
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    
    # Thêm job mới
    scheduler.add_job(
        posting_logic, 
        trigger=CronTrigger(hour=hour, minute=minute, timezone=TIMEZONE), 
        id=job_id, 
        args=[app]
    )
    print(f"⏰ Đã cập nhật lịch đăng bài: {hour:02d}:{minute:02d} hàng ngày.")

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
        new_data = {
            "name": chat_title,
            "limit": 25,       
            "current_index": 0,
            "files": []        
        }
        await update_channel_data(chat_id, new_data)
        await msg.reply_text(f"✅ Đã thêm kho: **{chat_title}**\nID: `{chat_id}`", parse_mode="Markdown")

async def menu_kho(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage = await get_storage()
    if not storage:
        await update.message.reply_text("📭 Kho trống. Hãy Forward tin từ kênh vào đây để thêm.")
        return

    keyboard = []
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

    elif data.startswith("KHO_ADD_"):
        cid = data.split("_")[-1]
        context.user_data['autopost_mode'] = {'action': 'adding', 'channel_id': cid, 'buffer': []}
        await query.edit_message_text(f"📥 **ĐANG MỞ KHO {cid}**\n\nHãy gửi Ảnh/Video vào đây (Gửi bao nhiêu cũng được).\nGõ `/xong` khi hoàn tất.")

    elif data.startswith("KHO_RESET_"):
        cid = data.split("_")[-1]
        await update_channel_data(cid, {"current_index": 0})
        await query.answer("✅ Đã Reset về 0!", show_alert=True)
        await menu_kho(query.message, context)

    elif data.startswith("KHO_LIMIT_"):
        cid = data.split("_")[-1]
        context.user_data['autopost_mode'] = {'action': 'setting_limit', 'channel_id': cid}
        await query.edit_message_text(f"⚙️ **Cài đặt số lượng đăng mỗi ngày**\n\nNhập số lượng mới (Ví dụ: 25):")

# ==============================================================================
# 4. CÀI ĐẶT LỊCH TRÌNH (/SETSCHEDULE)
# ==============================================================================
async def command_setschedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bắt đầu quy trình cài đặt giờ"""
    context.user_data['autopost_mode'] = {'action': 'set_hour'}
    await update.message.reply_text("🕒 **CÀI ĐẶT GIỜ ĐĂNG BÀI**\n\nVui lòng nhập **GIỜ** (0 - 23):", parse_mode="Markdown")

# ==============================================================================
# 5. XỬ LÝ TIN NHẮN (LOGIC CHÍNH CỦA INPUT)
# ==============================================================================
async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get('autopost_mode')
    
    # Nếu không có mode, check forward kênh
    if not mode: 
        if update.message.forward_from_chat:
            await handle_add_channel(update, context)
        return

    msg = update.message
    
    # --- LOGIC CÀI ĐẶT GIỜ (/setschedule) ---
    if mode['action'] == 'set_hour':
        try:
            h = int(msg.text)
            if 0 <= h <= 23:
                mode['hour'] = h
                mode['action'] = 'set_minute' # Chuyển sang bước nhập phút
                await msg.reply_text(f"✅ Giờ: {h}\n\nTiếp tục nhập **PHÚT** (0 - 59):")
            else:
                await msg.reply_text("❌ Giờ phải từ 0 đến 23. Nhập lại:")
        except: await msg.reply_text("❌ Vui lòng nhập số.")
        return

    elif mode['action'] == 'set_minute':
        try:
            m = int(msg.text)
            if 0 <= m <= 59:
                h = mode['hour']
                # 1. Lưu vào Database
                await save_schedule_time(h, m)
                # 2. Cập nhật Scheduler ngay lập tức
                reschedule_job(context.application, h, m)
                
                await msg.reply_text(f"✅ **ĐÃ LƯU!**\nBot sẽ tự động đăng bài vào lúc **{h:02d}:{m:02d}** hàng ngày.", parse_mode="Markdown")
                context.user_data['autopost_mode'] = None
            else:
                await msg.reply_text("❌ Phút phải từ 0 đến 59. Nhập lại:")
        except: await msg.reply_text("❌ Vui lòng nhập số.")
        return

    # --- LOGIC NẠP FILE & LIMIT ---
    cid = mode.get('channel_id')
    
    if mode['action'] == 'adding':
        entry = None
        if msg.photo: entry = {"id": msg.photo[-1].file_id, "type": "photo"}
        elif msg.video: entry = {"id": msg.video.file_id, "type": "video"}
        if entry:
            mode['buffer'].append(entry)
    
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
    try:
        current_data = (await asyncio.to_thread(requests.get, f"{DB_URL}/{cid}.json")).json()
        current_files = current_data.get('files', []) or []
        updated_files = current_files + new_files
        await update_channel_data(cid, {"files": updated_files})
        await update.message.reply_text(f"✅ **NẠP THÀNH CÔNG!**\nTổng kho hiện tại: {len(updated_files)}", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {e}")
    context.user_data['autopost_mode'] = None

# ==============================================================================
# 6. LOGIC ĐĂNG BÀI (CORE) & BÁO CÁO
# ==============================================================================

async def check_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage = await get_storage()
    if not storage: return await update.message.reply_text("📭 Không có dữ liệu.")
    
    # Lấy giờ lịch trình hiện tại để báo cáo
    h, m = await get_schedule_time()
    
    msg = f"⏰ **LỊCH TRÌNH:** {h:02d}:{m:02d} hàng ngày.\n\n📊 **TÌNH TRẠNG KHO:**\n\n"
    for cid, data in storage.items():
        name = data.get('name', cid)
        total = len(data.get('files', []) or [])
        curr = data.get('current_index', 0)
        remains = total - curr
        icon = "✅" if remains > 50 else "⚠️"
        msg += f"{icon} **{name}:** {curr}/{total} (Còn {remains})\n"
        
    await update.message.reply_text(msg, parse_mode="Markdown")

async def posting_logic(app):
    """Hàm chạy ngầm để đăng bài"""
    print("⏰ Đang chạy Auto Post...")
    storage = await get_storage()
    if not storage: return

    for cid, data in storage.items():
        files = data.get('files', []) or []
        curr = data.get('current_index', 0)
        limit = data.get('limit', 25)
        name = data.get('name', cid)
        
        if curr >= len(files):
            print(f"❌ {name}: HẾT HÀNG!")
            continue
            
        end_index = min(curr + limit, len(files))
        batch = files[curr : end_index]
        chunks = [batch[i:i + 10] for i in range(0, len(batch), 10)]
        
        success_count = 0
        for chunk in chunks:
            media_group = []
            for item in chunk:
                if item['type'] == 'photo': media_group.append(InputMediaPhoto(item['id']))
                elif item['type'] == 'video': media_group.append(InputMediaVideo(item['id']))
            try:
                if media_group:
                    await app.bot.send_media_group(chat_id=cid, media=media_group)
                    success_count += len(chunk)
                    await asyncio.sleep(5)
            except Exception as e:
                print(f"Lỗi đăng kênh {name}: {e}")
        
        new_index = curr + success_count
        await update_channel_data(cid, {"current_index": new_index})
        print(f"✅ {name}: Đã đăng {success_count} bài.")

async def send_all_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 Đang kích hoạt đăng bài thủ công...")
    await posting_logic(context.application)
    await update.message.reply_text("✅ Đã chạy xong quy trình đăng bài.")
    await check_status(update, context) 

# ==============================================================================
# 7. KHỞI TẠO & ĐĂNG KÝ
# ==============================================================================

async def init_scheduler_from_db(context: ContextTypes.DEFAULT_TYPE):
    """Chạy 1 lần khi bot khởi động để lấy giờ từ DB"""
    h, m = await get_schedule_time()
    reschedule_job(context.application, h, m)
    print(f"♻️ Đã khôi phục lịch trình: {h:02d}:{m:02d}")

def register_feature6(app):
    # Lệnh Admin
    app.add_handler(CommandHandler("kho", menu_kho))
    app.add_handler(CommandHandler("xong", command_xong))
    app.add_handler(CommandHandler("check", check_status))
    app.add_handler(CommandHandler("sendall", send_all_command))
    app.add_handler(CommandHandler("setschedule", command_setschedule)) # <--- Lệnh mới
    
    # Handler
    app.add_handler(CallbackQueryHandler(handle_kho_callback, pattern="^KHO_"))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_input), group=3)
    
    # Khởi động Scheduler
    if not scheduler.running:
        scheduler.start()
        
    # Đặt một tác vụ chạy sau 1 giây để load giờ từ DB
    app.job_queue.run_once(init_scheduler_from_db, 1)
