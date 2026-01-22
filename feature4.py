import asyncio
import requests
import time
from telegram import Update
from telegram.ext import ContextTypes, ChatJoinRequestHandler, CommandHandler
# 👇 ĐÃ SỬA DÒNG NÀY: Thay FloodWait bằng RetryAfter
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
        print(f"✅ [SOS Data] Đã lưu ID: {user.id}")
    except Exception as e:
        print(f"❌ Lỗi lưu trữ SOS: {e}")

# ==============================================================================
# 2. XEM BÁO CÁO
# ==============================================================================
async def check_full_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        url = f"{BASE_DB_URL}/IDUser.json"
        res = await asyncio.to_thread(requests.get, url)
        
        if res.status_code != 200 or not res.json():
            await update.message.reply_text("📂 Kho dữ liệu SOS hiện đang TRỐNG.")
            return

        data = res.json()
        total_count = len(data)
        
        group_stats = {}
        for uid, info in data.items():
            source = info.get('from_source', 'Không rõ')
            group_stats[source] = group_stats.get(source, 0) + 1
            
        sorted_stats = sorted(group_stats.items(), key=lambda item: item[1], reverse=True)

        msg = (
            f"📂 <b>BÁO CÁO SOS SYSTEM</b>\n"
            f"➖➖➖➖➖➖➖➖\n"
            f"👥 Tổng ID đã lưu: <b>{total_count}</b>\n\n"
            f"📊 <b>TOP NGUỒN HIỆU QUẢ:</b>\n"
        )
        for name, count in sorted_stats:
            msg += f"🔥 {name}: <b>{count}</b> thành viên\n"
            
        await update.message.reply_text(msg, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {e}")

# ==============================================================================
# 3. GỬI TIN NHẮN (LIVE UPDATE - 30S/LẦN)
# ==============================================================================

async def background_sender(context, chat_id, message_to_copy, user_ids):
    success = 0
    blocked = 0
    total = len(user_ids)
    start_time = time.time()
    
    # ⏰ Mốc thời gian lần cập nhật cuối cùng
    last_update_time = time.time()
    
    # Gửi tin nhắn khởi đầu
    status_msg = await context.bot.send_message(
        chat_id=chat_id, 
        text=f"🚀 <b>Đang khởi động chiến dịch...</b>\nTarget: {total} người.",
        parse_mode="HTML"
    )

    for i, user_id in enumerate(user_ids):
        try:
            await context.bot.copy_message(
                chat_id=int(user_id),
                from_chat_id=message_to_copy.chat_id,
                message_id=message_to_copy.message_id
            )
            success += 1
            await asyncio.sleep(0.04) 

        # 👇 ĐÃ SỬA KHỐI NÀY: Dùng RetryAfter và e.retry_after
        except RetryAfter as e:
            print(f"⚠️ FloodWait: Ngủ {e.retry_after}s...")
            await asyncio.sleep(e.retry_after + 1)
            try:
                await context.bot.copy_message(
                    chat_id=int(user_id),
                    from_chat_id=message_to_copy.chat_id,
                    message_id=message_to_copy.message_id
                )
                success += 1
            except: blocked += 1

        except (Forbidden, BadRequest):
            blocked += 1
        except Exception:
            blocked += 1
        
        # LOGIC MỚI: CẬP NHẬT MỖI 30 GIÂY
        current_time = time.time()
        if (current_time - last_update_time >= 30) or (i + 1) == total:
            try:
                percent = int((i + 1) / total * 100)
                bar = "█" * (percent // 10) + "░" * (10 - (percent // 10))
                
                await status_msg.edit_text(
                    f"🚀 <b>ĐANG GỬI TIN NHẮN...</b>\n"
                    f"➖➖➖➖➖➖➖➖\n"
                    f"📊 Tiến độ: <b>{percent}%</b>\n"
                    f"[{bar}] {i+1}/{total}\n\n"
                    f"✅ Thành công: <b>{success}</b>\n"
                    f"🚫 Thất bại: <b>{blocked}</b>\n"
                    f"⏳ Đang chạy...",
                    parse_mode="HTML"
                )
                last_update_time = current_time
            except Exception:
                pass

    # Báo cáo cuối cùng
    duration = int(time.time() - start_time)
    await status_msg.edit_text(
        f"✅ <b>CHIẾN DỊCH HOÀN TẤT!</b>\n"
        f"⏱ Thời gian: {duration} giây\n"
        f"➖➖➖➖➖➖➖➖\n"
        f"👥 Tổng gửi: <b>{total}</b>\n"
        f"🟢 Thành công: <b>{success}</b>\n"
        f"🔴 Thất bại: <b>{blocked}</b> (Block/Die/Bot Kicked)",
        parse_mode="HTML"
    )

async def send_to_full_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ Hãy Reply tin nhắn cần gửi.")
        return

    # Lấy danh sách ID
    url = f"{BASE_DB_URL}/IDUser.json"
    try:
        init_msg = await update.message.reply_text("⏳ Đang tải danh sách ID...")
        res = await asyncio.to_thread(requests.get, url)
        
        if res.status_code != 200 or not res.json():
            await init_msg.edit_text("❌ Danh sách trống.")
            return
            
        user_ids = list(res.json().keys())
        total = len(user_ids)
        
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
        await update.message.reply_text(f"❌ Lỗi hệ thống: {e}")

# ==============================================================================
# 4. ĐĂNG KÝ
# ==============================================================================
def register_feature4(app):
    app.add_handler(ChatJoinRequestHandler(collect_id_silent))
    app.add_handler(CommandHandler("FullIn4", check_full_info))
    app.add_handler(CommandHandler("sendtofullin4", send_to_full_info))
