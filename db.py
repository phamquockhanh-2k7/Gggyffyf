import aiohttp
import config

headers = {
    "apikey": config.SUPABASE_KEY,
    "Authorization": f"Bearer {config.SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# generic GET
async def _get(table, filter_str=None):
    url = f"{config.SUPABASE_URL}/rest/v1/{table}"
    if filter_str:
        url += f"?{filter_str}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                return await resp.json()
            return None

# generic POST/UPSERT
async def _upsert(table, data):
    url = f"{config.SUPABASE_URL}/rest/v1/{table}"
    upsert_headers = headers.copy()
    upsert_headers["Prefer"] = "resolution=merge-duplicates"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=data if isinstance(data, list) else [data], headers=upsert_headers) as resp:
            return resp.status in [200, 201]

# generic DELETE
async def _delete(table, filter_str):
    url = f"{config.SUPABASE_URL}/rest/v1/{table}?{filter_str}"
    async with aiohttp.ClientSession() as session:
        async with session.delete(url, headers=headers) as resp:
            return resp.status in [200, 204]

# ==== CREDITS ====
async def get_credits(user_id):
    data = await _get("ref", f"user_id=eq.{user_id}")
    return data[0]['credit'] if data else None

async def set_credits(user_id, amount):
    return await _upsert("ref", {"user_id": user_id, "credit": amount})

async def check_daily_task_status(user_id):
    data = await _get("daily_check", f"user_id=eq.{user_id}")
    return data[0]['last_checked'] if data else None

async def mark_daily_task_done(user_id, today_str):
    return await _upsert("daily_check", {"user_id": user_id, "last_checked": today_str})

# ==== STORAGE ====
async def get_shared(alias):
    data = await _get("shared", f"share_id=eq.{alias}")
    return data[0]['files'] if data else None

async def set_shared(alias, files):
    return await _upsert("shared", {"share_id": str(alias), "files": files})

async def get_storage_code(alias):
    data = await _get("storage_codes", f"code=eq.{alias}")
    return data[0]['data'] if data else None

async def set_storage_code(alias, files):
    return await _upsert("storage_codes", {"code": str(alias), "data": files})

# ==== AUTOPOST ====
async def get_autopost_storage():
    data = await _get("autopost_storage")
    if not data: return {}
    return {str(item['channel_id']): item for item in data}

async def update_autopost_storage(channel_id, data):
    row = {"channel_id": int(channel_id), **data}
    return await _upsert("autopost_storage", row)

async def delete_autopost_storage(channel_id):
    return await _delete("autopost_storage", f"channel_id=eq.{channel_id}")

async def get_autopost_settings():
    data = await _get("autopost_settings")
    if not data: return {}
    return {str(item['channel_id']): {"hour": item['post_hour'], "minute": item['post_minute']} for item in data}

async def update_autopost_settings(channel_id, hour, minute):
    return await _upsert("autopost_settings", {"channel_id": channel_id, "post_hour": hour, "post_minute": minute})

async def delete_autopost_settings(channel_id):
    return await _delete("autopost_settings", f"channel_id=eq.{channel_id}")
    
async def get_autopost_users():
    data = await _get("autopost_users")
    if not data: return {}
    return {str(item['user_id']): item['is_authorized'] for item in data}

async def update_autopost_users(user_data):
    # expect {user_id: bool}
    batch = [{"user_id": int(uid), "is_authorized": auth} for uid, auth in user_data.items()]
    return await _upsert("autopost_users", batch)

# ==== BROADCAST ====
async def get_broadcast_channels():
    data = await _get("broadcast_channels")
    return {str(item['channel_id']): f"Kênh {item['channel_id']}" for item in (data or [])}

async def add_broadcast_channel(channel_id):
    return await _upsert("broadcast_channels", {"channel_id": channel_id})

async def remove_broadcast_channel(channel_id):
    return await _delete("broadcast_channels", f"channel_id=eq.{channel_id}")

async def get_broadcast_history():
    data = await _get("broadcast_history")
    if not data: return {}
    return {str(item['post_id']): {"time": item['time'], "sent_to": item['sent_to']} for item in data}

async def delete_broadcast_history(post_id):
    return await _delete("broadcast_history", f"post_id=eq.{post_id}")

async def update_broadcast_history(post_id, time, sent_to):
    return await _upsert("broadcast_history", {"post_id": str(post_id), "time": time, "sent_to": sent_to})

# ==== USERS ====
async def get_all_users():
    data = await _get("IDUser")
    if not data: return {}
    return {str(item['user_id']): {
        "first_name": item.get('first_name'),
        "username": item.get('username'),
        "from_source": item.get('from_source'),
        "joined_date": item.get('joined_date')
    } for item in data}

async def add_user(user_id, data):
    row = {"user_id": user_id, **data}
    return await _upsert("IDUser", row)
