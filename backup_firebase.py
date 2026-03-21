import urllib.request
import json
import os

url = "https://bot-telegram-99852-default-rtdb.firebaseio.com/.json"
print("Downloading Firebase Data...")

try:
    with urllib.request.urlopen(url) as response:
        data = json.loads(response.read().decode('utf-8'))
        with open("firebase_backup.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("Data successfully backed up to firebase_backup.json! Data secured locally.")
except Exception as e:
    print(f"Error: {e}")
