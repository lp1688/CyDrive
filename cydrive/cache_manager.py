import os
import time
from typing import Optional, List

class CacheManager:
    """Smart On-Demand LRU Cache Manager for CyDrive."""

    def __init__(self, cache_dir: str = "./Telegram_Cache", limit_gb: int = 20):
        self.cache_dir = os.path.abspath(cache_dir)
        self.limit_bytes = limit_gb * 1024 * 1024 * 1024
        os.makedirs(self.cache_dir, exist_ok=True)

    def get_local_path(self, rel_path: str) -> str:
        """Returns the absolute path inside the cache for a given relative path."""
        # Sanitize relative path
        clean_rel = rel_path.lstrip("/\\")
        full_path = os.path.join(self.cache_dir, clean_rel)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        return full_path

    def is_cached(self, rel_path: str) -> bool:
        """Checks if a file exists locally and has non-zero size."""
        local_path = self.get_local_path(rel_path)
        return os.path.exists(local_path) and os.path.getsize(local_path) > 0

    def touch(self, rel_path: str):
        """Updates the access time (atime) of a cached file for LRU tracking."""
        local_path = self.get_local_path(rel_path)
        if os.path.exists(local_path):
            try:
                os.utime(local_path, None)
            except Exception:
                pass

    def get_current_cache_size(self) -> int:
        """Calculates total size of cached files in bytes."""
        total_size = 0
        for root, _, files in os.walk(self.cache_dir):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    total_size += os.path.getsize(fp)
                except OSError:
                    pass
        return total_size

    def evict_lru(self, bytes_needed: int = 0):
        """Evicts oldest accessed files if cache limit is exceeded."""
        current_size = self.get_current_cache_size()
        if (current_size + bytes_needed) <= self.limit_bytes:
            return

        # Collect all files with their atime and size
        file_entries = []
        for root, _, files in os.walk(self.cache_dir):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    stat = os.stat(fp)
                    file_entries.append((stat.st_atime, stat.st_size, fp))
                except OSError:
                    pass

        # Sort by access time ascending (oldest first)
        file_entries.sort(key=lambda x: x[0])

        for atime, size, fp in file_entries:
            if (current_size + bytes_needed) <= self.limit_bytes:
                break
            try:
                os.remove(fp)
                current_size -= size
            except OSError:
                pass

    def clear_all(self):
        """Clears all cached files."""
        for root, dirs, files in os.walk(self.cache_dir, topdown=False):
            for f in files:
                try:
                    os.remove(os.path.join(root, f))
                except OSError:
                    pass
            for d in dirs:
                try:
                    os.rmdir(os.path.join(root, d))
                except OSError:
                    pass
