import asyncio
import requests
import time
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# ==============================================================================
# ⚙️ CẤU HÌNH DATABASE
# ==============================================================================
BASE_URL = "https://bot-telegram-99852-default-rtdb.firebaseio.com"
BROADCAST_DB = f"{BASE_URL}/broadcast_channels"
HISTORY_DB = f"{BASE_URL}/broadcast_history"
RETENTION_PERIOD = 259200 

async def active_system(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['is_system_active'] = True
    await update.message.reply_text(
        "🔓 **ĐÃ MỞ KHÓA (Cho riêng bạn)!**", parse_mode="Markdown"
    )

async def lock_system(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['is_system_active'] = False
    await update.message.reply_text("🔒 **ĐÃ KHÓA!**", parse_mode="Markdown")

def is_user_allowed(context):
    return context.user_data.get('is_system_active', False)

# ==============================================================================
# 1. HÀM PHỤ TRỢ (UNDO & CLEAN)
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
    if not is_user_allowed(context): return 

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

async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_user_allowed(context): return

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
    if not is_user_allowed(context): return

    try:
        res = await asyncio.to_thread(requests.get, f"{BROADCAST_DB}.json")
        data = res.json()
        if not data: return await update.message.reply_text("📭 Trống.")
        keyboard = [[InlineKeyboardButton(f"❌ {name}", callback_data=f"DEL_ID_{c_id}")] for c_id, name in data.items()]
        keyboard.append([InlineKeyboardButton("🗑 XÓA TẤT CẢ", callback_data="DEL_ALL"), InlineKeyboardButton("Đóng", callback_data="CLOSE_MENU")])
        await update.message.reply_text(f"📋 Xóa:", reply_markup=InlineKeyboardMarkup(keyboard))
    except: pass

async def handle_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_user_allowed(context): return

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
    if not is_user_allowed(context): return

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
# 2. XỬ LÝ GỬI TIN & ALBUM (DIRECT API)
# ==============================================================================

async def send_via_direct_api(token, chat_id, from_chat_id, message_ids):
    url = f"https://api.telegram.org/bot{token}/forwardMessages"
    payload = {
        "chat_id": chat_id,
        "from_chat_id": from_chat_id,
        "message_ids": message_ids
    }
    response = await asyncio.to_thread(requests.post, url, json=payload)
    return response.json()

async def process_album_later(media_group_id, context, from_chat_id):
    await asyncio.sleep(4) 
    
    # ✅ FIX: Lấy buffer từ bot_data
    if 'album_buffer' not in context.bot_data: return
    buffer = context.bot_data['album_buffer']
    
    if media_group_id not in buffer: return 
    
    msg_ids = sorted(buffer[media_group_id])
    del buffer[media_group_id]
    
    try:
        res = await asyncio.to_thread(requests.get, f"{BROADCAST_DB}.json")
        targets = res.json()
    except: targets = {}
    if not targets: return

    sent_log_for_undo = []
    success_count = 0
    fail_count = 0
    error_details = []

    bot_token = context.bot.token 

    for target_id in targets.keys():
        try:
            api_res = await send_via_direct_api(bot_token, target_id, from_chat_id, msg_ids)
            
            if api_res.get("ok"):
                result_msgs = api_res.get("result", [])
                new_ids = [m["message_id"] for m in result_msgs]
                sent_log_for_undo.append({'chat_id': target_id, 'msg_ids': new_ids})
                success_count += 1
            else:
                error_desc = api_res.get("description", "Unknown error")
                fail_count += 1
                error_details.append(f"- ID {target_id}: {error_desc}")
                
        except Exception as e:
            fail_count += 1
            error_details.append(f"- ID {target_id}: {str(e)}")

    if sent_log_for_undo:
        history_entry = {"time": int(time.time()), "sent_to": sent_log_for_undo}
        for source_id in msg_ids:
            try:
                await asyncio.to_thread(requests.put, f"{HISTORY_DB}/{source_id}.json", json=history_entry)
            except: pass

    msg_report = f"✅ **Album ({len(msg_ids)} ảnh):**\n- Thành công: {success_count}\n- Thất bại: {fail_count}"
    if error_details:
        msg_report += "\n⚠️ Lỗi: " + error_details[0]
    
    try:
        await context.bot.send_message(chat_id=from_chat_id, text=msg_report, parse_mode="Markdown")
    except: pass

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or update.effective_chat.type != "private": return

    if not is_user_allowed(context):
        return 

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
            await msg.reply_text("💡 **MENU:**\n/bc on - Bật\n/activeforadmin - Mở khóa\nForward từ kênh vào đây để thêm.")
        return

    # --- GỬI ALBUM ---
    if msg.media_group_id:
        group_id = msg.media_group_id
        
        # ✅ FIX: Tạo buffer trong bot_data
        if 'album_buffer' not in context.bot_data:
            context.bot_data['album_buffer'] = {}
            
        if group_id not in context.bot_data['album_buffer']:
            context.bot_data['album_buffer'][group_id] = []
            asyncio.create_task(process_album_later(group_id, context, msg.chat_id))
            await msg.reply_text("⏳ Đang xử lý Album (API)...")
            
        context.bot_data['album_buffer'][group_id].append(msg.message_id)
        return
    
    # --- GỬI TIN LẺ ---
    try:
        res = await asyncio.to_thread(requests.get, f"{BROADCAST_DB}.json")
        targets = res.json()
    except: targets = {}
    if not targets: return await msg.reply_text("⚠️ List trống.")
    
    status_msg = await msg.reply_text(f"🚀 Đang gửi tin lẻ...")
    sent_log = []
    bot_token = context.bot.token
    
    for target_id in targets.keys():
        try:
            api_res = await asyncio.to_thread(requests.post, 
                f"https://api.telegram.org/bot{bot_token}/forwardMessage",
                json={"chat_id": target_id, "from_chat_id": msg.chat_id, "message_id": msg.message_id}
            )
            resp = api_res.json()
            if resp.get("ok"):
                new_id = resp["result"]["message_id"]
                sent_log.append({'chat_id': target_id, 'msg_ids': [new_id]})
        except: pass
    
    if sent_log:
        entry = {"time": int(time.time()), "sent_to": sent_log}
        await asyncio.to_thread(requests.put, f"{HISTORY_DB}/{msg.message_id}.json", json=entry)
        context.user_data['last_broadcast_history'] = sent_log

    await status_msg.edit_text(f"✅ Xong tin lẻ ({len(sent_log)}/{len(targets)}).")

def register_feature5(app):
    app.add_handler(CommandHandler("activeforadmin", active_system))
    app.add_handler(CommandHandler("lockbot", lock_system))
    app.add_handler(CommandHandler("add", add_group))
    app.add_handler(CommandHandler("bc", broadcast_mode))
    app.add_handler(CommandHandler("delete", show_delete_menu))
    app.add_handler(CommandHandler("undo", undo_broadcast))
    app.add_handler(CallbackQueryHandler(handle_delete_callback, pattern="^(DEL_|CLOSE)"))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message), group=2)
