import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from playwright.async_api import async_playwright

from forexfactory_mcp.models.time_period import TimePeriod
from forexfactory_mcp.settings import get_settings

logger = logging.getLogger(__name__)


class FFScraperService:
    """
    Service for scraping the ForexFactory calendar using Playwright.

    This class is initialized with either:
      - A predefined TimePeriod (e.g. TODAY, NEXT_WEEK, THIS_MONTH), or
      - TimePeriod.CUSTOM with explicit start and end dates.

    Based on these parameters, the service builds the correct ForexFactory URL
    and fetches events from the calendar page by executing JavaScript in the DOM.
    """

    def __init__(
        self,
        time_period: TimePeriod,
        custom_start_date: Optional[str] = None,
        custom_end_date: Optional[str] = None,
    ):
        self.settings = get_settings()
        self.time_period = time_period
        self.custom_start_date = custom_start_date
        self.custom_end_date = custom_end_date
        self.url = self._build_url()

    def _format_date(self, date_str: str) -> str:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        return date_obj.strftime("%b%d.%Y").lower()

    def _build_url(self) -> str:
        base_url = self.settings.BASE_URL

        if (
            self.time_period == TimePeriod.CUSTOM
            and self.custom_start_date
            and self.custom_end_date
        ):
            start_date = self._format_date(self.custom_start_date)
            end_date = self._format_date(self.custom_end_date)
            href = (
                f"{TimePeriod.to_href(self.time_period)}"
                f"{start_date}-{end_date}"
            )
        else:
            href = TimePeriod.to_href(self.time_period)

        return f"{base_url}{href}"

    async def get_events(self) -> List[Dict[str, Any]]:
        return await self._get_calendar(self.url)

    async def _get_calendar(self, url: str) -> List[Dict[str, Any]]:
        logger.info(f"🌐 Scraping ForexFactory: {url}")

        days_array: List[Dict[str, Any]] = []

        playwright = None
        browser = None
        context = None
        page = None

        timeout_ms = self.settings.SCRAPER_TIMEOUT_MS
        logger.info(f"⏱ Using timeout {timeout_ms}ms")

        try:
            playwright = await async_playwright().start()

            browser = await playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox"],
            )

            # ---------------------------------------------------------
            # Proxy configuration
            # ---------------------------------------------------------
            proxy_server = os.environ.get("PROXY_SERVER")
            proxy_username = os.environ.get("PROXY_USERNAME")
            proxy_password = os.environ.get("PROXY_PASSWORD")

            context_kwargs = {}

            if proxy_server:
                proxy_config = {
                    "server": proxy_server,
                }

                if proxy_username:
                    proxy_config["username"] = proxy_username

                if proxy_password:
                    proxy_config["password"] = proxy_password

                context_kwargs["proxy"] = proxy_config

                logger.info("🌐 Using configured proxy server")
            else:
                logger.info("🌐 No proxy configured; using direct connection")

            context = await browser.new_context(**context_kwargs)

            page = await context.new_page()

            # Apply timeouts
            page.set_default_timeout(timeout_ms)
            page.set_default_navigation_timeout(timeout_ms)

            # Apply extra headers
            await page.set_extra_http_headers(
                self.settings.extra_http_headers
            )

            # Navigate
            await page.goto(
                url,
                wait_until="domcontentloaded",
            )

            try:
                # Extract ForexFactory calendar state
                data = await page.evaluate(
                    """() => {
                        if (
                            typeof window.calendarComponentStates ===
                            'undefined'
                        ) {
                            return [];
                        }

                        return (
                            window.calendarComponentStates[1]?.days ||
                            window.calendarComponentStates[0]?.days ||
                            []
                        );
                    }"""
                )

                days_array = data or []

            except Exception as e:
                logger.error(
                    f"⚠️ Failed to evaluate calendar state: {e}"
                )

        except Exception as e:
            logger.exception(
                f"⚠️ Could not scrape ForexFactory: {e}"
            )

        finally:
            # Always close resources in reverse order
            for obj, close_fn in [
                (page, page.close if page else None),
                (context, context.close if context else None),
                (browser, browser.close if browser else None),
                (playwright, playwright.stop if playwright else None),
            ]:
                if close_fn:
                    try:
                        await close_fn()
                    except Exception:
                        pass

        return days_array
