import asyncio
import requests
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
import config

BASE_URL = config.FIREBASE_URL
BROADCAST_DB = f"{BASE_URL}/broadcast_channels"
HISTORY_DB = f"{BASE_URL}/broadcast_history"
RETENTION_PERIOD = 259200 

async def active_system(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['is_active'] = True
    await update.message.reply_text("🔓 Mở khóa.")

async def lock_system(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['is_active'] = False
    await update.message.reply_text("🔒 Đã khóa.")

def is_allowed(ctx): return ctx.user_data.get('is_active', False)

async def clean_old():
    try:
        data = (await asyncio.to_thread(requests.get, f"{HISTORY_DB}.json")).json()
        if not data: return
        now = int(time.time())
        for k, v in data.items():
            if now - v.get('time', 0) > RETENTION_PERIOD:
                await asyncio.to_thread(requests.delete, f"{HISTORY_DB}/{k}.json")
    except: pass

async def undo_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(context): return 
    msg = update.effective_message
    target = None
    if msg.reply_to_message:
        rid = str(msg.reply_to_message.message_id)
        target = (await asyncio.to_thread(requests.get, f"{HISTORY_DB}/{rid}.json")).json()
        if target: await asyncio.to_thread(requests.delete, f"{HISTORY_DB}/{rid}.json")
    elif context.user_data.get('last_bc'):
        target = {'sent_to': context.user_data['last_bc']}
        context.user_data['last_bc'] = []
    
    if not target: return await msg.reply_text("⚠️ Không có gì để Undo.")
    
    stt = await msg.reply_text("🗑 Đang xóa...")
    cnt = 0
    for i in target.get('sent_to', []):
        for mid in i['msg_ids']:
            try:
                await context.bot.delete_message(i['chat_id'], mid)
                cnt += 1
            except: pass
    await stt.edit_text(f"✅ Đã xóa {cnt} tin.")

async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(context): return
    if update.effective_chat.type == "private": return await update.message.reply_text("❌ Forward từ kênh vào đây.")
    try:
        await asyncio.to_thread(requests.put, f"{BROADCAST_DB}/{update.effective_chat.id}.json", json=update.effective_chat.title or "Group")
        await update.message.reply_text("✅ Đã thêm.")
    except: pass

async def show_del_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(context): return
    data = (await asyncio.to_thread(requests.get, f"{BROADCAST_DB}.json")).json()
    if not data: return await update.message.reply_text("📭 Trống.")
    kb = [[InlineKeyboardButton(f"❌ {n}", callback_data=f"DEL_ID_{i}")] for i, n in data.items()]
    kb.append([InlineKeyboardButton("🗑 XÓA HẾT", callback_data="DEL_ALL"), InlineKeyboardButton("Đóng", callback_data="CLOSE_MENU")])
    await update.message.reply_text("📋 Xóa:", reply_markup=InlineKeyboardMarkup(kb))

async def handle_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(context): return
    q = update.callback_query
    await q.answer()
    if q.data == "CLOSE_MENU": return await q.message.delete()
    if q.data == "DEL_ALL":
        await asyncio.to_thread(requests.delete, f"{BROADCAST_DB}.json")
        return await q.edit_message_text("✅ Đã xóa hết.")
    if q.data.startswith("DEL_ID_"):
        await asyncio.to_thread(requests.delete, f"{BROADCAST_DB}/{q.data.split('_')[-1]}.json")
        await q.edit_message_text("✅ Đã xóa.")

async def broadcast_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(context): return
    if context.args and context.args[0].lower() == "on":
        context.user_data['cur_mode'] = 'BC'
        await update.message.reply_text("📡 BẬT Broadcast.")
        asyncio.create_task(clean_old())
    elif context.args:
        context.user_data['cur_mode'] = None
        await update.message.reply_text("zzz TẮT.")

async def send_direct(token, cid, from_id, mids):
    url = f"https://api.telegram.org/bot{token}/forwardMessages"
    return (await asyncio.to_thread(requests.post, url, json={"chat_id": cid, "from_chat_id": from_id, "message_ids": mids})).json()

async def proc_album(gid, ctx, fid):
    await asyncio.sleep(4)
    buf = ctx.bot_data.get('alb_buf', {})
    if gid not in buf: return
    mids = sorted(buf[gid])
    del buf[gid]
    
    targs = (await asyncio.to_thread(requests.get, f"{BROADCAST_DB}.json")).json()
    if not targs: return
    
    log, suc, fail, err = [], 0, 0, []
    tk = ctx.bot.token
    for tid in targs.keys():
        try:
            res = await send_direct(tk, tid, fid, mids)
            if res.get("ok"):
                log.append({'chat_id': tid, 'msg_ids': [m['message_id'] for m in res['result']]})
                suc += 1
            else:
                fail += 1
                err.append(res.get("description", "?"))
        except Exception as e:
            fail += 1
            err.append(str(e))
    
    if log:
        hentry = {"time": int(time.time()), "sent_to": log}
        for sid in mids: await asyncio.to_thread(requests.put, f"{HISTORY_DB}/{sid}.json", json=hentry)
    
    rpt = f"✅ Album ({len(mids)}):\nOk: {suc} | Fail: {fail}"
    if err: rpt += f"\nLỗi: {err[0]}"
    try: await ctx.bot.send_message(fid, rpt)
    except: pass

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or update.effective_chat.type != "private": return
    if not is_allowed(context): return
    
    if context.user_data.get('cur_mode') != 'BC':
        if msg.forward_from_chat:
            try:
                await asyncio.to_thread(requests.put, f"{BROADCAST_DB}/{msg.forward_from_chat.id}.json", json=msg.forward_from_chat.title)
                await msg.reply_text(f"🎯 Thêm: {msg.forward_from_chat.title}")
            except: pass
        else: await msg.reply_text("💡 /bc on để bật mode gửi.")
        return

    if msg.media_group_id:
        gid = msg.media_group_id
        if 'alb_buf' not in context.bot_data: context.bot_data['alb_buf'] = {}
        if gid not in context.bot_data['alb_buf']:
            context.bot_data['alb_buf'][gid] = []
            asyncio.create_task(proc_album(gid, context, msg.chat_id))
            await msg.reply_text("⏳ Gửi album...")
        context.bot_data['alb_buf'][gid].append(msg.message_id)
        return

    targs = (await asyncio.to_thread(requests.get, f"{BROADCAST_DB}.json")).json()
    if not targs: return await msg.reply_text("⚠️ List trống.")
    
    stt = await msg.reply_text("🚀 Đang gửi...")
    log, tk = [], context.bot.token
    for tid in targs.keys():
        try:
            res = (await asyncio.to_thread(requests.post, f"https://api.telegram.org/bot{tk}/forwardMessage", json={"chat_id": tid, "from_chat_id": msg.chat_id, "message_id": msg.message_id})).json()
            if res.get("ok"): log.append({'chat_id': tid, 'msg_ids': [res["result"]["message_id"]]})
        except: pass
    
    if log:
        await asyncio.to_thread(requests.put, f"{HISTORY_DB}/{msg.message_id}.json", json={"time": int(time.time()), "sent_to": log})
        context.user_data['last_bc'] = log
    
    await stt.edit_text(f"✅ Xong ({len(log)}/{len(targs)}).")

def register_feature5(app):
    app.add_handler(CommandHandler("activeforadmin", active_system))
    app.add_handler(CommandHandler("lockbot", lock_system))
    app.add_handler(CommandHandler("add", add_group))
    app.add_handler(CommandHandler("bc", broadcast_mode))
    app.add_handler(CommandHandler("delete", show_del_menu))
    app.add_handler(CommandHandler("undo", undo_broadcast))
    app.add_handler(CallbackQueryHandler(handle_del, pattern="^(DEL_|CLOSE)"))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_msg), group=2)
