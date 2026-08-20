import os
import mimetypes
import tempfile
from typing import Optional

try:
    from aiohttp import web
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False
from cydrive.config import CyDriveConfig
from cydrive.database import MetaDatabase

class CyWebDashboard:
    """Lightweight aiohttp Pure Virtual Web Dashboard for CyDrive."""

    def __init__(self, config: CyDriveConfig, db: MetaDatabase, telegram_engine=None):
        self.config = config
        self.db = db
        self.telegram_engine = telegram_engine
        if HAS_AIOHTTP:
            self.app = web.Application()
            self.runner = None
            self.site = None
            self._setup_routes()
        else:
            self.app = None

    def _setup_routes(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        static_dir = os.path.join(current_dir, "static")
        self.template_dir = os.path.join(current_dir, "templates")

        self.app.router.add_get("/", self.index_handler)
        self.app.router.add_get("/api/files", self.get_files_handler)
        self.app.router.add_get("/api/stats", self.get_stats_handler)
        self.app.router.add_post("/api/upload", self.upload_handler)
        self.app.router.add_get("/api/download/{filename}", self.download_handler)
        self.app.router.add_static("/static/", path=static_dir, name="static")

    async def index_handler(self, request):
        html_file = os.path.join(self.template_dir, "index.html")
        with open(html_file, "r", encoding="utf-8") as f:
            content = f.read()
        return web.Response(text=content, content_type="text/html")

    async def get_files_handler(self, request):
        files = self.db.list_all_files()
        return web.json_response(files)

    async def get_stats_handler(self, request):
        stats = self.db.get_stats()
        stats.update({
            "drive_letter": self.config.drive_letter,
            "webdav_host": self.config.webdav_host,
            "webdav_port": self.config.webdav_port,
            "webdav_url": f"http://{self.config.webdav_host}:{self.config.webdav_port}",
            "chat_id": self.config.chat_id,
            "is_configured": bool(self.config.bot_token and self.config.bot_token != "NOT_CONFIGURED")
        })
        return web.json_response(stats)

    async def upload_handler(self, request):
        reader = await request.multipart()
        field = await reader.next()
        if field.name == "file":
            filename = field.filename
            if not filename:
                return web.json_response({"error": "No filename"}, status=400)
            
            ext = os.path.splitext(filename)[1]
            temp_fd, temp_path = tempfile.mkstemp(prefix="cydrive_up_", suffix=ext)
            try:
                with open(temp_path, "wb") as f:
                    while chunk := await field.read_chunk():
                        f.write(chunk)
                
                # Upload directly to Telegram cloud
                if self.telegram_engine and self.telegram_engine.is_connected:
                    await self.telegram_engine.upload_file(temp_path, f"/{filename}")
                else:
                    # Fallback to local storage if telegram not connected
                    dest = os.path.join(self.config.storage_path, filename)
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    import shutil
                    shutil.copy2(temp_path, dest)
            finally:
                os.close(temp_fd)
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass
            
            return web.json_response({"success": True, "filename": filename})
        return web.json_response({"error": "Invalid upload"}, status=400)

    async def download_handler(self, request):
        filename = request.match_info.get("filename")
        rel_path = f"/{filename}"
        file_record = self.db.get_file(rel_path) or self.db.get_file(filename)
        
        local_path = os.path.join(self.config.storage_path, filename)
        
        # 1. If available in local cache/disk, stream directly
        if os.path.exists(local_path):
            mime_type, _ = mimetypes.guess_type(local_path)
            mime_type = mime_type or "application/octet-stream"
            return web.FileResponse(local_path, headers={
                "Content-Type": mime_type,
                "Content-Disposition": f'inline; filename="{filename}"'
            })

        # 2. If available on Telegram, stream directly from Telegram cloud on-demand
        if file_record and file_record.get("telegram_msg_id") and self.telegram_engine and self.telegram_engine.is_connected:
            msg_id = file_record["telegram_msg_id"]
            msg = await self.telegram_engine.client.get_messages(self.config.chat_id, ids=msg_id)
            if msg and msg.media:
                file_size = file_record.get("size", 0)
                mime_type = file_record.get("mime_type") or mimetypes.guess_type(filename)[0] or "application/octet-stream"
                
                response = web.StreamResponse(
                    status=200,
                    reason='OK',
                    headers={
                        'Content-Type': mime_type,
                        'Content-Disposition': f'inline; filename="{filename}"',
                        'Content-Length': str(file_size)
                    }
                )
                await response.prepare(request)
                
                async for chunk in self.telegram_engine.client.iter_download(msg.media):
                    await response.write(chunk)
                await response.write_eof()
                return response

        return web.Response(text="File not found in CyDrive cloud", status=404)

    async def start(self):
        if not HAS_AIOHTTP:
            print("⚠️ [Web UI] 'aiohttp' library not installed. Install with `pip install -r requirements.txt`.")
            return

        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.config.web_ui_host, self.config.web_ui_port)
        await self.site.start()
        print(f"✨ [Web UI] Dashboard active at http://{self.config.web_ui_host}:{self.config.web_ui_port}")
