import asyncio
import nest_asyncio
from flask import Flask, request
from telegram import Bot, Update
from telegram.constants import ParseMode
import telegram
import firebase_admin
from firebase_admin import credentials, db
import requests
from keep_alive import keep_alive

BOT_TOKEN = "8064426886:AAFAWxoIKjiyTGG_DxcXFXDUizHZyANldE4"
API_SHORTENER = "https://vuotlink.vip/st?api=5d2e33c19847dea76f4fdb49695fd81aa669af86&url="

WEBHOOK_URL = f"https://bewildered-wenda-happyboy2k777-413cd6df.koyeb.app/webhook/{BOT_TOKEN}"

# Firebase setup
cred = credentials.Certificate("firebase.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': "https://bot-telegram-99852-default-rtdb.firebaseio.com/"
})

bot = Bot(token=BOT_TOKEN)
app = Flask(__name__)
nest_asyncio.apply()

# Hàm rút gọn link
def shorten_url(url):
    try:
        res = requests.get(API_SHORTENER + url)
        return res.text if res.status_code == 200 else url
    except:
        return url

# Ghi log người dùng vào Firebase
def log_user(user_id):
    ref = db.reference(f'/users/{user_id}')
    ref.set({"used": True})

# Xử lý tin nhắn đến
async def handle_update(update: Update):
    if update.message:
        user_id = update.effective_user.id
        log_user(user_id)

        if update.message.text:
            text = update.message.text
            if text.startswith("http"):
                short = shorten_url(text)
                await bot.send_message(chat_id=update.effective_chat.id, text=f"🔗 Rút gọn: {short}")
            else:
                await bot.send_message(chat_id=update.effective_chat.id, text="Gửi link để rút gọn!")

# Route webhook
@app.route(f"/webhook/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = telegram.Update.de_json(request.get_json(force=True), bot)
    asyncio.run(handle_update(update))
    return "OK", 200

# Đặt Webhook
async def set_webhook():
    await bot.set_webhook(WEBHOOK_URL)

# Khởi chạy bot
if __name__ == "__main__":
    keep_alive()  # Tạo server Flask nền nếu cần
    asyncio.run(set_webhook())
    app.run(host="0.0.0.0", port=8080)
