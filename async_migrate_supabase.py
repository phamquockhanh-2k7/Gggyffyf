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
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

BATCH_SIZE = 1000
CONCURRENCY_LIMIT = 10

async def upsert_batch(session, table, batch, semaphore):
    endpoint = f"{url}/rest/v1/{table}"
    async with semaphore:
        for attempt in range(3):
            try:
                async with session.post(endpoint, json=batch, headers=headers) as resp:
                    if resp.status not in [200, 201]:
                        text = await resp.text()
                        print(f"Error inserting into {table}: {resp.status} - {text}")
                    else:
                        print(f"  -> Inserted {len(batch)} rows into {table}")
                    return
            except Exception as e:
                print(f"Attempt {attempt + 1} failed for {table}: {e}")
                await asyncio.sleep(2)

async def upload_data():
    if not os.path.exists('firebase_backup.json'):
        print("firebase_backup.json not found!")
        return

    print("Loading huge JSON file into RAM...")
    with open('firebase_backup.json', encoding='utf-8') as f:
        data = json.load(f)

    print("[SUCCESS] Loaded! Starting data migration to Supabase...")

    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    
    async with aiohttp.ClientSession() as session:
        tasks = []

        if 'IDUser' in data:
            def sid_valid(s): return str(s).replace('-','').isdigit()
            print(f"Migrating IDUser (Total: {len(data['IDUser'])})")
            users_batch = []
            for uid, udata in data['IDUser'].items():
                if not sid_valid(uid) or not isinstance(udata, dict): continue
                users_batch.append({
                    "user_id": int(uid),
                    "first_name": str(udata.get('first_name', '')),
                    "username": str(udata.get('username', '')),
                    "from_source": str(udata.get('from_source', '')),
                    "joined_date": udata.get('joined_date') if udata.get('joined_date') else None
                })
                
                if len(users_batch) >= BATCH_SIZE:
                    tasks.append(upsert_batch(session, "IDUser", users_batch, semaphore))
                    users_batch = []
            if users_batch: tasks.append(upsert_batch(session, "IDUser", users_batch, semaphore))

        if 'ref' in data:
            print(f"Migrating ref (Total: {len(data['ref'])})")
            ref_batch = []
            for uid, credit in data['ref'].items():
                if uid.replace('-','').isdigit():
                    ref_batch.append({"user_id": int(uid), "credit": int(credit)})
                if len(ref_batch) >= BATCH_SIZE:
                    tasks.append(upsert_batch(session, "ref", ref_batch, semaphore))
                    ref_batch = []
            if ref_batch: tasks.append(upsert_batch(session, "ref", ref_batch, semaphore))

        if 'broadcast_channels' in data:
            print(f"Migrating broadcast_channels (Total: {len(data['broadcast_channels'])})")
            channels_list = data['broadcast_channels'].keys() if isinstance(data['broadcast_channels'], dict) else data['broadcast_channels']
            channels_batch = []
            for cid in channels_list:
                if str(cid).replace('-','').isdigit():
                    channels_batch.append({"channel_id": int(cid)})
                if len(channels_batch) >= BATCH_SIZE:
                    tasks.append(upsert_batch(session, "broadcast_channels", channels_batch, semaphore))
                    channels_batch = []
            if channels_batch: tasks.append(upsert_batch(session, "broadcast_channels", channels_batch, semaphore))

        if 'shared' in data:
            print(f"Migrating shared (Total: {len(data['shared'])})")
            shared_batch = []
            for sid, sdata in data['shared'].items():
                shared_batch.append({"share_id": str(sid), "files": sdata})
                if len(shared_batch) >= BATCH_SIZE:
                    tasks.append(upsert_batch(session, "shared", shared_batch, semaphore))
                    shared_batch = []
            if shared_batch: tasks.append(upsert_batch(session, "shared", shared_batch, semaphore))

        if 'autopost_settings' in data:
            print(f"Migrating autopost_settings (Total: {len(data['autopost_settings'])})")
            ap_settings_batch = []
            for cid, sdata in data['autopost_settings'].items():
                channel_id = 0 if cid == 'schedule' else (int(cid) if sid_valid(cid) else None)
                if channel_id is not None:
                    ap_settings_batch.append({
                        "channel_id": channel_id, 
                        "post_hour": int(sdata.get('hour', 0)) if isinstance(sdata, dict) else 0, 
                        "post_minute": int(sdata.get('minute', 0)) if isinstance(sdata, dict) else 0
                    })
                if len(ap_settings_batch) >= BATCH_SIZE:
                    tasks.append(upsert_batch(session, "autopost_settings", ap_settings_batch, semaphore))
                    ap_settings_batch = []
            if ap_settings_batch: tasks.append(upsert_batch(session, "autopost_settings", ap_settings_batch, semaphore))

        if 'autopost_storage' in data:
            print(f"Migrating autopost_storage (Total: {len(data['autopost_storage'])})")
            ap_storage_batch = []
            for cid, sdata in data['autopost_storage'].items():
                if sid_valid(cid) and isinstance(sdata, dict):
                    ap_storage_batch.append({
                        "channel_id": int(cid),
                        "name": str(sdata.get('name', 'Kênh')),
                        "current_index": int(sdata.get('current_index', 0)),
                        "post_limit": int(sdata.get('post_limit', 1)),
                        "files": sdata.get('files', [])
                    })
                if len(ap_storage_batch) >= BATCH_SIZE:
                    tasks.append(upsert_batch(session, "autopost_storage", ap_storage_batch, semaphore))
                    ap_storage_batch = []
            if ap_storage_batch: tasks.append(upsert_batch(session, "autopost_storage", ap_storage_batch, semaphore))

        if 'autopost_users' in data:
            print(f"Migrating autopost_users (Total: {len(data['autopost_users'])})")
            ap_users_batch = []
            for uid, auth in data['autopost_users'].items():
                if sid_valid(uid):
                    ap_users_batch.append({
                        "user_id": int(uid),
                        "is_authorized": auth and str(auth).lower() != "false"
                    })
                if len(ap_users_batch) >= BATCH_SIZE:
                    tasks.append(upsert_batch(session, "autopost_users", ap_users_batch, semaphore))
                    ap_users_batch = []
            if ap_users_batch: tasks.append(upsert_batch(session, "autopost_users", ap_users_batch, semaphore))

        if 'broadcast_history' in data:
            print(f"Migrating broadcast_history (Total: {len(data['broadcast_history'])})")
            history_batch = []
            for pid, hdata in data['broadcast_history'].items():
                if isinstance(hdata, dict):
                    history_batch.append({
                        "post_id": str(pid),
                        "time": int(hdata.get('time', 0)),
                        "sent_to": hdata.get('sent_to', [])
                    })
                if len(history_batch) >= BATCH_SIZE:
                    tasks.append(upsert_batch(session, "broadcast_history", history_batch, semaphore))
                    history_batch = []
            if history_batch: tasks.append(upsert_batch(session, "broadcast_history", history_batch, semaphore))

        if 'daily_check' in data:
            print(f"Migrating daily_check (Total: {len(data['daily_check'])})")
            daily_batch = []
            for uid, ddata in data['daily_check'].items():
                if sid_valid(uid):
                    last_c = str(ddata.get('last_checked', '')) if isinstance(ddata, dict) else str(ddata)
                    daily_batch.append({"user_id": int(uid), "last_checked": last_c})
                if len(daily_batch) >= BATCH_SIZE:
                    tasks.append(upsert_batch(session, "daily_check", daily_batch, semaphore))
                    daily_batch = []
            if daily_batch: tasks.append(upsert_batch(session, "daily_check", daily_batch, semaphore))

        if 'user_files' in data:
            print(f"Migrating user_files (Total: {len(data['user_files'])})")
            ufile_batch = []
            for uid, fdata in data['user_files'].items():
                if sid_valid(uid):
                    ufile_batch.append({"user_id": int(uid), "files": fdata if isinstance(fdata, list) else []})
                if len(ufile_batch) >= BATCH_SIZE:
                    tasks.append(upsert_batch(session, "user_files", ufile_batch, semaphore))
                    ufile_batch = []
            if ufile_batch: tasks.append(upsert_batch(session, "user_files", ufile_batch, semaphore))

        print("Migrating storage_codes...")
        codes_batch = []
        known_keys = ['IDUser', 'ref', 'broadcast_channels', 'broadcast_history', 
                      'autopost_settings', 'autopost_storage', 'autopost_users', 
                      'daily_check', 'shared', 'users', 'settings']
        for k, v in data.items():
            if k not in known_keys:
                codes_batch.append({"code": str(k), "data": v})
        
        if codes_batch:
            tasks.append(upsert_batch(session, "storage_codes", codes_batch, semaphore))

        print(f"Waiting for {len(tasks)} batches to complete...")
        await asyncio.gather(*tasks)
        print("Migration Completed successfully!")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(upload_data())
