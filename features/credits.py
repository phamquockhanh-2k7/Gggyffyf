import asyncio
import requests
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
from telegram.ext import ContextTypes, CallbackQueryHandler
import config

FIREBASE_URL = config.FIREBASE_URL

async def get_credits(user_id):
    res = await asyncio.to_thread(requests.get, f"{FIREBASE_URL}/ref/{user_id}.json")
    return res.json() if (res.status_code == 200 and res.json() is not None) else None

async def init_user_if_new(user_id):
    curr = await get_credits(user_id)
    if curr is None:
        await asyncio.to_thread(requests.put, f"{FIREBASE_URL}/ref/{user_id}.json", json=1)
        return 1
    return curr

async def add_credit(user_id, amount=1):
    curr = await get_credits(user_id) or 0
    await asyncio.to_thread(requests.put, f"{FIREBASE_URL}/ref/{user_id}.json", json=curr + amount)

async def deduct_credit(user_id):
    curr = await get_credits(user_id) or 0
    if curr > 0:
        await asyncio.to_thread(requests.put, f"{FIREBASE_URL}/ref/{user_id}.json", json=curr - 1)
        return True
    return False

async def check_daily_task_status(user_id):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    res = await asyncio.to_thread(requests.get, f"{FIREBASE_URL}/daily_check/{user_id}.json")
    return res.json() == today

async def mark_daily_task_done(user_id):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    await asyncio.to_thread(requests.put, f"{FIREBASE_URL}/daily_check/{user_id}.json", json=today)

async def open_task_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_daily_task_status(query.from_user.id):
        return await context.bot.send_message(query.from_user.id, "⚠️ Nhận rồi! Quay lại mai nhé.")
    
    kb = [[InlineKeyboardButton("👉 B1: Lấy Link", callback_data="task_get_link")],
          [InlineKeyboardButton("✅ B2: Xác nhận", callback_data="task_confirm")]]
    await context.bot.send_message(query.from_user.id, "<b>🎁 NHIỆM VỤ NGÀY</b>\nTham gia kênh để nhận 1 lượt.", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def handle_task_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    if query.data == "task_get_link":
        context.user_data['temp_task'] = True
        kb = [[InlineKeyboardButton("🚀 Tham gia ngay", url=config.JOIN_LINK_CHANNEL)],
              [InlineKeyboardButton("✅ B2: Xác nhận", callback_data="task_confirm")]]
        await query.edit_message_text("🔗 Ấn tham gia dưới:", reply_markup=InlineKeyboardMarkup(kb))
    elif query.data == "task_confirm":
        if not context.user_data.get('temp_task'): return await context.bot.send_message(uid, "❌ Làm B1 trước!")
        if await check_daily_task_status(uid): return await query.edit_message_text("⚠️ Nhận rồi!")
        await add_credit(uid, 1)
        await mark_daily_task_done(uid)
        context.user_data['temp_task'] = False
        await query.edit_message_text("🎉 XONG! +1 lượt.")

async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    alias = query.data.replace("dl_", "").strip()
    try:
        creds = await get_credits(uid) or 1
        if creds <= 0: return await query.answer("❌ Hết lượt!", show_alert=True)
        await query.answer("🔍 Đang tải...")
        
        # Check Shared
        url1 = f"{FIREBASE_URL}/shared/{alias}.json"
        res1 = await asyncio.to_thread(requests.get, url1)
        data = res1.json()
        
        # Check Root
        if not data:
            url2 = f"{FIREBASE_URL}/{alias}.json"
            res2 = await asyncio.to_thread(requests.get, url2)
            data = res2.json()

        if data:
            if await deduct_credit(uid):
                new_creds = creds - 1
                media, text, docs = [], [], []
                for item in data:
                    if item["type"] == "photo": media.append(InputMediaPhoto(item["file_id"]))
                    elif item["type"] == "video": media.append(InputMediaVideo(item["file_id"]))
                    elif item["type"] == "text": text.append(item["file_id"])
                    elif item["type"] == "document": docs.append(item["file_id"])

                if text: await context.bot.send_message(query.message.chat_id, "\n\n".join(text))
                if media:
                    for i in range(0, len(media), 10):
                        await context.bot.send_media_group(query.message.chat_id, media[i:i+10])
                for doc in docs: await context.bot.send_document(query.message.chat_id, doc)
                
                await context.bot.send_message(query.message.chat_id, f"✅ Đã gửi! Còn {new_creds} lượt.")
                
                ref_link = f"https://t.me/{context.bot.username}?start=ref_{uid}"
                kb = [[InlineKeyboardButton(f"📥 Tải ({new_creds} lượt)", callback_data=f"dl_{alias}")],
                      [InlineKeyboardButton("🔗 Chia sẻ", url=f"https://t.me/share/url?url={ref_link}&text=Hot")],
                      [InlineKeyboardButton("🎁 Nhiệm vụ", callback_data="task_open")]]
                await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(kb))
        else: await context.bot.send_message(query.message.chat_id, "❌ Không tìm thấy dữ liệu.")
    except Exception as e: await context.bot.send_message(query.message.chat_id, f"❌ Lỗi: {e}")

async def delete_msg_job(context: ContextTypes.DEFAULT_TYPE):
    try: await context.bot.delete_message(context.job.chat_id, context.job.data)
    except: pass

async def check_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try: await update.message.delete()
    except: pass
    if not update.message: return
    uid = update.effective_user.id
    creds = await init_user_if_new(uid)
    ref = f"https://t.me/{context.bot.username}?start=ref_{uid}"
    txt = f"👤 **PROFILE**\n🆔: `{uid}`\n📥: **{creds}**\n🔗 `{ref}`"
    kb = [[InlineKeyboardButton("🚀 Chia sẻ", url=f"https://t.me/share/url?url={ref}&text=Hot")]]
    await update.message.reply_text(txt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def cheat_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await add_credit(update.effective_user.id, 20)
    await update.message.reply_text("Admin: +20.")

def register_feature3(app):
    app.add_handler(CallbackQueryHandler(download_callback, pattern="^dl_"))
    app.add_handler(CallbackQueryHandler(open_task_menu, pattern="^task_open$"))
    app.add_handler(CallbackQueryHandler(handle_task_actions, pattern="^task_(get_link|confirm)$"))
