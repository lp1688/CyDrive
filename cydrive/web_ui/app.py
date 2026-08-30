import os
import time
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
            middlewares = []
            if getattr(self.config, "web_password", ""):
                @web.middleware
                async def basic_auth_middleware(request, handler):
                    """Requires HTTP Basic authentication on all routes when a password is configured."""
                    auth_header = request.headers.get("Authorization", "")
                    if not self._check_basic_auth(auth_header):
                        return web.Response(
                            status=401,
                            text="401 Unauthorized: CyDrive credentials required.",
                            headers={"WWW-Authenticate": 'Basic realm="CyDrive", charset="UTF-8"'}
                        )
                    return await handler(request)
                middlewares.append(basic_auth_middleware)
            self.app = web.Application(middlewares=middlewares)
            self.runner = None
            self.site = None
            self._setup_routes()
        else:
            self.app = None

    def _check_basic_auth(self, auth_header: str) -> bool:
        import base64
        import secrets
        if not auth_header.startswith("Basic "):
            return False
        try:
            decoded = base64.b64decode(auth_header[6:].strip(), validate=True).decode("utf-8")
            username, _, password = decoded.partition(":")
        except Exception:
            return False
        return (
            secrets.compare_digest(username, self.config.web_username)
            and secrets.compare_digest(password, self.config.web_password)
        )

    @staticmethod
    def _sanitize_filename(filename: Optional[str]) -> Optional[str]:
        """Rejects path traversal and strips directory components from a client-supplied filename."""
        if not filename or not isinstance(filename, str):
            return None
        from urllib.parse import unquote
        # Decode percent-encoding first so obfuscated traversal (%2e%2e%2f, ..%2F) is also caught
        normalized = unquote(filename).replace("\\", "/")
        if any(part == ".." for part in normalized.split("/")):
            return None
        name = normalized.rsplit("/", 1)[-1].strip()
        if not name or name == ".":
            return None
        return name

    def _setup_routes(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        static_dir = os.path.join(current_dir, "static")
        self.template_dir = os.path.join(current_dir, "templates")

        self.app.router.add_get("/", self.index_handler)
        self.app.router.add_get("/api/files", self.get_files_handler)
        self.app.router.add_get("/api/stats", self.get_stats_handler)
        self.app.router.add_post("/api/upload", self.upload_handler)
        self.app.router.add_post("/api/delete", self.delete_handler)
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

    async def delete_handler(self, request):
        try:
            data = await request.json()
            filename = self._sanitize_filename(data.get("filename"))
            if not filename:
                return web.json_response({"error": "Invalid filename"}, status=400)
            
            clean_rel = f"/{filename}"
            self.db.delete_file(clean_rel)

            # Clean cache if any (filename is sanitized to a plain basename above)
            local_path = os.path.join(self.config.cache_path, filename)
            if os.path.exists(local_path):
                try:
                    os.remove(local_path)
                except OSError:
                    pass

            return web.json_response({"success": True, "deleted": filename})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def upload_handler(self, request):
        reader = await request.multipart()
        field = await reader.next()
        if field.name == "file":
            filename = self._sanitize_filename(field.filename)
            if not filename:
                return web.json_response({"error": "Invalid filename"}, status=400)
            
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
                    dest = os.path.join(self.config.cache_path, filename)
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    import shutil
                    shutil.copy2(temp_path, dest)
                    file_size = os.path.getsize(dest)
                    self.db.upsert_file(
                        rel_path=f"/{filename}",
                        name=filename,
                        parent_dir="/",
                        size=file_size,
                        mtime=time.time(),
                        is_uploaded=False,
                        is_cached=True
                    )
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
        filename = self._sanitize_filename(request.match_info.get("filename"))
        if not filename:
            return web.json_response({"error": "Invalid filename"}, status=400)
        rel_path = f"/{filename}"
        file_record = self.db.get_file(rel_path)
        
        local_path = os.path.join(self.config.cache_path, filename)
        
        # 1. If available in local cache/disk, stream directly
        if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
            mime_type, _ = mimetypes.guess_type(local_path)
            mime_type = mime_type or "application/octet-stream"
            return web.FileResponse(local_path, headers={
                "Content-Type": mime_type,
                "Content-Disposition": f'inline; filename="{filename}"'
            })

        # 2. If available on Telegram, stream or hydrate from Telegram cloud
        if file_record and self.telegram_engine and self.telegram_engine.is_connected:
            chunk_count = file_record.get("chunk_count", 1) or 1
            is_encrypted = bool(file_record.get("is_encrypted", 0))

            # If chunked or encrypted, reconstitute to local cache first
            if chunk_count > 1 or is_encrypted:
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                ok = await self.telegram_engine.download_file_record(file_record, local_path)
                if ok and os.path.exists(local_path):
                    mime_type, _ = mimetypes.guess_type(local_path)
                    mime_type = mime_type or "application/octet-stream"
                    return web.FileResponse(local_path, headers={
                        "Content-Type": mime_type,
                        "Content-Disposition": f'inline; filename="{filename}"'
                    })
            else:
                msg_id = file_record.get("telegram_msg_id")
                if msg_id:
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
        from cydrive.config import get_display_ip
        disp_ip = get_display_ip(self.config.web_ui_host)
        print(f"✨ [Web UI] Dashboard active at http://{disp_ip}:{self.config.web_ui_port}")
