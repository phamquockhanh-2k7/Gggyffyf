import asyncio
import config
from features.shortener import generate_shortened_content
import traceback

async def test():
    try:
        url = "https://t.me/hoahocduong_vip?start=0401202641jO9Rl"
        res = await generate_shortened_content(url)
        print("Success:", res)
    except Exception as e:
        print("Crash!")
        traceback.print_exc()

if __name__ == "__main__":
    if __import__('os').name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test())
