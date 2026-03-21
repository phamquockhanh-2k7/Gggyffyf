import asyncio
from telegram import Bot
import os
from dotenv import load_dotenv

load_dotenv()
tokens = os.getenv("LIST_TOKEN_MAIN", "").split(',')
bot = Bot(tokens[0].strip())

async def main():
    try:
        content = """**Link mua + vượt :** \n https://checklink.top/abc?tag=1&ref=2\n**Link mua 2 :** \n test"""
        await bot.send_message(chat_id='869333454', text=f"<pre>{content}</pre>", parse_mode="HTML")
        print("Success!")
    except Exception as e:
        print("ERROR:", repr(e))

asyncio.run(main())
