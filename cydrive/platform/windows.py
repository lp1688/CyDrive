import os
import sys
import subprocess
import winreg
from typing import Tuple

class WindowsMounter:
    """Automates Windows WebDAV Registry optimization and Drive mapping."""

    REG_PATH = r"SYSTEM\CurrentControlSet\Services\WebClient\Parameters"

    @staticmethod
    def is_windows() -> bool:
        return sys.platform.startswith("win")

    @classmethod
    def optimize_webdav_registry(cls) -> Tuple[bool, str]:
        """Ensures Windows WebDAV client allows up to 4GB files and HTTP Basic Auth."""
        if not cls.is_windows():
            return False, "Not on Windows."

        try:
            # Try to write to HKLM
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, cls.REG_PATH, 0, winreg.KEY_SET_VALUE | winreg.KEY_READ)
            # Set FileSizeLimitInBytes to 4GB (0xffffffff)
            winreg.SetValueEx(key, "FileSizeLimitInBytes", 0, winreg.REG_DWORD, 4294967295)
            # Set BasicAuthLevel to 2 (allow basic auth over non-SSL)
            winreg.SetValueEx(key, "BasicAuthLevel", 0, winreg.REG_DWORD, 2)
            winreg.CloseKey(key)

            # Restart WebClient service to apply
            subprocess.run(["net", "stop", "webclient"], capture_output=True, text=True)
            subprocess.run(["net", "start", "webclient"], capture_output=True, text=True)
            return True, "Registry tuned successfully for 4GB WebDAV file transfers."
        except PermissionError:
            return False, "Administrator privilege required to tune WebDAV registry. Run terminal as Admin."
        except Exception as e:
            return False, f"Registry error: {e}"

    @classmethod
    def mount_drive(cls, drive_letter: str = "Y:", webdav_url: str = "http://127.0.0.1:8080") -> Tuple[bool, str]:
        """Mounts WebDAV as a Windows network drive letter."""
        if not cls.is_windows():
            return False, "Not on Windows."

        drive_letter = drive_letter.strip().upper()
        if not drive_letter.endswith(":"):
            drive_letter += ":"

        # First remove if already mapped
        cls.unmount_drive(drive_letter)

        # Run net use
        cmd = ["net", "use", drive_letter, webdav_url, "/persistent:no"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return True, f"Successfully mounted CyDrive to {drive_letter}"
        else:
            return False, f"Failed to mount drive {drive_letter}: {result.stderr or result.stdout}"

    @classmethod
    def unmount_drive(cls, drive_letter: str = "Y:") -> Tuple[bool, str]:
        """Unmounts the Windows network drive."""
        if not cls.is_windows():
            return False, "Not on Windows."

        drive_letter = drive_letter.strip().upper()
        if not drive_letter.endswith(":"):
            drive_letter += ":"

        cmd = ["net", "use", drive_letter, "/delete", "/y"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0, result.stdout or result.stderr
