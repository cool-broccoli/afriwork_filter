import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# ===========================
# YOUR INFO
# ===========================

load_dotenv()


def start_health_server():
    port = int(os.getenv("PORT", "8080"))

    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ("/", "/health"):
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"ok")
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            return

    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"Health server listening on port {port}")
    return server


def get_required_env(name):
    value = os.getenv(name)
    if value:
        return value
    return None


api_id_value = get_required_env("API_ID")
api_hash = get_required_env("API_HASH")
session_string = get_required_env("SESSION")

if not api_id_value or not api_hash or not session_string:
    print("Missing Telegram environment variables. The bot will stay up for health checks until they are configured.")
    start_health_server()
    while True:
        time.sleep(60)

try:
    api_id = int(api_id_value)
except ValueError as exc:
    raise RuntimeError("API_ID must be an integer") from exc

CHANNEL = "freelance_ethio"

# ===========================
# FILTERS
# ===========================

# Job types we want
GOOD_TYPES = [
    "remote",
    "part-time",
    "contractual",
    "hybrid"
]

# Jobs to ignore
BLOCKED_KEYWORDS = [

    # Accounting
    "accountant",
    "accounting",
    "bookkeeper",
    "finance",

    # Graphic design
    "graphic designer",
    "graphics designer",
    "graphic design",
    "illustrator",

    # Video
    "video editor",
    "video editing",
    "videographer",

    # Social media
    "social media",
    "content creator",
    "content manager",
    "host",
    "tiktok",
    "instagram",
    "youtube",

]

client = TelegramClient(StringSession(session_string), api_id, api_hash)


def normalize_text(text):
    if not text:
        return ""

    return re.sub(r"\s+", " ", text).strip().lower()


def looks_like_job(text):
    if not text:
        return False

    normalized = normalize_text(text)

    return all(marker in normalized for marker in ["job title", "job type", "work location"])


def get_job_title(text):
    m = re.search(r"job title\s*[:\-]\s*(.+)", text, re.I)

    if m:
        return m.group(1).strip().lower()

    return ""


def get_job_type(text):
    m = re.search(r"job type\s*[:\-]\s*(.+)", text, re.I)

    if m:
        return m.group(1).strip().lower()

    return ""


def blocked(title):

    for word in BLOCKED_KEYWORDS:
        if word in title:
            return True

    return False


def wanted(job_type):

    for t in GOOD_TYPES:
        if t in job_type:
            return True

    return False


@client.on(events.NewMessage(chats=CHANNEL, incoming=True))
async def handler(event):
    text = event.raw_text or event.message.message or ""

    if not looks_like_job(text):
        return

    title = get_job_title(text)
    job_type = get_job_type(text)

    if not title or not job_type:
        return

    if blocked(title):
        return

    if not wanted(job_type):
        return

    print(f"Matched -> {title} ({job_type})")

    try:
        me = await client.get_me()
        await client.forward_messages(me, event.message)
        print("Forwarded to Saved Messages")
    except Exception as exc:
        print(f"Forward failed: {exc}")
        try:
            await client.send_message("me", text)
        except Exception as fallback_exc:
            print(f"Fallback send failed: {fallback_exc}")


print("Running... waiting for new messages")
client.start()
client.run_until_disconnected()