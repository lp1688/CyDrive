from __future__ import annotations

import json
from typing import Any

from scraper.config import ScraperConfig
from scraper.models import MachineRecord, ScrapeResult
from scraper.parse_utils import (
    machine_from_api_item,
    normalize_machine_id,
    parse_int,
    parse_number,
    parse_percent,
)


class MachineScraper:
    """Login + scrape machine grid (API intercept preferred, DOM fallback)."""

    def __init__(self, config: ScraperConfig) -> None:
        self.config = config

    async def run(self) -> ScrapeResult:
        if not self.config.username or not self.config.password:
            return ScrapeResult(
                ok=False,
                count=0,
                source="config",
                error="Missing username/password. Copy .env.example → .env or fill config.json.",
            )
        if "example.com" in self.config.base_url:
            return ScrapeResult(
                ok=False,
                count=0,
                source="config",
                error="Update base_url / login_url / machine_list_url to the real site before scraping.",
            )

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return ScrapeResult(
                ok=False,
                count=0,
                source="playwright",
                error="playwright not installed. Run: pip install -r requirements.txt && playwright install chromium",
            )

        intercepted: list[dict[str, Any]] = []
        sel = self.config.selectors

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.config.headless)
            context = await browser.new_context()
            page = await context.new_page()
            page.set_default_timeout(self.config.timeout_ms)

            async def on_response(response: Any) -> None:
                if not self.config.api_intercept.enabled:
                    return
                url = response.url
                if self.config.api_intercept.url_substring not in url:
                    return
                try:
                    if response.status != 200:
                        return
                    data = await response.json()
                except Exception:
                    return
                items = self._extract_list(data)
                for item in items:
                    if isinstance(item, dict):
                        intercepted.append(item)

            page.on("response", on_response)

            try:
                await self._login(page)
                await page.goto(self.config.machine_list_url, wait_until="networkidle")
                try:
                    await page.locator(sel.show_all_filter).first.click(timeout=3000)
                except Exception:
                    pass

                if intercepted:
                    machines = [
                        MachineRecord(**machine_from_api_item(item)) for item in intercepted
                    ]
                    machines = self._dedupe(machines)
                    if self.config.fetch_details:
                        machines = await self._enrich_details(page, machines)
                    await browser.close()
                    return ScrapeResult(
                        ok=True,
                        count=len(machines),
                        source="api_intercept",
                        machines=machines,
                    )

                machines = await self._scrape_dom(page)
                if self.config.fetch_details:
                    machines = await self._enrich_details(page, machines)
                await browser.close()
                return ScrapeResult(
                    ok=True,
                    count=len(machines),
                    source="dom",
                    machines=machines,
                )
            except Exception as exc:
                await browser.close()
                return ScrapeResult(
                    ok=False,
                    count=0,
                    source="playwright",
                    error=str(exc),
                )

    async def _login(self, page: Any) -> None:
        sel = self.config.selectors
        await page.goto(self.config.login_url, wait_until="domcontentloaded")
        await page.fill(sel.username_input, self.config.username)
        await page.fill(sel.password_input, self.config.password)
        await page.click(sel.login_button)
        await page.wait_for_load_state("networkidle")

    async def _scrape_dom(self, page: Any) -> list[MachineRecord]:
        sel = self.config.selectors
        cards = page.locator(sel.machine_card)
        count = await cards.count()
        machines: list[MachineRecord] = []

        for i in range(count):
            card = cards.nth(i)
            mid_text = await self._text_or_attr(card, sel.machine_id, "data-machine-id")
            if not mid_text:
                mid_text = await card.get_attribute("data-machine-id")
            percent_text = await self._text_or_attr(card, sel.machine_percent, None)
            occupied = await card.locator(sel.occupied_icon).count() > 0
            locked = await card.locator(sel.locked_icon).count() > 0
            machines.append(
                MachineRecord(
                    machine_id=normalize_machine_id(mid_text),
                    percent=parse_percent(percent_text),
                    occupied=occupied,
                    locked=locked,
                    raw={"index": i, "id_text": mid_text, "percent_text": percent_text},
                )
            )

        # Pagination: keep clicking next until disabled / gone
        while True:
            next_btn = page.locator(sel.next_page).first
            try:
                if not await next_btn.is_visible(timeout=1000):
                    break
                if await next_btn.is_disabled():
                    break
                await next_btn.click()
                await page.wait_for_timeout(800)
            except Exception:
                break
            cards = page.locator(sel.machine_card)
            count = await cards.count()
            for i in range(count):
                card = cards.nth(i)
                mid_text = await self._text_or_attr(card, sel.machine_id, "data-machine-id")
                if not mid_text:
                    mid_text = await card.get_attribute("data-machine-id")
                percent_text = await self._text_or_attr(card, sel.machine_percent, None)
                occupied = await card.locator(sel.occupied_icon).count() > 0
                locked = await card.locator(sel.locked_icon).count() > 0
                machines.append(
                    MachineRecord(
                        machine_id=normalize_machine_id(mid_text),
                        percent=parse_percent(percent_text),
                        occupied=occupied,
                        locked=locked,
                        raw={"index": i, "id_text": mid_text, "percent_text": percent_text},
                    )
                )

        return self._dedupe(machines)

    async def _enrich_details(
        self, page: Any, machines: list[MachineRecord]
    ) -> list[MachineRecord]:
        """Click each card and read the bottom detail drawer when selectors match."""
        sel = self.config.selectors
        enriched: list[MachineRecord] = []
        for m in machines:
            card = page.locator(sel.machine_card).filter(
                has_text=m.machine_id.lstrip("0") or m.machine_id
            ).first
            try:
                await card.click(timeout=2000)
                panel = page.locator(sel.detail_panel).first
                await panel.wait_for(state="visible", timeout=3000)
                data = m.model_dump()
                data.update(
                    {
                        "spins_since_win": parse_int(
                            await self._safe_text(panel, sel.detail_spins_since_win)
                        ),
                        "prev1_spins": parse_int(
                            await self._safe_text(panel, sel.detail_prev1_spins)
                        ),
                        "prev2_spins": parse_int(
                            await self._safe_text(panel, sel.detail_prev2_spins)
                        ),
                        "today_bet": parse_number(
                            await self._safe_text(panel, sel.detail_today_bet)
                        ),
                        "today_rate": parse_percent(
                            await self._safe_text(panel, sel.detail_today_rate)
                        ),
                        "days30_bet": parse_number(
                            await self._safe_text(panel, sel.detail_days30_bet)
                        ),
                        "days30_rate": parse_percent(
                            await self._safe_text(panel, sel.detail_days30_rate)
                        ),
                    }
                )
                enriched.append(MachineRecord(**data))
            except Exception:
                enriched.append(m)
        return enriched

    @staticmethod
    async def _text_or_attr(locator: Any, css: str, attr: str | None) -> str | None:
        try:
            node = locator.locator(css).first
            if await node.count() > 0:
                text = (await node.inner_text()).strip()
                if text:
                    return text
            if attr:
                return await locator.get_attribute(attr)
        except Exception:
            return None
        return None

    @staticmethod
    async def _safe_text(root: Any, css: str) -> str | None:
        try:
            node = root.locator(css).first
            if await node.count() == 0:
                return None
            return (await node.inner_text()).strip()
        except Exception:
            return None

    @staticmethod
    def _extract_list(data: Any) -> list[Any]:
        if isinstance(data, list):
            return data
        if not isinstance(data, dict):
            return []
        for key in ("data", "list", "machines", "items", "result", "rows"):
            val = data.get(key)
            if isinstance(val, list):
                return val
            if isinstance(val, dict):
                nested = MachineScraper._extract_list(val)
                if nested:
                    return nested
        return []

    @staticmethod
    def _dedupe(machines: list[MachineRecord]) -> list[MachineRecord]:
        seen: dict[str, MachineRecord] = {}
        for m in machines:
            if not m.machine_id:
                continue
            seen[m.machine_id] = m
        return list(seen.values())


def seed_demo_machines() -> list[MachineRecord]:
    """Deterministic sample data for local API / UI wiring without the real site."""
    samples = [
        {"machine_id": "001", "percent": 61.15, "occupied": True, "locked": False, "today_rate": 58.86},
        {"machine_id": "002", "percent": 120.72, "occupied": False, "locked": False, "today_rate": 95.1},
        {"machine_id": "012", "percent": 76.94, "occupied": True, "locked": True, "today_rate": 70.2},
        {
            "machine_id": "207",
            "percent": 58.86,
            "occupied": False,
            "locked": False,
            "spins_since_win": 0,
            "prev1_spins": 71,
            "prev2_spins": 1,
            "today_bet": 3240847.40,
            "today_rate": 58.86,
            "days30_bet": 535849997.60,
            "days30_rate": 95.62,
        },
    ]
    return [MachineRecord(**s, raw=s) for s in samples]


async def run_demo_scrape() -> ScrapeResult:
    machines = seed_demo_machines()
    return ScrapeResult(ok=True, count=len(machines), source="demo", machines=machines)
