import asyncio
import requests
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ChatJoinRequestHandler, CommandHandler, CallbackQueryHandler
from telegram.error import Forbidden, BadRequest, RetryAfter, NetworkError
import config

BASE_DB_URL = config.FIREBASE_URL
CHECKPOINT_DB = f"{BASE_DB_URL}/broadcast_checkpoint.json"
active_tasks = set()

async def collect_id_silent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    req = update.chat_join_request
    user, chat = req.from_user, req.chat
    try:
        info = {'first_name': user.first_name, 'username': user.username or "No", 'joined_date': str(req.date), 'from_source': chat.title}
        await asyncio.to_thread(requests.put, f"{BASE_DB_URL}/IDUser/{user.id}.json", json=info)
    except: pass

async def check_full_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        res = await asyncio.to_thread(requests.get, f"{BASE_DB_URL}/IDUser.json")
        data = res.json()
        if not data: return await update.message.reply_text("📂 Trống.")
        stats = {}
        for _, i in data.items():
            src = i.get('from_source', 'Unknown')
            stats[src] = stats.get(src, 0) + 1
        msg = f"📂 **BÁO CÁO SOS**\n👥 Tổng: {len(data)}\n" + "\n".join([f"🔥 {k}: {v}" for k, v in sorted(stats.items(), key=lambda x: x[1], reverse=True)])
        await update.message.reply_text(msg, parse_mode="Markdown")
    except: await update.message.reply_text("❌ Lỗi.")

async def save_checkpoint(index, success, blocked):
    await asyncio.to_thread(requests.put, CHECKPOINT_DB, json={"index": index, "success": success, "blocked": blocked})

async def background_sender(context, chat_id, msg_copy, user_ids, start=0, succ=0, blk=0):
    total = len(user_ids)
    targets = user_ids[start:]
    start_time = time.time()
    last_upd = time.time()
    
    status_msg = await context.bot.send_message(chat_id, f"🚀 Chạy từ {start}/{total}...")

    for i, uid in enumerate(targets):
        real_idx = start + i
        try:
            tid = int(uid)
            await context.bot.copy_message(tid, msg_copy.chat_id, msg_copy.message_id)
            succ += 1
            await asyncio.sleep(0.8)
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after + 2)
            try:
                await context.bot.copy_message(tid, msg_copy.chat_id, msg_copy.message_id)
                succ += 1
            except: blk += 1
        except: blk += 1
        
        if time.time() - last_upd >= 20 or (real_idx + 1) == total:
            await save_checkpoint(real_idx + 1, succ, blk)
            try:
                pc = int((real_idx + 1) / total * 100)
                await status_msg.edit_text(f"🚀 {pc}%\n✅ {succ} | 🚫 {blk}\n📍 {real_idx + 1}/{total}")
                last_upd = time.time()
            except: pass

    await asyncio.to_thread(requests.delete, CHECKPOINT_DB)
    await status_msg.edit_text(f"✅ XONG!\n⏱ {int(time.time() - start_time)}s\n✅ {succ} | 🚫 {blk}")

async def send_to_full_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    try:
        cp = (await asyncio.to_thread(requests.get, CHECKPOINT_DB)).json()
    except: cp = None

    if cp:
        kb = [[InlineKeyboardButton(f"▶️ Tiếp tục từ {cp['index']}", callback_data="RESUME_BROADCAST")],
              [InlineKeyboardButton("🔄 Chạy mới", callback_data="NEW_BROADCAST")]]
        await msg.reply_text(f"⚠️ Có tiến trình cũ ({cp['index']}).", reply_markup=InlineKeyboardMarkup(kb))
        context.user_data['broadcast_msg'] = msg.reply_to_message
        return

    if not msg.reply_to_message: return await msg.reply_text("⚠️ Reply tin nhắn cần gửi.")
    await start_broadcast_process(update, context, msg.reply_to_message)

async def handle_broadcast_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "NEW_BROADCAST":
        await asyncio.to_thread(requests.delete, CHECKPOINT_DB)
        if not context.user_data.get('broadcast_msg'): return await q.edit_message_text("❌ Mất tin nhắn gốc.")
        await q.delete_message()
        await start_broadcast_process(update, context, context.user_data['broadcast_msg'])
    elif q.data == "RESUME_BROADCAST":
        cp = (await asyncio.to_thread(requests.get, CHECKPOINT_DB)).json()
        if not cp: return await q.edit_message_text("❌ Lỗi CP.")
        await q.delete_message()
        if not context.user_data.get('broadcast_msg'): return await context.bot.send_message(q.message.chat_id, "❌ Mất tin nhắn gốc.")
        await start_broadcast_process(update, context, context.user_data['broadcast_msg'], cp['index'], cp['success'], cp['blocked'])

async def start_broadcast_process(update, context, msg_copy, start=0, succ=0, blk=0):
    chat_id = update.effective_chat.id
    init = await context.bot.send_message(chat_id, "⏳ Tải list...")
    res = await asyncio.to_thread(requests.get, f"{BASE_DB_URL}/IDUser.json")
    if not res.json(): return await init.edit_text("❌ Trống.")
    ids = list(res.json().keys())[::-1]
    await init.delete()
    t = asyncio.create_task(background_sender(context, chat_id, msg_copy, ids, start, succ, blk))
    active_tasks.add(t)
    t.add_done_callback(active_tasks.discard)

def register_feature4(app):
    app.add_handler(ChatJoinRequestHandler(collect_id_silent))
    app.add_handler(CommandHandler("FullIn4", check_full_info))
    app.add_handler(CommandHandler("sendtofullin4", send_to_full_info))
    app.add_handler(CallbackQueryHandler(handle_broadcast_decision, pattern="^(NEW_BROADCAST|RESUME_BROADCAST)$"))
