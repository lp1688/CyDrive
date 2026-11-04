#!/usr/bin/env python3
"""CLI entry: scrape once, or start the JSON API server."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scraper.browser import MachineScraper, run_demo_scrape
from scraper.config import load_config, load_env_settings
from scraper.database import MachineStore


def cmd_scrape(demo: bool, dump_json: Path | None) -> int:
    cfg = load_config()
    store = MachineStore(cfg.resolved_db_path())

    async def _run():
        if demo:
            return await run_demo_scrape()
        return await MachineScraper(cfg).run()

    result = asyncio.run(_run())
    store.upsert_machines(result.machines, source=result.source, ok=result.ok, error=result.error)

    payload = {
        "ok": result.ok,
        "count": result.count,
        "source": result.source,
        "scraped_at": result.scraped_at,
        "error": result.error,
        "machines": [m.model_dump() for m in result.machines],
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    print(text)
    if dump_json:
        dump_json.parent.mkdir(parents=True, exist_ok=True)
        dump_json.write_text(text + "\n", encoding="utf-8")

    return 0 if result.ok else 1


def cmd_serve() -> int:
    from scraper.api import main as api_main

    api_main()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Game room machine list scraper")
    sub = p.add_subparsers(dest="command", required=True)

    scrape = sub.add_parser("scrape", help="Run one scrape and upsert into SQLite")
    scrape.add_argument(
        "--demo",
        action="store_true",
        help="Seed demo machines (no real site / credentials needed)",
    )
    scrape.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Also write the scrape result JSON to this path",
    )

    sub.add_parser("serve", help="Start FastAPI JSON server for another page")

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "scrape":
        return cmd_scrape(demo=args.demo, dump_json=args.json_out)
    if args.command == "serve":
        # ensure settings load so missing .env is not fatal
        load_env_settings()
        return cmd_serve()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
