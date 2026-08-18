import os
import asyncio
import time
from typing import Optional, Callable, Dict, Any, List
from telethon import TelegramClient, events
from telethon.tl.types import DocumentAttributeFilename, MessageMediaDocument

from cydrive.config import CyDriveConfig
from cydrive.database import MetaDatabase
from cydrive.chunker import FileChunker

class TelegramSyncEngine:
    """Telethon MTProto Engine for fast uploads, downloads, and bot commands."""

    def __init__(self, config: CyDriveConfig, db: MetaDatabase):
        self.config = config
        self.db = db
        self.client = TelegramClient(
            "cynet_bot_session",
            config.api_id,
            config.api_hash
        )
        self.is_connected = False
        self.on_file_received_callback: Optional[Callable] = None

    async def start(self):
        """Starts the Telethon client with bot token."""
        await self.client.start(bot_token=self.config.bot_token)
        self.is_connected = True
        self._register_handlers()
        me = await self.client.get_me()
        print(f"🤖 [Telegram] Logged in as @{me.username} (ID: {me.id})")

    def _register_handlers(self):
        """Registers message handlers and bot commands."""
        
        # 1. Handle incoming files from Telegram
        @self.client.on(events.NewMessage(chats=self.config.chat_id))
        async def handle_incoming(event):
            if event.message and event.message.media:
                await self._process_incoming_file(event)
            elif event.message and event.message.text:
                await self._process_bot_command(event)

    async def _process_incoming_file(self, event):
        """Processes and downloads media sent directly into Telegram chat."""
        msg = event.message
        file_name = None

        if hasattr(msg, "file") and msg.file:
            file_name = getattr(msg.file, "name", None)

        if not file_name:
            ext = getattr(msg.file, "ext", ".bin") if hasattr(msg, "file") else ".bin"
            file_name = f"Telegram_File_{msg.id}{ext}"

        rel_path = f"/{file_name}"
        dest_path = os.path.join(self.config.storage_path, file_name)
        
        print(f"📥 [SYNC] Incoming Telegram file: {file_name} ...")
        await msg.download_media(file=dest_path)
        
        size = os.path.getsize(dest_path) if os.path.exists(dest_path) else 0
        self.db.upsert_file(
            rel_path=rel_path,
            name=file_name,
            parent_dir="/",
            size=size,
            mtime=time.time(),
            telegram_msg_id=msg.id,
            is_uploaded=True,
            is_cached=True
        )

        try:
            await event.respond(f"💾 File **'{file_name}'** ({size // 1024} KB) synced to CyDrive Drive ({self.config.drive_letter})!")
        except Exception:
            pass

    async def _process_bot_command(self, event):
        """Processes interactive bot commands from the user."""
        text = event.message.text.strip()
        
        if text.startswith("/start") or text.startswith("/help"):
            help_text = (
                "🚀 **CyDrive Cloud Storage Engine v2.0**\n"
                "Developed by Cynet Security Team (https://cynetx.ir)\n\n"
                "**Available Commands:**\n"
                "📊 `/stats` - View cloud storage analytics\n"
                "🔍 `/search <query>` - Search files in your drive\n"
                "📥 `/get <filename>` - Download a file directly\n"
                "ℹ️ Send any file to this chat to save it to your Windows Drive!"
            )
            await event.respond(help_text)

        elif text.startswith("/stats"):
            stats = self.db.get_stats()
            size_mb = stats["total_bytes"] / (1024 * 1024)
            size_gb = size_mb / 1024
            
            size_str = f"{size_gb:.2f} GB" if size_gb >= 1 else f"{size_mb:.2f} MB"
            stats_text = (
                "📊 **CyDrive Storage Statistics**\n\n"
                f"📁 **Total Files:** `{stats['total_files']}`\n"
                f"🗂️ **Total Folders:** `{stats['total_dirs']}`\n"
                f"☁️ **Total Cloud Storage:** `{size_str}`\n"
                f"✅ **Synced Files:** `{stats['uploaded_files']}`\n"
                f"🖥️ **Mapped Windows Drive:** `{self.config.drive_letter}`"
            )
            await event.respond(stats_text)

        elif text.startswith("/search"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                await event.respond("⚠️ Please specify a search keyword. e.g. `/search document.pdf`")
                return
            query = parts[1]
            results = self.db.search_files(query)
            if not results:
                await event.respond(f"🔍 No files found matching: `{query}`")
            else:
                lines = ["🔍 **Search Results:**\n"]
                for item in results[:15]:
                    icon = "📁" if item["is_dir"] else "📄"
                    size_kb = item["size"] // 1024
                    lines.append(f"{icon} `{item['name']}` ({size_kb} KB)")
                await event.respond("\n".join(lines))

    async def upload_file(self, local_path: str, rel_path: str, progress_callback: Optional[Callable] = None) -> Optional[int]:
        """Uploads a local file to Telegram and records it in database."""
        if not os.path.exists(local_path):
            return None

        file_size = os.path.getsize(local_path)
        file_name = os.path.basename(local_path)

        caption = (
            f"🚀 **CyDrive Cloud Backup**\n"
            f"📁 Path: `{rel_path}`\n"
            f"📦 Size: `{file_size // 1024} KB`"
        )

        try:
            msg = await self.client.send_file(
                self.config.chat_id,
                local_path,
                caption=caption,
                progress_callback=progress_callback
            )
            return msg.id
        except Exception as e:
            print(f"❌ [Telegram Upload Error] Failed to upload {file_name}: {e}")
            return None

    async def download_file_by_id(self, msg_id: int, dest_path: str, progress_callback: Optional[Callable] = None) -> bool:
        """Downloads a specific message media by its Telegram message ID."""
        try:
            msg = await self.client.get_messages(self.config.chat_id, ids=msg_id)
            if msg and msg.media:
                await msg.download_media(file=dest_path, progress_callback=progress_callback)
                return True
        except Exception as e:
            print(f"❌ [Telegram Download Error] Failed to download msg {msg_id}: {e}")
        return False
