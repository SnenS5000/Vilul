from __future__ import annotations

import json
import re
import threading
from html import unescape
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class WorldstateClient:
    def __init__(self, platform: str = "pc") -> None:
        self.platform = platform
        self.base_url = f"https://api.warframestat.us/{platform}/"

    def fetch_worldstate(self) -> dict[str, Any]:
        request = Request(
            self.base_url,
            headers={
                "User-Agent": "WarframeCompanion/0.2",
                "Accept": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=12) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise RuntimeError(f"Worldstate request failed with HTTP {error.code}.") from error
        except URLError as error:
            raise RuntimeError("Worldstate request failed. Check your internet connection.") from error


class WarframeMarketClient:
    def __init__(self) -> None:
        self.home_url = "https://warframe.market/"
        self.catalog_api_url = "https://api.warframe.market/v2/items"
        self.item_api_url_template = "https://api.warframe.market/v2/item/{url_name}/set"
        self.orders_api_url_template = "https://api.warframe.market/v2/orders/item/{url_name}"
        self.statistics_url_template = "https://api.warframe.market/v1/items/{url_name}/statistics"
        self.asset_base_url = "https://warframe.market/static/assets/"
        self._browser_headers = {
            "User-Agent": "WarframeCompanion/0.3",
            "Accept-Language": "en-US,en;q=0.9",
        }
        self._lock = threading.RLock()
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    def fetch_item_catalog(self) -> list[dict[str, str]]:
        payload = self._browser_get_json(self.catalog_api_url)
        items: list[dict[str, str]] = []
        for entry in payload.get("data", []):
            if not isinstance(entry, dict):
                continue
            localized = entry.get("i18n", {}).get("en", {})
            item_name = localized.get("name")
            url_name = entry.get("slug")
            if not item_name or not url_name:
                continue
            items.append(
                {
                    "item_name": str(item_name),
                    "url_name": str(url_name),
                    "thumb_url": self._asset_url(localized.get("thumb")),
                    "icon_url": self._asset_url(localized.get("icon")),
                    "max_rank": int(entry.get("maxRank") or 0),
                    "is_set": "set" in entry.get("tags", []),
                }
            )
        items.sort(key=lambda item: item["item_name"].lower())
        return items

    def fetch_item_details(self, url_name: str) -> dict[str, Any]:
        payload = self._browser_get_json(self.item_api_url_template.format(url_name=url_name))
        return payload.get("data", {})

    def fetch_item_orders(self, url_name: str) -> list[dict[str, Any]]:
        payload = self._browser_get_json(self.orders_api_url_template.format(url_name=url_name))
        return payload.get("data", [])

    def fetch_item_statistics(self, url_name: str) -> dict[str, Any]:
        url = self.statistics_url_template.format(url_name=url_name)
        request = Request(
            url,
            headers={
                **self._browser_headers,
                "Accept": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise RuntimeError(f"Market statistics request failed with HTTP {error.code}.") from error
        except URLError as error:
            raise RuntimeError("Market statistics request failed. Check your internet connection.") from error

        return payload.get("payload", {}).get("statistics_closed", {})

    def close(self) -> None:
        with self._lock:
            if self._page is not None:
                self._page.close()
                self._page = None
            if self._context is not None:
                self._context.close()
                self._context = None
            if self._browser is not None:
                self._browser.close()
                self._browser = None
            if self._playwright is not None:
                self._playwright.stop()
                self._playwright = None

    def _fetch_text(self, url: str, accept: str) -> str:
        request = Request(
            url,
            headers={
                **self._browser_headers,
                "Accept": accept,
            },
        )
        try:
            with urlopen(request, timeout=15) as response:
                return response.read().decode("utf-8")
        except HTTPError as error:
            raise RuntimeError(f"Market request failed with HTTP {error.code}.") from error
        except URLError as error:
            raise RuntimeError("Market request failed. Check your internet connection.") from error

    def _browser_get_json(self, url: str) -> dict[str, Any]:
        with self._lock:
            self._ensure_browser_session()
            assert self._context is not None
            response = self._context.request.get(
                url,
                headers={"Accept": "application/json"},
            )
            if response.status == 403:
                self._refresh_browser_session()
                response = self._context.request.get(
                    url,
                    headers={"Accept": "application/json"},
                )
            if response.status != 200:
                raise RuntimeError(f"Market request failed with HTTP {response.status}.")
            return response.json()

    def _ensure_browser_session(self) -> None:
        if self._context is not None and self._page is not None:
            return

        try:
            from playwright.sync_api import sync_playwright
        except ImportError as error:
            raise RuntimeError(
                "Playwright is required for live orders. Run 'py -3 -m pip install playwright' "
                "and 'py -3 -m playwright install chromium'."
            ) from error

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=True)
        self._context = self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/145.0.0.0 Safari/537.36"
            ),
            locale="en-US",
        )
        self._page = self._context.new_page()
        self._page.goto(self.home_url, wait_until="networkidle", timeout=120000)

    def _refresh_browser_session(self) -> None:
        if self._page is None:
            self._ensure_browser_session()
            return
        self._page.goto(self.home_url, wait_until="networkidle", timeout=120000)

    def _asset_url(self, path: Any) -> str:
        if not path:
            return ""
        text = str(path).lstrip("/")
        return f"{self.asset_base_url}{text}"

    @staticmethod
    def _extract_embedded_json(html: str, script_id: str) -> Any:
        pattern = rf'<script type="application/json" id="{re.escape(script_id)}">(.*?)</script>'
        match = re.search(pattern, html, re.DOTALL)
        if match is None:
            raise RuntimeError(f"Could not find {script_id} on the market page.")
        return json.loads(unescape(match.group(1)))

    @staticmethod
    def _extract_meta_content(html: str, name: str) -> str:
        if name == "title":
            match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        else:
            pattern = rf'<meta name="{re.escape(name)}" content="([^"]*)"'
            match = re.search(pattern, html, re.IGNORECASE)
        if match is None:
            return "-"
        return unescape(match.group(1)).strip()
