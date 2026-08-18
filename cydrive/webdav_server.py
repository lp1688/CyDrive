import os
import threading
from wsgidav.wsgidav_app import WsgiDAVApp
from cheroot import wsgi

class CyWebDAVServer:
    """Manages the local WebDAV server engine."""

    def __init__(self, root_path: str, host: str = "127.0.0.1", port: int = 8080):
        self.root_path = os.path.abspath(root_path)
        self.host = host
        self.port = port
        self.server = None
        self._thread = None
        os.makedirs(self.root_path, exist_ok=True)

    def _create_app(self):
        config = {
            "host": self.host,
            "port": self.port,
            "provider_mapping": {"/": self.root_path},
            "simple_dc": {"user_mapping": {"*": True}},  # Allow anonymous local access
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
        
        print(f"🌐 [WebDAV] Server running at http://{self.host}:{self.port}")
        
        if blocking:
            self.server.start()
        else:
            self._thread = threading.Thread(target=self.server.start, daemon=True)
            self._thread.start()

    def stop(self):
        """Stops the WebDAV server."""
        if self.server:
            self.server.stop()
