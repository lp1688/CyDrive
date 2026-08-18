import os
import time
import threading
import queue
from typing import Callable, Optional
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent, FileMovedEvent
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False
    Observer = object
    FileSystemEventHandler = object

class FileSyncHandler(FileSystemEventHandler):
    """Handles real-time file system modification events with debouncing."""

    def __init__(self, watch_dir: str, change_queue: queue.Queue):
        super().__init__()
        self.watch_dir = os.path.abspath(watch_dir)
        self.change_queue = change_queue
        self._last_events = {}

    def _normalize_rel_path(self, path: str) -> str:
        rel = os.path.relpath(path, self.watch_dir)
        return "/" + rel.replace("\\", "/").lstrip("/")

    def on_created(self, event):
        if not event.is_directory:
            self._handle_file(event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            self._handle_file(event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            self._handle_file(event.dest_path)

    def _handle_file(self, file_path: str):
        # Ignore temporary files
        base = os.path.basename(file_path)
        if base.startswith("~") or base.startswith(".") or base.endswith(".tmp") or base.endswith(".crdownload"):
            return

        now = time.time()
        last_time = self._last_events.get(file_path, 0)
        if now - last_time < 2.0:  # 2 second debounce
            return

        self._last_events[file_path] = now
        self.change_queue.put(file_path)

class DriveWatcher:
    """Manages Watchdog background observer and file-lock verification."""

    def __init__(self, watch_dir: str, on_file_ready: Callable[[str, str], None]):
        self.watch_dir = os.path.abspath(watch_dir)
        self.on_file_ready = on_file_ready
        self.change_queue = queue.Queue()
        self.observer = Observer()
        self.handler = FileSyncHandler(self.watch_dir, self.change_queue)
        self._running = False
        self._worker_thread = threading.Thread(target=self._process_queue, daemon=True)

    def is_file_ready(self, file_path: str, retries: int = 5, delay: float = 0.5) -> bool:
        """Verifies that the file copy is finished and the OS lock is released."""
        if not os.path.exists(file_path):
            return False

        for _ in range(retries):
            try:
                # Check if file size is stable
                size1 = os.path.getsize(file_path)
                time.sleep(delay)
                size2 = os.path.getsize(file_path)
                if size1 == size2 and size1 > 0:
                    with open(file_path, "r+b"):
                        return True
            except (IOError, PermissionError):
                time.sleep(delay)
        return False

    def _process_queue(self):
        while self._running:
            try:
                file_path = self.change_queue.get(timeout=1.0)
                if self.is_file_ready(file_path):
                    rel_path = "/" + os.path.relpath(file_path, self.watch_dir).replace("\\", "/").lstrip("/")
                    self.on_file_ready(file_path, rel_path)
                self.change_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"⚠️ [Watcher Error] {e}")

    def start(self):
        """Starts watching the directory for file changes."""
        if not HAS_WATCHDOG:
            print("⚠️ [Watcher] 'watchdog' library not installed. Install with `pip install -r requirements.txt`.")
            return

        self._running = True
        self.observer.schedule(self.handler, self.watch_dir, recursive=True)
        self.observer.start()
        self._worker_thread.start()
        print(f"👁️ [Watcher] Active & Monitoring: {self.watch_dir}")

    def stop(self):
        """Stops the observer."""
        self._running = False
        if HAS_WATCHDOG and hasattr(self.observer, "stop"):
            self.observer.stop()
            self.observer.join()
