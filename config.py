import os
from dotenv import load_dotenv

# Load file .env nếu chạy local (trên Koyeb nó tự nhận biến hệ thống)
load_dotenv()

def get_list(key):
    val = os.getenv(key, "")
    return [x.strip() for x in val.split(',') if x.strip()]

# 1. LIST TOKENS
MAIN_BOT_TOKENS = get_list("LIST_TOKEN_MAIN")
BROADCAST_BOT_TOKENS = get_list("LIST_TOKEN_BROADCAST")
SOS_BOT_TOKENS = get_list("LIST_TOKEN_SOS")

# 2. DATABASE & SYSTEM
FIREBASE_URL = os.getenv("FIREBASE_URL", "")
MAIN_CHANNEL_USERNAME = os.getenv("MAIN_CHANNEL_USERNAME", "@hoahocduong_vip")
JOIN_LINK_CHANNEL = os.getenv("JOIN_LINK_CHANNEL", "")

# 3. LINKS QUẢNG CÁO
REF_LINK_1 = os.getenv("REF_LINK_1", "")
REF_LINK_2 = os.getenv("REF_LINK_2", "")

# 4. API RÚT GỌN
# VuotLink.
API_KEY_VUOTLINK = os.getenv("API_KEY_VUOTLINK")
DOMAIN_MASK_VUOTLINK = os.getenv("DOMAIN_MASK_VUOTLINK")
URL_API_VUOTLINK = "https://vuotlink.vip/api" # URL gốc của API (ít thay đổi nên để đây cũng được)
ORIGIN_DOMAIN_VUOTLINK = "vuotlink.vip"

# LinkX
API_KEY_LINKX = os.getenv("API_KEY_LINKX")
DOMAIN_MASK_LINKX = os.getenv("DOMAIN_MASK_LINKX")
URL_API_LINKX = "https://linkx.me/api"
ORIGIN_DOMAIN_LINKX = "linkx.me"

# AnonLink
API_KEY_ANON = os.getenv("API_KEY_ANON")
DOMAIN_MASK_ANON = os.getenv("DOMAIN_MASK_ANON")
URL_API_ANON = "https://anonlink.io/api"
ORIGIN_DOMAIN_ANON = "anonlink.io"
