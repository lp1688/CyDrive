import os
import mimetypes

try:
    from aiohttp import web
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False
from cydrive.config import CyDriveConfig
from cydrive.database import MetaDatabase

class CyWebDashboard:
    """Lightweight aiohttp Web Dashboard for CyDrive."""

    def __init__(self, config: CyDriveConfig, db: MetaDatabase):
        self.config = config
        self.db = db
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
        return web.json_response(stats)

    async def upload_handler(self, request):
        reader = await request.multipart()
        field = await reader.next()
        if field.name == "file":
            filename = field.filename
            if not filename:
                return web.json_response({"error": "No filename"}, status=400)
            
            dest = os.path.join(self.config.storage_path, filename)
            with open(dest, "wb") as f:
                while chunk := await field.read_chunk():
                    f.write(chunk)
            
            return web.json_response({"success": True, "filename": filename})
        return web.json_response({"error": "Invalid upload"}, status=400)

    async def download_handler(self, request):
        filename = request.match_info.get("filename")
        file_path = os.path.join(self.config.storage_path, filename)
        if not os.path.exists(file_path):
            return web.Response(text="File not found", status=404)

        mime_type, _ = mimetypes.guess_type(file_path)
        mime_type = mime_type or "application/octet-stream"
        
        return web.FileResponse(file_path, headers={
            "Content-Type": mime_type,
            "Content-Disposition": f'inline; filename="{filename}"'
        })

    async def start(self):
        if not HAS_AIOHTTP:
            print("⚠️ [Web UI] 'aiohttp' library not installed. Install with `pip install -r requirements.txt`.")
            return

        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.config.web_ui_host, self.config.web_ui_port)
        await self.site.start()
        print(f"✨ [Web UI] Dashboard active at http://{self.config.web_ui_host}:{self.config.web_ui_port}")
