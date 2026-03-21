import os
import json
import requests
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

def upsert_table(table, data):
    if not data: return
    batch_size = 500
    for i in range(0, len(data), batch_size):
        batch = data[i:i+batch_size]
        endpoint = f"{url}/rest/v1/{table}"
        try:
            resp = requests.post(endpoint, json=batch, headers=headers)
            if resp.status_code not in [200, 201]:
                print(f"Error inserting into {table}: {resp.status_code} - {resp.text}")
            else:
                print(f"  -> Inserted {len(batch)} rows into {table}")
        except Exception as e:
            print(f"Request failed for {table}: {e}")

def upload_data():
    if not os.path.exists('firebase_backup.json'):
        print("firebase_backup.json not found!")
        return

    with open('firebase_backup.json', encoding='utf-8') as f:
        data = json.load(f)

    print("Starting data migration to Supabase via requests...")

    if 'IDUser' in data:
        print("Migrating IDUser...")
        users_batch = []
        for uid, udata in data['IDUser'].items():
            if not uid.replace('-','').isdigit(): continue
            users_batch.append({
                "user_id": int(uid),
                "first_name": str(udata.get('first_name', '')),
                "username": str(udata.get('username', '')),
                "from_source": str(udata.get('from_source', '')),
                "joined_date": udata.get('joined_date') if udata.get('joined_date') else None
            })
        upsert_table("IDUser", users_batch)

    if 'ref' in data:
        print("Migrating ref (credits)...")
        ref_batch = [{"user_id": int(uid), "credit": int(credit)} for uid, credit in data['ref'].items() if uid.replace('-','').isdigit()]
        upsert_table("ref", ref_batch)

    if 'broadcast_channels' in data:
        print("Migrating broadcast_channels...")
        if isinstance(data['broadcast_channels'], dict):
            channels_batch = [{"channel_id": int(cid)} for cid in data['broadcast_channels'].keys() if str(cid).replace('-','').isdigit()]
        else:
            channels_batch = [{"channel_id": int(cid)} for cid in data['broadcast_channels'] if str(cid).replace('-','').isdigit()]
        upsert_table("broadcast_channels", channels_batch)

    if 'shared' in data:
        print("Migrating shared...")
        shared_batch = [{"share_id": str(sid), "files": sdata} for sid, sdata in data['shared'].items()]
        upsert_table("shared", shared_batch)

    print("Migrating storage_codes...")
    codes_batch = []
    known_keys = ['IDUser', 'ref', 'broadcast_channels', 'broadcast_history', 
                  'autopost_settings', 'autopost_storage', 'autopost_users', 
                  'daily_check', 'shared', 'users', 'settings']
    for k, v in data.items():
        if k not in known_keys:
            codes_batch.append({"code": str(k), "data": v})
    upsert_table("storage_codes", codes_batch)

    print("Migration Completed successfully!")

if __name__ == "__main__":
    upload_data()
