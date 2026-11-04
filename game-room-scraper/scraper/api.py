from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from scraper.browser import MachineScraper, run_demo_scrape
from scraper.config import load_config, load_env_settings
from scraper.database import MachineStore


def create_app() -> FastAPI:
    cfg = load_config()
    store = MachineStore(cfg.resolved_db_path())

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield

    app = FastAPI(
        title="Game Room Scraper API",
        version="0.1.0",
        description="Expose scraped machine list as JSON for another page / consumer.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "db": str(cfg.resolved_db_path())}

    @app.get("/machines")
    def list_machines() -> dict[str, Any]:
        machines = store.list_machines()
        return {
            "count": len(machines),
            "latest_run": store.latest_run(),
            "machines": machines,
        }

    @app.get("/machines/{machine_id}")
    def get_machine(machine_id: str) -> dict[str, Any]:
        row = store.get_machine(machine_id)
        if not row:
            # also try zero-padded
            row = store.get_machine(machine_id.zfill(3))
        if not row:
            raise HTTPException(status_code=404, detail="machine not found")
        return row

    @app.post("/scrape")
    async def trigger_scrape(demo: bool = Query(False, description="Use demo seed data")) -> dict[str, Any]:
        fresh_cfg = load_config()
        if demo:
            result = await run_demo_scrape()
        else:
            result = await MachineScraper(fresh_cfg).run()

        store.upsert_machines(
            result.machines,
            source=result.source,
            ok=result.ok,
            error=result.error,
        )
        return {
            "ok": result.ok,
            "count": result.count,
            "source": result.source,
            "scraped_at": result.scraped_at,
            "error": result.error,
            "machines": [m.model_dump() for m in result.machines],
        }

    @app.get("/runs/latest")
    def latest_run() -> dict[str, Any]:
        run = store.latest_run()
        if not run:
            raise HTTPException(status_code=404, detail="no scrape runs yet")
        return run

    return app


app = create_app()


def main() -> None:
    import uvicorn

    env = load_env_settings()
    uvicorn.run(
        "scraper.api:app",
        host=env.api_host,
        port=env.api_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
