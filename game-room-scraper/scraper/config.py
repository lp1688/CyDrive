from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.json"
EXAMPLE_CONFIG_PATH = PROJECT_ROOT / "config.example.json"


class Selectors(BaseModel):
    username_input: str = "input[name='username']"
    password_input: str = "input[name='password']"
    login_button: str = "button[type='submit']"
    machine_card: str = "[data-machine-id], .machine-card"
    machine_id: str = ".machine-id"
    machine_percent: str = ".machine-percent"
    occupied_icon: str = ".occupied, .user-icon"
    locked_icon: str = ".locked, .lock-icon"
    detail_panel: str = ".machine-detail"
    detail_today_bet: str = ".today-bet"
    detail_today_rate: str = ".today-rate"
    detail_days30_bet: str = ".days30-bet"
    detail_days30_rate: str = ".days30-rate"
    detail_spins_since_win: str = ".spins-since-win"
    detail_prev1_spins: str = ".prev1-spins"
    detail_prev2_spins: str = ".prev2-spins"
    next_page: str = ".pagination .next, button[aria-label='next']"
    show_all_filter: str = "button:has-text('顯示全部')"


class ApiIntercept(BaseModel):
    enabled: bool = True
    url_substring: str = "/api/machines"


class ScraperConfig(BaseModel):
    base_url: str = "https://example.com"
    login_url: str = "https://example.com/login"
    machine_list_url: str = "https://example.com/machines"
    username: str = ""
    password: str = ""
    headless: bool = True
    timeout_ms: int = 30000
    db_path: str = "./data/machines.db"
    fetch_details: bool = True
    selectors: Selectors = Field(default_factory=Selectors)
    api_intercept: ApiIntercept = Field(default_factory=ApiIntercept)

    def resolved_db_path(self) -> Path:
        path = Path(self.db_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path


class EnvSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    scraper_base_url: str | None = None
    scraper_login_url: str | None = None
    scraper_machine_list_url: str | None = None
    scraper_username: str | None = None
    scraper_password: str | None = None
    scraper_headless: bool | None = None
    scraper_timeout_ms: int | None = None
    scraper_db_path: str | None = None
    api_host: str = "127.0.0.1"
    api_port: int = 8090


def _load_json_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def load_config(config_path: Path | None = None) -> ScraperConfig:
    """Merge config.json (or example) with environment overrides."""
    path = config_path or DEFAULT_CONFIG_PATH
    raw = _load_json_config(path)
    if not raw and EXAMPLE_CONFIG_PATH.exists():
        raw = _load_json_config(EXAMPLE_CONFIG_PATH)

    cfg = ScraperConfig.model_validate(raw)
    env = EnvSettings()

    updates: dict[str, Any] = {}
    if env.scraper_base_url:
        updates["base_url"] = env.scraper_base_url
    if env.scraper_login_url:
        updates["login_url"] = env.scraper_login_url
    if env.scraper_machine_list_url:
        updates["machine_list_url"] = env.scraper_machine_list_url
    if env.scraper_username:
        updates["username"] = env.scraper_username
    if env.scraper_password:
        updates["password"] = env.scraper_password
    if env.scraper_headless is not None:
        updates["headless"] = env.scraper_headless
    if env.scraper_timeout_ms is not None:
        updates["timeout_ms"] = env.scraper_timeout_ms
    if env.scraper_db_path:
        updates["db_path"] = env.scraper_db_path

    if updates:
        cfg = cfg.model_copy(update=updates)
    return cfg


def load_env_settings() -> EnvSettings:
    return EnvSettings()
