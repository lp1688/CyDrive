import os
import io
import time
import threading
from typing import Optional, List
from wsgidav.wsgidav_app import WsgiDAVApp
from wsgidav.dav_provider import DAVProvider, DAVCollection, DAVNonCollection
from wsgidav.dav_error import HTTP_NOT_FOUND, HTTP_FORBIDDEN, DAVError
from cheroot import wsgi

from cydrive.database import MetaDatabase
from cydrive.cache_manager import CacheManager

class VirtualTelegramFile(DAVNonCollection):
    """Virtual File Resource mapped directly to Telegram Cloud."""

    def __init__(self, path: str, environ: dict, file_record: dict, cache_mgr: CacheManager, telegram_engine=None):
        super().__init__(path, environ)
        self.file_record = file_record
        self.cache_mgr = cache_mgr
        self.telegram_engine = telegram_engine

    def get_content_length(self) -> int:
        return self.file_record.get("size", 0)

    def support_content_length(self) -> bool:
        return True

    def get_content_type(self) -> str:
        return self.file_record.get("mime_type") or "application/octet-stream"

    def get_creation_date(self) -> float:
        return self.file_record.get("created_at", time.time())

    def get_last_modified(self) -> float:
        return self.file_record.get("mtime", time.time())

    def get_etag(self) -> str:
        sha = self.file_record.get("sha256")
        if sha:
            return f'"{sha}"'
        mtime = self.file_record.get("mtime", 0)
        size = self.file_record.get("size", 0)
        return f'"{mtime}-{size}"'

    def support_etag(self) -> bool:
        return True

    def support_ranges(self) -> bool:
        return True

    def get_content(self):
        """Streams content on-demand from cache or Telegram cloud."""
        rel_path = self.path
        local_cached = self.cache_mgr.get_local_path(rel_path)

        # If cached locally, stream from disk
        if os.path.exists(local_cached):
            self.cache_mgr.touch(rel_path)
            return open(local_cached, "rb")

        # If not cached locally but exists on Telegram
        msg_id = self.file_record.get("telegram_msg_id")
        if msg_id and self.telegram_engine and self.telegram_engine.is_connected:
            print(f"⚡ [VIRTUAL STREAM] On-demand hydrating {rel_path} from Telegram cloud...")
            self.cache_mgr.evict_lru(self.file_record.get("size", 0))
            
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            success = loop.run_until_complete(
                self.telegram_engine.download_file_by_id(msg_id, local_cached)
            )
            if success and os.path.exists(local_cached):
                return open(local_cached, "rb")

        # Return empty stream fallback
        return io.BytesIO(b"")

    def begin_write(self, content_type=None):
        """Prepares writing new content directly to virtual cache & cloud."""
        rel_path = self.path
        local_cached = self.cache_mgr.get_local_path(rel_path)
        os.makedirs(os.path.dirname(local_cached), exist_ok=True)
        return open(local_cached, "wb")


class VirtualTelegramFolder(DAVCollection):
    """Virtual Folder Resource representing hierarchical directories in Telegram."""

    def __init__(self, path: str, environ: dict, db: MetaDatabase, cache_mgr: CacheManager, telegram_engine=None):
        super().__init__(path, environ)
        self.db = db
        self.cache_mgr = cache_mgr
        self.telegram_engine = telegram_engine

    def get_member_names(self) -> List[str]:
        rel_path = self.path if self.path.startswith("/") else "/" + self.path
        items = self.db.list_dir(parent_dir=rel_path)
        return [item["name"] for item in items]

    def get_member(self, name: str):
        rel_path = os.path.join(self.path, name).replace("\\", "/")
        if not rel_path.startswith("/"):
            rel_path = "/" + rel_path

        item = self.db.get_file(rel_path)
        if not item:
            return None

        if item["is_dir"]:
            return VirtualTelegramFolder(rel_path, self.environ, self.db, self.cache_mgr, self.telegram_engine)
        else:
            return VirtualTelegramFile(rel_path, self.environ, item, self.cache_mgr, self.telegram_engine)

    def support_etag(self) -> bool:
        return False

    def support_ranges(self) -> bool:
        return False

    def create_empty_resource(self, name: str):
        rel_path = os.path.join(self.path, name).replace("\\", "/")
        if not rel_path.startswith("/"):
            rel_path = "/" + rel_path

        self.db.upsert_file(
            rel_path=rel_path,
            name=name,
            parent_dir=self.path,
            size=0,
            mtime=time.time(),
            is_dir=False,
            is_uploaded=False,
            is_cached=True
        )
        item = self.db.get_file(rel_path)
        return VirtualTelegramFile(rel_path, self.environ, item, self.cache_mgr, self.telegram_engine)

    def create_collection(self, name: str):
        rel_path = os.path.join(self.path, name).replace("\\", "/")
        if not rel_path.startswith("/"):
            rel_path = "/" + rel_path

        self.db.upsert_file(
            rel_path=rel_path,
            name=name,
            parent_dir=self.path,
            size=0,
            mtime=time.time(),
            is_dir=True,
            is_uploaded=True,
            is_cached=True
        )
        return VirtualTelegramFolder(rel_path, self.environ, self.db, self.cache_mgr, self.telegram_engine)


class PureVirtualTelegramProvider(DAVProvider):
    """Pure Virtual WebDAV Provider communicating directly with Telegram & SQLite VFS."""

    def __init__(self, db: MetaDatabase, cache_mgr: CacheManager, telegram_engine=None):
        super().__init__()
        self.db = db
        self.cache_mgr = cache_mgr
        self.telegram_engine = telegram_engine

    def get_resource_inst(self, path: str, environ: dict):
        clean_path = "/" + path.strip("/") if path.strip("/") else "/"
        if clean_path == "/":
            return VirtualTelegramFolder("/", environ, self.db, self.cache_mgr, self.telegram_engine)

        item = self.db.get_file(clean_path)
        if not item:
            # Check if parent exists
            parent = "/" + os.path.dirname(clean_path).strip("/") if os.path.dirname(clean_path).strip("/") else "/"
            name = os.path.basename(clean_path)
            parent_res = self.db.get_file(parent)
            if parent_res or parent == "/":
                return None
            return None

        if item["is_dir"]:
            return VirtualTelegramFolder(clean_path, environ, self.db, self.cache_mgr, self.telegram_engine)
        else:
            return VirtualTelegramFile(clean_path, environ, item, self.cache_mgr, self.telegram_engine)


class CyWebDAVServer:
    """Manages the Pure Virtual WebDAV server engine."""

    def __init__(self, root_path: str, host: str = "127.0.0.1", port: int = 8080, db: Optional[MetaDatabase] = None, cache_mgr: Optional[CacheManager] = None, telegram_engine=None):
        self.root_path = os.path.abspath(root_path)
        self.host = host
        self.port = port
        self.db = db
        self.cache_mgr = cache_mgr or CacheManager()
        self.telegram_engine = telegram_engine
        self.server = None
        self._thread = None
        os.makedirs(self.root_path, exist_ok=True)

    def _create_app(self):
        config = {
            "host": self.host,
            "port": self.port,
            "provider_mapping": {
                "/": PureVirtualTelegramProvider(self.db, self.cache_mgr, self.telegram_engine) if self.db else self.root_path
            },
            "simple_dc": {"user_mapping": {"*": True}},
            "verbose": 1,
            "enable_cors": True,
            "dir_browser": {
                "enable": True,
                "response_trailer": "Powered by Cynet CyDrive (https://cynetx.ir)"
            }
        }
        return WsgiDAVApp(config)

    def start(self, blocking: bool = False):
        """Starts the WebDAV server."""
        app = self._create_app()
        self.server = wsgi.Server(bind_addr=(self.host, self.port), wsgi_app=app)
        print(f"🌐 [WebDAV] Pure Virtual Cloud Drive running at http://{self.host}:{self.port}")
        
        if blocking:
            self.server.start()
        else:
            self._thread = threading.Thread(target=self.server.start, daemon=True)
            self._thread.start()

    def stop(self):
        """Stops the WebDAV server."""
        if self.server:
            self.server.stop()
