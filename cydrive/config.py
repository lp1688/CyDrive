import os
import json
from dataclasses import dataclass, asdict
from typing import Optional

CONFIG_FILE = "config.json"
DEFAULT_STORAGE_DIR = os.path.abspath("./Telegram_Drive")
DEFAULT_CACHE_DIR = os.path.abspath("./Telegram_Cache")
DEFAULT_DB_FILE = os.path.abspath("./cydrive_meta.db")

# Cynet Telegram Android Client Credentials
DEFAULT_API_ID = 6
DEFAULT_API_HASH = "eb06d4abfb49dc3eeb1aeb98ae0f581e"

@dataclass
class CyDriveConfig:
    bot_token: str
    chat_id: int or str
    api_id: int = DEFAULT_API_ID
    api_hash: str = DEFAULT_API_HASH
    storage_path: str = DEFAULT_STORAGE_DIR
    cache_path: str = DEFAULT_CACHE_DIR
    db_path: str = DEFAULT_DB_FILE
    webdav_host: str = "127.0.0.1"
    webdav_port: int = 8080
    web_ui_host: str = "127.0.0.1"
    web_ui_port: int = 8088
    enable_web_ui: bool = True
    drive_letter: str = "Y:"
    auto_mount_drive: bool = True
    chunk_size_mb: int = 1900
    cache_limit_gb: int = 20
    encryption_password: Optional[str] = None
    enable_encryption: bool = False

    @classmethod
    def load(cls, file_path: str = CONFIG_FILE, prompt_if_missing: bool = True) -> "CyDriveConfig":
        """Loads configuration from JSON file or prompts the user interactively."""
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("bot_token") and data.get("chat_id"):
                        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
            except Exception as e:
                print(f"[!] Warning reading config: {e}. Starting setup wizard.")

        if prompt_if_missing:
            return cls.interactive_setup(file_path)
        else:
            # Fallback default configuration
            return cls(bot_token="NOT_CONFIGURED", chat_id=0)

    @classmethod
    def interactive_setup(cls, file_path: str = CONFIG_FILE) -> "CyDriveConfig":
        """Interactive setup wizard for first-time configuration."""
        print("=" * 65)
        print("  🚀 CyDrive: First-Time Interactive Configuration Wizard")
        print("  🌐 Cynet Security Team - https://cynetx.ir")
        print("=" * 65)
        print("\n🔑 Please provide your Telegram Bot credentials:")
        
        bot_token = input("👉 Enter Telegram Bot Token (from @BotFather): ").strip()
        while not bot_token or ":" not in bot_token:
            if not bot_token:
                bot_token = input("❌ Token cannot be empty. Enter Bot Token: ").strip()
            else:
                print("⚠️ Warning: Bot tokens usually follow format '123456789:ABCdef...'")
                confirm = input("👉 Keep this token anyway? (y/n): ").strip().lower()
                if confirm == "y":
                    break
                bot_token = input("👉 Enter Telegram Bot Token: ").strip()

        chat_id_input = input("👉 Enter your Telegram User ID / Chat ID (from @userinfobot): ").strip()
        while not chat_id_input:
            chat_id_input = input("❌ Chat ID cannot be empty. Enter Chat ID: ").strip()

        try:
            chat_id = int(chat_id_input)
        except ValueError:
            chat_id = chat_id_input

        # Suggest best available drive letter
        from cydrive.platform.windows import WindowsMounter
        best_letter = WindowsMounter.get_best_drive_letter("Y:") if WindowsMounter.is_windows() else "Y:"

        drive_letter = input(f"👉 Choose Windows Drive Letter [default: {best_letter}]: ").strip().upper()
        if not drive_letter:
            drive_letter = best_letter
        if not drive_letter.endswith(":"):
            drive_letter += ":"

        cfg = cls(
            bot_token=bot_token,
            chat_id=chat_id,
            drive_letter=drive_letter
        )
        cfg.save(file_path)
        print(f"\n✅ Configuration successfully saved to {file_path}\n")
        return cfg

    def save(self, file_path: str = CONFIG_FILE):
        """Saves current configuration to file."""
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=4)
        
        # Ensure working directories exist
        os.makedirs(self.storage_path, exist_ok=True)
        os.makedirs(self.cache_path, exist_ok=True)
