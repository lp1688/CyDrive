import os
import json
import time
import asyncio
import threading
from telethon import TelegramClient, events
from wsgidav.wsgidav_app import WsgiDAVApp
from cheroot import wsgi

CONFIG_FILE = "config.json"
STORAGE_PATH = os.path.abspath("./Telegram_Drive")
os.makedirs(STORAGE_PATH, exist_ok=True)

# 1. Cynet Public API Credentials
API_ID = 6
API_HASH = "eb06d4abfb49dc3eeb1aeb98ae0f581e"

def print_banner():
    print("=" * 65)
    print("  🚀 CYNET TG-DRIVE: Unlimited Cloud Storage Engine v1.0")
    print("  🌐 Developed by Cynet Security Team (cynetx.ir)")
    print("  🔄 Two-Way File Synchronization: Windows PC <-> Telegram")
    print("=" * 65)

# 2. Load or Prompt for User Credentials
def load_or_create_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                if cfg.get("bot_token") and cfg.get("chat_id"):
                    return cfg
        except Exception:
            pass

    print("\n[+] First-Time Configuration Setup:")
    bot_token = input("👉 Enter Telegram Bot Token (from @BotFather): ").strip()
    chat_id_input = input("👉 Enter your Telegram User/Chat ID: ").strip()

    try:
        chat_id = int(chat_id_input)
    except ValueError:
        chat_id = chat_id_input

    cfg = {
        "bot_token": bot_token,
        "chat_id": chat_id
    }

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4)
    print("✅ Configuration successfully saved to config.json\n")
    return cfg

print_banner()
config_data = load_or_create_config()
BOT_TOKEN = config_data["bot_token"]
TARGET_CHAT_ID = config_data["chat_id"]

client = TelegramClient("cynet_bot_session", API_ID, API_HASH)
synced_files = set()

# 3. Incoming Telegram File Handler (Telegram -> Windows Drive)
@client.on(events.NewMessage(chats=TARGET_CHAT_ID))
async def incoming_file_handler(event):
    if event.message and event.message.media:
        msg_id = event.message.id
        file_name = getattr(event.message.file, 'name', None)
        if not file_name:
            ext = getattr(event.message.file, 'ext', '.jpg')
            file_name = f"Telegram_File_{msg_id}{ext}"
            
        destination = os.path.join(STORAGE_PATH, file_name)
        print(f"\n📥 [DOWNLOAD] Incoming file from Telegram: {file_name} ...")
        
        # Download media to local drive
        await event.message.download_media(file=destination)
        synced_files.add(file_name)
        
        print(f"✅ [DOWNLOAD] Successfully saved to Windows Drive (Y:): {file_name}\n")
        try:
            await event.respond(f"💾 File '{file_name}' was successfully saved to your Windows Drive (Y:)!")
        except Exception:
            pass

# 4. Outgoing File Worker (Windows Drive -> Telegram Cloud)
async def upload_worker():
    await client.start(bot_token=BOT_TOKEN)
    me = await client.get_me()
    print(f"\n✅ Cynet Cloud Bot Active: @{me.username}")
    print(f"📁 Windows Drive Mount Path: {STORAGE_PATH}")
    print(f"🎯 Target Sync Chat ID: {TARGET_CHAT_ID}\n")

    # Index existing files to prevent duplicate upload
    for root, dirs, files in os.walk(STORAGE_PATH):
        for file in files:
            synced_files.add(file)

    while True:
        try:
            for root, dirs, files in os.walk(STORAGE_PATH):
                for file in files:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, STORAGE_PATH)
                    
                    if file not in synced_files and os.path.getsize(file_path) > 0:
                        print(f"📤 [UPLOAD] Uploading to Telegram Cloud: {file} ...")
                        try:
                            await client.send_file(
                                TARGET_CHAT_ID, 
                                file_path, 
                                caption=f"💾 Saved from Windows Drive (Y:)\n📁 File: {file}"
                            )
                            synced_files.add(file)
                            print(f"✅ [UPLOAD] Successfully uploaded to Telegram: {file}\n")
                        except Exception as e:
                            print(f"⚠️ [UPLOAD ERROR] Failed to upload {file}: {e}")
        except Exception as e:
            pass
        await asyncio.sleep(3)

def start_telegram_sync():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    client.add_event_handler(incoming_file_handler)
    loop.run_until_complete(upload_worker())

# Run Telegram background sync thread
sync_thread = threading.Thread(target=start_telegram_sync, daemon=True)
sync_thread.start()

# 5. Start Windows WebDAV Network Drive Server
webdav_config = {
    "host": "127.0.0.1",
    "port": 8080,
    "provider_mapping": {"/": STORAGE_PATH},
    "simple_dc": {"user_mapping": {"*": True}},
    "verbose": 1,
}

app = WsgiDAVApp(webdav_config)
server = wsgi.Server(bind_addr=(webdav_config["host"], webdav_config["port"]), wsgi_app=app)

print("=" * 65)
print("  🎉 CYNET TG-DRIVE IS LIVE ON http://127.0.0.1:8080")
print("  👉 Map Network Drive in 'This PC' with drive letter Y: or Z:")
print("=" * 65 + "\n")

try:
    server.start()
except KeyboardInterrupt:
    server.stop()
