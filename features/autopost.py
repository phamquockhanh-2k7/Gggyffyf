# ================================================================================================
# FEATURE6: POSTER BOT (CÓ CÔNG TẮC BẬT/TẮT: /activenow, /turnoff)
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

import db


# Khởi tạo Scheduler (Lên lịch) - Múi giờ Việt Nam
TIMEZONE = pytz.timezone('Asia/Ho_Chi_Minh')
scheduler = AsyncIOScheduler(timezone=TIMEZONE)

# Bộ nhớ đệm (Cache) danh sách người dùng đã kích hoạt
ACTIVE_USERS_CACHE = set()

# ==============================================================================
# 0. HỆ THỐNG BẢO MẬT (CÔNG TẮC)
# ==============================================================================
async def load_active_users():
    global ACTIVE_USERS_CACHE
    try:
        data = await db.get_autopost_users()
        if data:
            ACTIVE_USERS_CACHE = set(str(k) for k, active in data.items() if active)
        print(f"🛡 Đã tải {len(ACTIVE_USERS_CACHE)} người dùng kích hoạt.")
    except: pass

async def check_active(user_id):
    return str(user_id) in ACTIVE_USERS_CACHE

async def command_activenow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid in ACTIVE_USERS_CACHE:
        return await update.message.reply_text("✅ Bot đã được BẬT từ trước rồi.")
    try:
        await db.update_autopost_users({uid: True})
        ACTIVE_USERS_CACHE.add(uid)
        await update.message.reply_text("🔓 **ĐÃ BẬT BOT!**\nBây giờ bạn có thể sử dụng các lệnh.", parse_mode="Markdown")
    except: await update.message.reply_text("❌ Lỗi mạng.")

async def command_turnoff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid not in ACTIVE_USERS_CACHE: return 
    try:
        await db.update_autopost_users({uid: False})
        ACTIVE_USERS_CACHE.discard(uid)
        await update.message.reply_text("📴 **ĐÃ TẮT BOT!**\nTạm biệt.", parse_mode="Markdown")
    except: pass

# ==============================================================================
# 1. CÁC HÀM XỬ LÝ DATABASE & SCHEDULE
# ==============================================================================
async def get_storage():
    try: return await db.get_autopost_storage()
    except: return {}

async def update_channel_data(chat_id, data):
    await db.update_autopost_storage(chat_id, data)

async def delete_channel_data(chat_id):
    await db.delete_autopost_storage(chat_id)

async def get_schedule_time():
    try:
        # Assuming channel_id 0 serves as a global setting if there are multiple, or just take the first
        data = await db.get_autopost_settings()
        if data and "0" in data:
            return int(data["0"]['hour']), int(data["0"]['minute'])
        return 0, 0 
    except: return 0, 0

async def save_schedule_time(hour, minute):
    await db.update_autopost_settings(0, hour, minute)

def reschedule_job(app, hour, minute):
    job_id = "daily_autopost"
    if scheduler.get_job(job_id): scheduler.remove_job(job_id)
    scheduler.add_job(posting_logic, trigger=CronTrigger(hour=hour, minute=minute, timezone=TIMEZONE), id=job_id, args=[app])
    print(f"⏰ Lịch trình: {hour:02d}:{minute:02d}")

# ==============================================================================
# 2. QUẢN LÝ KÊNH
# ==============================================================================
async def handle_add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_active(update.effective_user.id): return 

    msg = update.effective_message
    if not msg.forward_from_chat: return
    
    chat = msg.forward_from_chat
    chat_id = str(chat.id)
    chat_title = chat.title or f"Channel {chat_id}"
    
    current_db = await get_storage()
    if chat_id in current_db:
        await msg.reply_text(f"⚠️ Kênh **{chat_title}** đã có rồi.")
    else:
        new_data = {"name": chat_title, "limit": 25, "current_index": 0, "files": []}
        await update_channel_data(chat_id, new_data)
        await msg.reply_text(f"✅ Đã thêm: **{chat_title}**\nID: `{chat_id}`", parse_mode="Markdown")

async def menu_kho(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_active(update.effective_user.id): return 

    storage = await get_storage()
    if not storage:
        await update.message.reply_text("📭 Kho trống. Forward tin từ kênh vào để thêm.")
        return

    keyboard = []
    for cid, data in storage.items():
        name = data.get('name', cid)
        keyboard.append([InlineKeyboardButton(f"📂 {name}", callback_data=f"KHO_SELECT_{cid}")])
    
    keyboard.append([InlineKeyboardButton("❌ Đóng", callback_data="KHO_CLOSE")])
    await update.message.reply_text("🏭 **QUẢN LÝ KHO:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ==============================================================================
# 3. XỬ LÝ NÚT BẤM
# ==============================================================================
async def handle_kho_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_active(update.effective_user.id): return 

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
        if cid not in storage: return await query.edit_message_text("❌ Kênh không tồn tại.")
        
        c_data = storage[cid]
        files = c_data.get('files', []) or []
        total = len(files)
        curr = c_data.get('current_index', 0)
        remains = total - curr
        
        # Format chi tiết trong Menu
        status = (
            f"📺 **{c_data.get('name')}**\n"
            f"🆔 `{cid}`\n"
            f"📊 Tiến độ: **{curr}/{total}**\n"
            f"📦 Còn lại: **{remains}**\n"
            f"🚀 Limit: {c_data.get('limit', 25)}/ngày"
        )
        
        kb = [
            [InlineKeyboardButton("📥 Nạp thêm", callback_data=f"KHO_ADD_{cid}"),
             InlineKeyboardButton("🗑 Xóa kênh", callback_data=f"KHO_DEL_ASK_{cid}")],
            [InlineKeyboardButton("⚙️ Chỉnh Limit", callback_data=f"KHO_LIMIT_{cid}"), 
             InlineKeyboardButton("🔄 Reset", callback_data=f"KHO_RESET_{cid}")],
            [InlineKeyboardButton("🔙 Quay lại", callback_data="KHO_BACK")]
        ]
        await query.edit_message_text(status, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif data == "KHO_BACK":
        await query.message.delete()
        await menu_kho(query.message, context)

    elif data.startswith("KHO_DEL_ASK_"):
        cid = data.split("_")[-1]
        kb = [[InlineKeyboardButton("✅ Xóa luôn", callback_data=f"KHO_DEL_CONFIRM_{cid}")],
              [InlineKeyboardButton("❌ Hủy", callback_data=f"KHO_SELECT_{cid}")]]
        await query.edit_message_text(f"⚠️ **XÓA KÊNH?**\nDữ liệu sẽ mất hết.", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif data.startswith("KHO_DEL_CONFIRM_"):
        cid = data.split("_")[-1]
        await delete_channel_data(cid)
        await query.answer("🗑 Đã xóa!", show_alert=True)
        await menu_kho(query.message, context)

    elif data.startswith("KHO_ADD_"):
        cid = data.split("_")[-1]
        context.user_data['autopost_mode'] = {'action': 'adding', 'channel_id': cid, 'buffer': []}
        await query.edit_message_text(f"📥 **NẠP KHO {cid}**\nGửi Ảnh/Video vào đây.\nXong gõ `/xong`.")

    elif data.startswith("KHO_RESET_"):
        cid = data.split("_")[-1]
        await update_channel_data(cid, {"current_index": 0})
        await query.answer("✅ Đã Reset về 0!", show_alert=True)
        await menu_kho(query.message, context)

    elif data.startswith("KHO_LIMIT_"):
        cid = data.split("_")[-1]
        context.user_data['autopost_mode'] = {'action': 'setting_limit', 'channel_id': cid}
        await query.edit_message_text(f"⚙️ Nhập số lượng đăng mỗi ngày:")

# ==============================================================================
# 4. INPUT & LỆNH KHÁC
# ==============================================================================
async def command_setschedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_active(update.effective_user.id): return
    context.user_data['autopost_mode'] = {'action': 'set_hour'}
    await update.message.reply_text("🕒 Nhập **GIỜ** (0-23):")

async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_active(update.effective_user.id): return

    mode = context.user_data.get('autopost_mode')
    if not mode: 
        if update.message.forward_from_chat: await handle_add_channel(update, context)
        return

    msg = update.message
    if mode['action'] == 'set_hour':
        try:
            h = int(msg.text)
            if 0 <= h <= 23:
                mode['hour'] = h
                mode['action'] = 'set_minute'
                await msg.reply_text(f"✅ Giờ: {h}. Nhập **PHÚT** (0-59):")
        except: pass
        return

    elif mode['action'] == 'set_minute':
        try:
            m = int(msg.text)
            if 0 <= m <= 59:
                await save_schedule_time(mode['hour'], m)
                reschedule_job(context.application, mode['hour'], m)
                await msg.reply_text(f"✅ Đã hẹn giờ: **{mode['hour']:02d}:{m:02d}**", parse_mode="Markdown")
                context.user_data['autopost_mode'] = None
        except: pass
        return

    cid = mode.get('channel_id')
    if mode['action'] == 'adding':
        entry = None
        if msg.photo: entry = {"id": msg.photo[-1].file_id, "type": "photo"}
        elif msg.video: entry = {"id": msg.video.file_id, "type": "video"}
        if entry: mode['buffer'].append(entry)
    
    elif mode['action'] == 'setting_limit':
        try:
            val = int(msg.text)
            await update_channel_data(cid, {"limit": val})
            await msg.reply_text(f"✅ Limit mới: **{val}**")
            context.user_data['autopost_mode'] = None
        except: pass

async def command_xong(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_active(update.effective_user.id): return 
    mode = context.user_data.get('autopost_mode')
    if not mode or mode['action'] != 'adding': return
    
    cid = mode['channel_id']
    new_files = mode['buffer']
    if not new_files: 
        context.user_data['autopost_mode'] = None
        return await update.message.reply_text("❌ Chưa có file nào.")

    await update.message.reply_text("⏳ Đang lưu...")
    try:
        current_data = await db.get_autopost_storage()
        c_data = current_data.get(cid, {}) if current_data else {}
        current_files = c_data.get('files', []) or []
        await update_channel_data(cid, {"files": current_files + new_files})
        await update.message.reply_text(f"✅ Đã nạp thêm {len(new_files)} file.")
    except: pass
    context.user_data['autopost_mode'] = None

# ==============================================================================
# 5. BÁO CÁO (Đã chỉnh sửa hiển thị)
# ==============================================================================
async def check_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_active(update.effective_user.id): return
    storage = await get_storage()
    if not storage: return await update.message.reply_text("📭 Trống.")
    h, m = await get_schedule_time()
    
    msg = f"⏰ **Lịch:** {h:02d}:{m:02d}\n\n"
    for cid, data in storage.items():
        files = data.get('files', []) or []
        total = len(files)
        curr = data.get('current_index', 0)
        remains = total - curr
        
        # --- LOGIC MỚI THEO YÊU CẦU ---
        icon = "✅" if remains > 100 else "⚠️"
        msg += f"{icon} **{data.get('name')}**: {curr}/{total} (Còn {remains})\n"
        
    await update.message.reply_text(msg, parse_mode="Markdown")

async def send_all_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_active(update.effective_user.id): return
    await update.message.reply_text("🚀 Đang chạy thủ công...")
    await posting_logic(context.application)
    await check_status(update, context)

# Logic chạy ngầm
async def posting_logic(app):
    print("⏰ Auto Post Running...")
    storage = await get_storage()
    if not storage: return

    for cid, data in storage.items():
        files = data.get('files', []) or []
        curr = data.get('current_index', 0)
        limit = data.get('limit', 25)
        
        if curr >= len(files): continue
        end_index = min(curr + limit, len(files))
        batch = files[curr : end_index]
        chunks = [batch[i:i + 10] for i in range(0, len(batch), 10)]
        
        count = 0
        for chunk in chunks:
            media = []
            for i in chunk:
                if i['type'] == 'photo': media.append(InputMediaPhoto(i['id']))
                elif i['type'] == 'video': media.append(InputMediaVideo(i['id']))
            try:
                if media:
                    await app.bot.send_media_group(cid, media=media)
                    count += len(chunk)
                    await asyncio.sleep(5)
            except: pass
        
        await update_channel_data(cid, {"current_index": curr + count})

async def init_scheduler_from_db(context: ContextTypes.DEFAULT_TYPE):
    await load_active_users() 
    h, m = await get_schedule_time()
    reschedule_job(context.application, h, m)

def register_feature6(app):
    app.add_handler(CommandHandler("activenow", command_activenow))
    app.add_handler(CommandHandler("turnoff", command_turnoff))

    app.add_handler(CommandHandler("kho", menu_kho))
    app.add_handler(CommandHandler("xong", command_xong))
    app.add_handler(CommandHandler("check", check_status))
    app.add_handler(CommandHandler("sendall", send_all_command))
    app.add_handler(CommandHandler("setschedule", command_setschedule))
    
    app.add_handler(CallbackQueryHandler(handle_kho_callback, pattern="^KHO_"))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_input), group=3)
    
    if not scheduler.running: scheduler.start()
    app.job_queue.run_once(init_scheduler_from_db, 1)
