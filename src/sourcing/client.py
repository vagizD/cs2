import time
import random
import logging
from pathlib import Path
from typing import Optional, Dict
from curl_cffi import requests as cffi_requests
import nodriver as uc
import asyncio

logger = logging.getLogger(__name__)

class HLTVClient:
    """
    Hybrid HLTV client:
    1. Uses local HTML disk cache if available.
    2. Uses fast curl_cffi with Cloudflare clearance cookies.
    3. Auto-refreshes cookies using nodriver on HTTP 403.
    """
    def __init__(self, base_cache_dir: str = "data/raw", delay_range: tuple = (1.0, 2.0)):
        self.base_cache_dir = Path(base_cache_dir)
        self.delay_range = delay_range
        self.session = cffi_requests.Session(impersonate="chrome")
        self.user_agent: Optional[str] = None
        self.cookies: Dict[str, str] = {}
        self._cookies_initialized = False

    def _refresh_cookies(self):
        logger.info("Initializing/Refreshing Cloudflare clearance cookies via nodriver...")

        async def _async_get_cookies():
            browser = await uc.start()
            page = await browser.get("https://www.hltv.org/results?startDate=2024-01-01&endDate=2024-01-07")
            await page.sleep(4)
            cookies = await page.send(uc.cdp.network.get_cookies())
            ua = await page.evaluate("navigator.userAgent")
            browser.stop()
            return cookies, ua

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        cookies, ua = loop.run_until_complete(_async_get_cookies())
        self.user_agent = ua
        self.session.headers["User-Agent"] = ua
        self.session.headers["Accept-Language"] = "en-US,en;q=0.9"
        self.session.headers["Referer"] = "https://www.hltv.org/"
        
        self.cookies = {c.name: c.value for c in cookies}
        for k, v in self.cookies.items():
            self.session.cookies.set(k, v)
            
        self._cookies_initialized = True
        logger.info("Successfully refreshed cookies: %s", list(self.cookies.keys()))

    def get_html(self, url: str, cache_path: Path, force_refresh: bool = False) -> str:
        """
        Gets HTML content for URL.
        If cache_path exists and not force_refresh, returns cached HTML.
        Otherwise fetches from web, saves to cache_path, and returns HTML.
        """
        cache_path = Path(cache_path)
        if cache_path.exists() and not force_refresh:
            logger.debug(f"Reading from local cache: {cache_path}")
            return cache_path.read_text(encoding="utf-8", errors="ignore")

        cache_path.parent.mkdir(parents=True, exist_ok=True)

        if not self._cookies_initialized:
            self._refresh_cookies()

        # Rate limiting delay
        time.sleep(random.uniform(*self.delay_range))

        logger.info(f"Downloading from web: {url}")
        resp = self.session.get(url)

        if resp.status_code == 403:
            logger.warning(f"Got 403 Forbidden for {url}. Attempting Cloudflare cookie refresh...")
            self._refresh_cookies()
            time.sleep(2.0)
            resp = self.session.get(url)

        if resp.status_code != 200:
            logger.error(f"Failed to fetch {url}, status: {resp.status_code}")
            resp.raise_for_status()

        html_content = resp.text
        cache_path.write_text(html_content, encoding="utf-8")
        logger.info(f"Saved raw HTML to {cache_path} ({len(html_content)} bytes)")
        return html_content
