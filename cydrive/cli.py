import sys
import os
import time
import asyncio
import threading
import argparse

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich import print as rprint
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

from cydrive.config import CyDriveConfig
from cydrive.database import MetaDatabase
from cydrive.cache_manager import CacheManager
from cydrive.telegram_client import TelegramSyncEngine
from cydrive.watcher import DriveWatcher
from cydrive.webdav_server import CyWebDAVServer
from cydrive.web_ui.app import CyWebDashboard
from cydrive.platform.windows import WindowsMounter

class CyDriveCLI:
    """CLI and Unified Application Runner for CyDrive."""

    def __init__(self):
        self.console = Console() if HAS_RICH else None

    def print_banner(self):
        banner_text = r"""
   ______      ____       _           
  / ____/_  __/ __ \_____(_)   _____  
 / /   / / / / / / / ___/ / | / / _ \ 
/ /___/ /_/ / /_/ / /  / /| |/ /  __/ 
\____/\__, /_____/_/  /_/ |___/\___/  
     /____/  CYNET CLOUD STORAGE ENGINE v2.0
        """
        if HAS_RICH:
            self.console.print(Panel(
                Text(banner_text, style="bold cyan") + 
                Text("\n🚀 Infinite Cloud Virtual Drive for Windows via Telegram\n🌐 Cynet Security Team • https://cynetx.ir", style="bold magenta"),
                border_style="cyan"
            ))
        else:
            print("=" * 65)
            print("  🚀 CyDrive: Infinite Cloud Virtual Drive v2.0")
            print("  🌐 Cynet Security Team - https://cynetx.ir")
            print("=" * 65)

    def print_status_table(self, config: CyDriveConfig, db: MetaDatabase):
        stats = db.get_stats()
        size_mb = stats["total_bytes"] / (1024 * 1024)

        if HAS_RICH:
            table = Table(title="💎 CyDrive Active Services & Status", border_style="bright_blue")
            table.add_column("Service / Component", style="cyan", no_wrap=True)
            table.add_column("Status / Address", style="green")
            table.add_column("Details", style="yellow")

            table.add_row("Telegram MTProto", "🟢 Connected", f"Target Chat: {config.chat_id}")
            table.add_row("WebDAV File Server", "🟢 Active", f"http://{config.webdav_host}:{config.webdav_port}")
            table.add_row("Cyberpunk Web UI", "🟢 Online", f"http://{config.web_ui_host}:{config.web_ui_port}")
            table.add_row("Windows Virtual Drive", "🔵 Mapped", f"Drive Letter: {config.drive_letter}")
            table.add_row("Local Disk Footprint", "🟢 0 Bytes (Pure Cloud)", "Direct on-demand streaming from Telegram")
            table.add_row("Cloud Storage Used", "🟣 Synced", f"{stats['total_files']} Files ({size_mb:.2f} MB)")

            self.console.print(table)
        else:
            print(f"[+] WebDAV Server: http://{config.webdav_host}:{config.webdav_port}")
            print(f"[+] Web UI: http://{config.web_ui_host}:{config.web_ui_port}")
            print(f"[+] Mounted Drive: {config.drive_letter}")
            print(f"[+] Local Disk Footprint: 0 Bytes (Pure Cloud)")
            print(f"[+] Total Files: {stats['total_files']} ({size_mb:.2f} MB)")

    def run(self):
        parser = argparse.ArgumentParser(description="CyDrive Cloud Storage Engine")
        parser.add_argument("command", nargs="?", default="run", choices=["run", "mount", "unmount", "fix-reg", "stats", "setup"], help="Command to execute")
        args = parser.parse_args()

        self.print_banner()

        if args.command == "setup":
            CyDriveConfig.interactive_setup()
            return

        is_run_command = (args.command == "run")
        config = CyDriveConfig.load(prompt_if_missing=is_run_command)
        db = MetaDatabase(config.db_path)

        if args.command == "fix-reg":
            success, msg = WindowsMounter.optimize_webdav_registry()
            print(f"[{'✅' if success else '❌'}] {msg}")
            return

        elif args.command == "mount":
            success, msg = WindowsMounter.mount_drive(config.drive_letter, f"http://{config.webdav_host}:{config.webdav_port}")
            print(f"[{'✅' if success else '❌'}] {msg}")
            return

        elif args.command == "unmount":
            success, msg = WindowsMounter.unmount_drive(config.drive_letter)
            print(f"[{'✅' if success else '❌'}] {msg}")
            return

        elif args.command == "stats":
            stats = db.get_stats()
            print(f"📊 Storage Stats: {stats}")
            return

        # Main 'run' workflow
        print("\n⏳ Initializing CyDrive v2.0 Pure Virtual Cloud Services...\n")
        
        cache_mgr = CacheManager(config.cache_path, config.cache_limit_gb)
        telegram_engine = TelegramSyncEngine(config, db)

        # 1. Start Pure Virtual WebDAV server
        webdav = CyWebDAVServer(
            root_path=config.storage_path,
            host=config.webdav_host,
            port=config.webdav_port,
            db=db,
            cache_mgr=cache_mgr,
            telegram_engine=telegram_engine
        )
        webdav.start(blocking=False)
        
        loop = asyncio.new_event_loop()

        # 2. Auto-mount Virtual Drive across Platforms (Windows, Linux, macOS)
        if config.auto_mount_drive:
            from cydrive.platform.linux_mac import UnixMounter
            if WindowsMounter.is_windows():
                WindowsMounter.optimize_webdav_registry()
                success, msg = WindowsMounter.mount_drive(config.drive_letter, f"http://{config.webdav_host}:{config.webdav_port}")
                if success:
                    print(f"✅ Auto-Mounted {config.drive_letter} Virtual Drive in Windows Explorer")
            elif UnixMounter.is_linux() or UnixMounter.is_macos():
                success, msg = UnixMounter.mount_drive(None, f"http://{config.webdav_host}:{config.webdav_port}")
                if success:
                    print(f"✅ {msg}")

        # 5. Start Web UI & Telegram Loop
        def start_async_loop():
            asyncio.set_event_loop(loop)
            
            # Start Telegram
            loop.run_until_complete(telegram_engine.start())
            
            # Start Web Dashboard
            if config.enable_web_ui:
                dashboard = CyWebDashboard(config, db, telegram_engine)
                loop.run_until_complete(dashboard.start())

            self.print_status_table(config, db)
            print("\n✨ CyDrive is running smoothly in background. Press Ctrl+C to stop.\n")
            loop.run_forever()

        async_thread = threading.Thread(target=start_async_loop, daemon=True)
        async_thread.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Shutting down CyDrive gracefully...")
            webdav.stop()
            if WindowsMounter.is_windows():
                WindowsMounter.unmount_drive(config.drive_letter)
            else:
                from cydrive.platform.linux_mac import UnixMounter
                UnixMounter.unmount_drive()
            print("👋 Goodbye!")

def main():
    cli = CyDriveCLI()
    cli.run()

if __name__ == "__main__":
    main()
