import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# 🔑 TOKEN BOT VÀ LINK FIREBASE
BOT_TOKEN = "8064426886:AAEtdQ_tUBNd3BMrPuHgd_k20azPTxcC-5I"
FIREBASE_URL = "https://bot-telegram-99852-default-rtdb.firebaseio.com"

# Biến tạm để xác định người nào đang gửi tin để broadcast
waiting_for_message = {}

# Khi user bắt đầu bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    url = f"{FIREBASE_URL}/users/{user_id}.json"
    requests.put(url, json={"joined": True})
    await update.message.reply_text("✅ Bạn đã được thêm vào danh sách nhận tin.")

# Khi admin gõ /guilink
async def guilink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    waiting_for_message[user_id] = True
    await update.message.reply_text("📨 Gửi nội dung bạn muốn phát cho mọi người.")

# Xử lý tin nhắn kế tiếp để phát tán
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if waiting_for_message.get(user_id):
        del waiting_for_message[user_id]

        msg = update.message.text or update.message.caption or "(tin nhắn không văn bản)"
        await update.message.reply_text("🔄 Đang gửi...")

        res = requests.get(f"{FIREBASE_URL}/users.json")
        if res.status_code == 200:
            users = res.json()
            count = 0
            for uid in users.keys():
                try:
                    await context.bot.send_message(chat_id=uid, text=msg)
                    count += 1
                except:
                    pass
            await update.message.reply_text(f"✅ Đã gửi đến {count} người dùng.")
        else:
            await update.message.reply_text("❌ Không lấy được danh sách người dùng.")
    else:
        await update.message.reply_text("⚠️ Gõ /guilink trước khi gửi nội dung.")

# Chạy bot
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("guilink", guilink))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling()
