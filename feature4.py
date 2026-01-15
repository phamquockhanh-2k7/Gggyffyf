import asyncio
import requests
from telegram import Update
# ĐÃ THÊM 'filters' VÀO DÒNG IMPORT DƯỚI ĐÂY
from telegram.ext import ContextTypes, ChatJoinRequestHandler, CommandHandler, filters

# Cấu hình Firebase
BASE_DB_URL = 'https://bot-telegram-99852-default-rtdb.firebaseio.com'

async def collect_id_silent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lưu ID người xin vào nhóm qua REST API"""
    request = update.chat_join_request
    user = request.from_user
    chat = request.chat
    try:
        user_info = {
            'first_name': user.first_name,
            'username': user.username if user.username else "No Username",
            'joined_date': str(request.date),
            'from_source': chat.title
        }
        url = f"{BASE_DB_URL}/IDUser/{user.id}.json"
        await asyncio.to_thread(requests.put, url, json=user_info)
        print(f"✅ [SOS Data] Đã lưu ID: {user.id} (Nguồn: {chat.title})")
    except Exception as e:
        print(f"❌ Lỗi lưu trữ SOS: {e}")

async def check_full_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        url = f"{BASE_DB_URL}/IDUser.json"
        res = await asyncio.to_thread(requests.get, url)
        if res.status_code != 200 or not res.json():
            await update.message.reply_text("📂 Kho dữ liệu SOS hiện đang TRỐNG.", parse_mode="HTML")
            return
        data = res.json()
        total_count = len(data)
        group_stats = {}
        for uid, info in data.items():
            source = info.get('from_source', 'Không rõ')
            group_stats[source] = group_stats.get(source, 0) + 1
        
        # Sắp xếp từ cao xuống thấp
        sorted_stats = sorted(group_stats.items(), key=lambda item: item[1], reverse=True)
        
        msg = f"📂 <b>BÁO CÁO SOS</b>\n👥 Tổng ID: <b>{total_count}</b>\n\n📊 <b>TOP NGUỒN:</b>\n"
        for name, count in sorted_stats:
            msg += f"🔥 {name}: <b>{count}</b> mem\n"
        await update.message.reply_text(msg, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {e}")

async def send_to_full_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ Hãy Reply tin nhắn cần gửi và gõ lệnh.", parse_mode="HTML")
        return
    url = f"{BASE_DB_URL}/IDUser.json"
    try:
        res = await asyncio.to_thread(requests.get, url)
        if res.status_code != 200 or not res.json():
            await update.message.reply_text("❌ Danh sách trống.")
            return
        user_ids = list(res.json().keys())
        status_msg = await update.message.reply_text(f"🚀 Đang gửi cho {len(user_ids)} người...", parse_mode="HTML")
        success, blocked = 0, 0
        for user_id in user_ids:
            try:
                await context.bot.copy_message(
                    chat_id=int(user_id),
                    from_chat_id=update.message.chat_id,
                    message_id=update.message.reply_to_message.message_id
                )
                success += 1
                await asyncio.sleep(0.05)
            except: blocked += 1
        await status_msg.edit_text(f"✅ HOÀN TẤT\n🟢 Thành công: {success}\n🔴 Thất bại: {blocked}")
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {e}")

def register_feature4(app):
    # ChatJoinRequestHandler BẮT BUỘC phải hoạt động ở nhóm/kênh để bắt người (KHÔNG thêm filter Private)
    app.add_handler(ChatJoinRequestHandler(collect_id_silent))
    
    # Lệnh Admin thì chỉ cho dùng riêng tư
    app.add_handler(CommandHandler("FullIn4", check_full_info, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("sendtofullin4", send_to_full_info, filters=filters.ChatType.PRIVATE))
