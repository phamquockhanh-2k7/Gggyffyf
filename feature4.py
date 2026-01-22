import asyncio
import requests
import time
from telegram import Update
from telegram.ext import ContextTypes, ChatJoinRequestHandler, CommandHandler
# Import đúng lỗi để xử lý chặn
from telegram.error import Forbidden, BadRequest, RetryAfter

# ==============================================================================
# CẤU HÌNH
# ==============================================================================
BASE_DB_URL = 'https://bot-telegram-99852-default-rtdb.firebaseio.com'

# ==============================================================================
# 1. TỰ ĐỘNG THU THẬP ID
# ==============================================================================
async def collect_id_silent(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    except Exception: pass

# ==============================================================================
# 2. XEM BÁO CÁO
# ==============================================================================
async def check_full_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        url = f"{BASE_DB_URL}/IDUser.json"
        res = await asyncio.to_thread(requests.get, url)
        if res.status_code != 200 or not res.json():
            await update.message.reply_text("📂 Data trống.")
            return
        data = res.json()
        total_count = len(data)
        group_stats = {}
        for uid, info in data.items():
            source = info.get('from_source', 'Không rõ')
            group_stats[source] = group_stats.get(source, 0) + 1
        sorted_stats = sorted(group_stats.items(), key=lambda item: item[1], reverse=True)
        msg = f"📂 <b>BÁO CÁO SOS</b>\n➖➖➖➖\n👥 Tổng ID: <b>{total_count}</b>\n\n📊 <b>NGUỒN:</b>\n"
        for name, count in sorted_stats:
            msg += f"🔥 {name}: <b>{count}</b>\n"
        await update.message.reply_text(msg, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {e}")

# ==============================================================================
# 3. GỬI TIN NHẮN (MÔ PHỎNG CƠ CHẾ 1s/tin CỦA BOT XỊN)
# ==============================================================================

async def background_sender(context, chat_id, message_to_copy, user_ids):
    success = 0
    blocked = 0
    total = len(user_ids)
    start_time = time.time()
    
    # Gửi tin nhắn khởi đầu
    status_msg = await context.bot.send_message(
        chat_id=chat_id, 
        text=f"🚀 <b>Khởi động...</b>\nTarget: {total} người.",
        parse_mode="HTML"
    )

    for i, user_id in enumerate(user_ids):
        try:
            # Chuyển ID sang int
            try: target_id = int(user_id)
            except: 
                blocked += 1
                continue

            await context.bot.copy_message(
                chat_id=target_id,
                from_chat_id=message_to_copy.chat_id,
                message_id=message_to_copy.message_id
            )
            success += 1
            
            # 🔥 CHÌA KHÓA THÀNH CÔNG: NGỦ 0.8 GIÂY
            # Cộng với thời gian mạng xử lý ~0.2s = Tổng 1 giây/tin
            # Tốc độ này cực kỳ an toàn, Telegram không bao giờ chặn.
            await asyncio.sleep(0.8) 

        except RetryAfter as e:
            # Nếu vẫn đen đủi bị chặn, ngủ đúng thời gian quy định
            wait_s = e.retry_after
            print(f"⚠️ Rate Limit: Ngủ {wait_s}s...")
            await asyncio.sleep(wait_s + 2)
            # Thử lại lần nữa
            try:
                await context.bot.copy_message(chat_id=target_id, from_chat_id=message_to_copy.chat_id, message_id=message_to_copy.message_id)
                success += 1
            except: blocked += 1

        except (Forbidden, BadRequest):
            blocked += 1
        except Exception:
            blocked += 1
        
        # 🔄 CẬP NHẬT: MỖI 20 NGƯỜI (Giống hệt Bot bạn thấy)
        # Vì 1 người tốn 1s, nên 20 người sẽ tốn ~20s -> Update mỗi 20s.
        if (i + 1) % 20 == 0 or (i + 1) == total:
            try:
                percent = int((i + 1) / total * 100)
                bar = "█" * (percent // 10) + "░" * (10 - (percent // 10))
                
                await status_msg.edit_text(
                    f"🚀 <b>ĐANG GỬI... ({percent}%)</b>\n"
                    f"[{bar}]\n"
                    f"➖➖➖➖➖➖\n"
                    f"✅ Đã gửi: <b>{success}</b>\n"
                    f"🚫 Thất bại: <b>{blocked}</b>\n"
                    f"👤 Tiến độ: <b>{i+1}/{total}</b>",
                    parse_mode="HTML"
                )
            except Exception: pass

    # Báo cáo cuối cùng
    duration = int(time.time() - start_time)
    await status_msg.edit_text(
        f"✅ <b>HOÀN TẤT!</b>\n"
        f"⏱ Thời gian: {duration}s\n"
        f"➖➖➖➖➖➖\n"
        f"👥 Tổng: <b>{total}</b>\n"
        f"🟢 Thành công: <b>{success}</b>\n"
        f"🔴 Thất bại: <b>{blocked}</b>",
        parse_mode="HTML"
    )

async def send_to_full_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ Hãy Reply tin nhắn cần gửi.")
        return

    url = f"{BASE_DB_URL}/IDUser.json"
    try:
        init_msg = await update.message.reply_text("⏳ Tải danh sách...")
        res = await asyncio.to_thread(requests.get, url)
        
        if res.status_code != 200 or not res.json():
            await init_msg.edit_text("❌ List trống.")
            return
            
        user_ids = list(res.json().keys())
        # Đảo ngược để gửi người mới trước (Mẹo nhỏ tăng tương tác)
        user_ids.reverse()
        
        await init_msg.delete()

        asyncio.create_task(
            background_sender(
                context, 
                update.effective_chat.id, 
                update.message.reply_to_message, 
                user_ids
            )
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {e}")

# ==============================================================================
# 4. ĐĂNG KÝ
# ==============================================================================
def register_feature4(app):
    app.add_handler(ChatJoinRequestHandler(collect_id_silent))
    app.add_handler(CommandHandler("FullIn4", check_full_info))
    app.add_handler(CommandHandler("sendtofullin4", send_to_full_info))
