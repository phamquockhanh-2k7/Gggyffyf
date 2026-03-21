import os
import asyncio
import aiohttp
from dotenv import load_dotenv

load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

headers = {
    "apikey": key,
    "Authorization": f"Bearer {key}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

async def test_insert():
    async with aiohttp.ClientSession() as session:
        endpoint_bc = f"{url}/rest/v1/broadcast_channels"
        resp1 = await session.post(endpoint_bc, json=[{"channel_id": -1001234567}], headers=headers)
        print("broadcast_channels status:", resp1.status)
        print(await resp1.text())

        endpoint_sc = f"{url}/rest/v1/storage_codes"
        resp2 = await session.post(endpoint_sc, json=[{"code": "test_code", "data": {"test": 1}}], headers=headers)
        print("storage_codes status:", resp2.status)
        print(await resp2.text())

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_insert())
