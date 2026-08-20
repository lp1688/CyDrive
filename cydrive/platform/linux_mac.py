import os
import sys
import subprocess
import shutil
from typing import Tuple

class UnixMounter:
    """Automates WebDAV Drive mounting on Linux and macOS."""

    @staticmethod
    def is_linux() -> bool:
        return sys.platform.startswith("linux")

    @staticmethod
    def is_macos() -> bool:
        return sys.platform == "darwin"

    @classmethod
    def get_default_mount_point(cls) -> str:
        """Returns the default local directory to mount CyDrive."""
        user_home = os.path.expanduser("~")
        mount_dir = os.path.join(user_home, "CyDrive")
        os.makedirs(mount_dir, exist_ok=True)
        return mount_dir

    @classmethod
    def mount_drive(cls, mount_path: str = None, webdav_url: str = "http://127.0.0.1:8080") -> Tuple[bool, str]:
        """Mounts WebDAV in Linux (via davfs2/gio) or macOS (via mount_webdav)."""
        if mount_path is None:
            mount_path = cls.get_default_mount_point()

        os.makedirs(mount_path, exist_ok=True)

        # 1. macOS Mounting
        if cls.is_macos():
            cmd = ["mount_webdav", webdav_url, mount_path]
            try:
                res = subprocess.run(cmd, capture_output=True, text=True)
                if res.returncode == 0:
                    return True, f"Mounted CyDrive to {mount_path}"
                else:
                    return False, f"macOS mount error: {res.stderr}"
            except Exception as e:
                return False, f"macOS mount failed: {e}"

        # 2. Linux Mounting
        if cls.is_linux():
            # Check if gio is available (GNOME / Desktop Linux)
            if shutil.which("gio"):
                try:
                    res = subprocess.run(["gio", "mount", webdav_url], capture_output=True, text=True)
                    if res.returncode == 0:
                        return True, f"Mounted CyDrive via GNOME GIO: {webdav_url}"
                except Exception:
                    pass

            # Check if mount.davfs is available
            if shutil.which("mount.davfs"):
                try:
                    cmd = ["mount", "-t", "davfs", webdav_url, mount_path]
                    res = subprocess.run(cmd, capture_output=True, text=True)
                    if res.returncode == 0:
                        return True, f"Mounted CyDrive via davfs2 to {mount_path}"
                except Exception:
                    pass

            # Headless Linux Server
            return True, f"CyDrive active on Linux server (WebDAV: {webdav_url} • Web UI: port 8088)"

        return False, "Unsupported Unix platform."

    @classmethod
    def unmount_drive(cls, mount_path: str = None) -> Tuple[bool, str]:
        """Unmounts the WebDAV directory on Linux/macOS."""
        if mount_path is None:
            mount_path = cls.get_default_mount_point()

        if not os.path.exists(mount_path):
            return True, "Mount path does not exist."

        try:
            if cls.is_macos():
                subprocess.run(["umount", mount_path], capture_output=True, text=True)
            elif cls.is_linux():
                subprocess.run(["fusermount", "-u", mount_path], capture_output=True, text=True)
                subprocess.run(["umount", mount_path], capture_output=True, text=True)
            return True, f"Unmounted {mount_path}"
        except Exception as e:
            return False, f"Unmount failed: {e}"
