"""Google OAuth automation via Camoufox + Playwright."""
import asyncio
import logging
from typing import Optional

from camoufox.async_api import AsyncCamoufox
from browserforge.fingerprints import Screen

from ..config import settings

log = logging.getLogger(__name__)


class GoogleOAuth:
    """Automates Google OAuth login in anti-detect browser."""

    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password

    async def login(self, auth_url: str) -> dict:
        """
        Navigate to auth_url, complete Google OAuth, return cookies.
        Returns dict with 'cookies' list from browser context.
        """
        proxy_cfg = None
        if settings.PROXY_URL:
            proxy_cfg = {"server": settings.PROXY_URL}

        async with AsyncCamoufox(
            headless=settings.CAMOUFOX_HEADLESS,
            os="windows",
            block_webrtc=settings.CAMOUFOX_BLOCK_WEBRTC,
            screen=Screen(max_width=settings.CAMOUFOX_MAX_WIDTH, max_height=settings.CAMOUFOX_MAX_HEIGHT),
            proxy=proxy_cfg,
            geoip=bool(settings.PROXY_URL),
        ) as browser:
            context = await browser.new_context()
            page = await context.new_page()

            try:
                # Navigate to CodeBuddy auth URL (redirects to Google)
                log.info(f"Navigating to auth URL for {self.email}")
                await page.goto(auth_url, wait_until="domcontentloaded", timeout=60000)

                # Handle CodeBuddy landing (checkbox + Continue with Google)
                await self._handle_codebuddy_landing(page)

                # Google OAuth flow
                await self._fill_google_email(page)
                await self._fill_google_password(page)
                await self._handle_google_consent(page)

                # Wait for redirect back to CodeBuddy
                await self._wait_for_codebuddy_redirect(page)

                # Extract cookies
                cookies = await context.cookies()
                log.info(f"Login success for {self.email}, got {len(cookies)} cookies")
                return {"cookies": cookies, "success": True}

            except Exception as e:
                log.error(f"Login failed for {self.email}: {e}")
                return {"cookies": [], "success": False, "error": str(e)}
            finally:
                await context.close()

    async def _handle_codebuddy_landing(self, page):
        """Handle CodeBuddy's pre-login page if it appears."""
        try:
            # Look for "Continue with Google" button
            google_btn = page.locator('text="Continue with Google"')
            if await google_btn.count() > 0:
                # Check any checkbox first
                checkbox = page.locator('input[type="checkbox"]')
                if await checkbox.count() > 0:
                    await checkbox.first.check(timeout=5000)
                    await asyncio.sleep(0.5)
                await google_btn.first.click(timeout=10000)
                log.info("Clicked 'Continue with Google'")
                await asyncio.sleep(2)
        except Exception:
            # May already be on Google page
            pass

    async def _fill_google_email(self, page):
        """Fill Google email field."""
        log.info("Filling Google email...")
        # Wait for email input
        email_input = page.locator("#identifierId")
        await email_input.wait_for(state="visible", timeout=30000)

        # Type with human-like delay
        await email_input.fill("")
        await email_input.type(self.email, delay=settings.TYPING_DELAY_MS)
        await asyncio.sleep(0.3)

        # Click Next
        next_btn = page.locator("#identifierNext button")
        await next_btn.click(timeout=10000)
        await asyncio.sleep(2)

    async def _fill_google_password(self, page):
        """Fill Google password field."""
        log.info("Filling Google password...")
        pwd_input = page.locator('input[name="Passwd"]')
        await pwd_input.wait_for(state="visible", timeout=30000)

        await pwd_input.fill("")
        await pwd_input.type(self.password, delay=settings.TYPING_DELAY_MS + 5)
        await asyncio.sleep(0.3)

        # Click Next
        next_btn = page.locator("#passwordNext button")
        await next_btn.click(timeout=10000)
        await asyncio.sleep(3)

    async def _handle_google_consent(self, page):
        """Handle Google consent/ToS screens if they appear."""
        try:
            # Google ToS (gaplustos)
            tos_btn = page.locator('button:has-text("I agree")')
            if await tos_btn.count() > 0:
                await tos_btn.first.click(timeout=5000)
                await asyncio.sleep(2)
        except Exception:
            pass

        try:
            # Consent "Continue" button
            continue_btn = page.locator('button:has-text("Continue")')
            if await continue_btn.count() > 0:
                await continue_btn.first.click(timeout=5000)
                await asyncio.sleep(2)
        except Exception:
            pass

        try:
            # Account picker - select the current email
            account_option = page.locator(f'[data-identifier="{self.email}"]')
            if await account_option.count() > 0:
                await account_option.first.click(timeout=5000)
                await asyncio.sleep(2)
        except Exception:
            pass

    async def _wait_for_codebuddy_redirect(self, page):
        """Wait until we're redirected back to codebuddy.ai."""
        log.info("Waiting for CodeBuddy redirect...")

        for _ in range(60):  # max 60 seconds
            url = page.url
            if "codebuddy.ai" in url:
                log.info(f"Redirected to CodeBuddy: {url}")
                return
            await asyncio.sleep(1)

        raise TimeoutError("Never redirected back to codebuddy.ai")
