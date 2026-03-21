import os
import json
import asyncio
import aiohttp
from dotenv import load_dotenv

load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

headers = {
    "apikey": key,
    "Authorization": f"Bearer {key}",
    "Prefer": "count=exact"
}

async def get_count(session, table):
    endpoint = f"{url}/rest/v1/{table}?select=*"
    async with session.head(endpoint, headers=headers) as resp:
        content_range = resp.headers.get("Content-Range")
        if content_range:
            return int(content_range.split('/')[-1])
        return 0

async def main():
    print("Loading firebase_backup.json to count original records...")
    with open('firebase_backup.json', encoding='utf-8') as f:
        data = json.load(f)

    counts = {
        "IDUser": len([k for k in data.get('IDUser', {}).keys() if str(k).replace('-', '').isdigit()]),
        "ref": len([k for k in data.get('ref', {}).keys() if str(k).replace('-', '').isdigit()]),
        "broadcast_channels": len([k for k in (data.get('broadcast_channels', {}).keys() if isinstance(data.get('broadcast_channels', {}), dict) else data.get('broadcast_channels', [])) if str(k).replace('-', '').isdigit()]),
        "shared": len(data.get('shared', {})),
        "autopost_settings": len([k for k in data.get('autopost_settings', {}).keys() if str(k).replace('-', '').isdigit()]),
        "autopost_storage": len([k for k, v in data.get('autopost_storage', {}).items() if str(k).replace('-', '').isdigit() and isinstance(v, dict)]),
        "autopost_users": len([k for k in data.get('autopost_users', {}).keys() if str(k).replace('-', '').isdigit()]),
        "broadcast_history": len([k for k, v in data.get('broadcast_history', {}).items() if isinstance(v, dict)]),
        "daily_check": len([k for k in data.get('daily_check', {}).keys() if str(k).replace('-', '').isdigit()]),
        "user_files": len([k for k in data.get('user_files', {}).keys() if str(k).replace('-', '').isdigit()])
    }

    known_keys = ['IDUser', 'ref', 'broadcast_channels', 'broadcast_history', 
                  'autopost_settings', 'autopost_storage', 'autopost_users', 
                  'daily_check', 'shared', 'users', 'settings']
    storage_codes_count = len([k for k in data.keys() if k not in known_keys])
    counts["storage_codes"] = storage_codes_count

    print("\n--- Original Firebase Data Counts ---")
    for k, v in counts.items():
        print(f"{k}: {v}")

    print("\n--- Fetching Supabase Counts ---")
    async with aiohttp.ClientSession() as session:
        tasks = [get_count(session, table) for table in counts.keys()]
        results = await asyncio.gather(*tasks)

        supabase_counts = dict(zip(counts.keys(), results))
        for k, v in supabase_counts.items():
            print(f"{k}: {v}")

    print("\n--- Comparison ---")
    all_match = True
    for k in counts.keys():
        if counts[k] == supabase_counts.get(k, 0):
            print(f"[OK] {k}: MATCH ({counts[k]})")
        else:
            print(f"[FAIL] {k}: MISMATCH (Firebase: {counts[k]}, Supabase: {supabase_counts.get(k, 0)})")
            all_match = False

    if all_match:
        print("\n[SUCCESS] ALL DATA HAS BEEN FULLY MIGRATED!")
    else:
        print("\n[WARNING] SOME DATA IS MISSING.")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
