"""
Test JWT capture: Hybrid approach v2
- Use CLIProxyAPIPlus device auth flow (POST /v2/plugin/auth/state -> poll GET /v2/plugin/auth/token)
- Use Camoufox for Google login automation
- Handle new CodeBuddy /login page (not Keycloak)
- Poll for JWT from backend (not browser intercept)
"""
import asyncio
import sys
import os
import time
import json
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
os.environ["CAMOUFOX_HEADLESS"] = "false"

import aiohttp
from camoufox.async_api import AsyncCamoufox
from browserforge.fingerprints import Screen

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
log = logging.getLogger(__name__)

CODEBUDDY_BASE_URL = "https://www.codebuddy.ai"
EMAIL = "akuncursorke8@gmail.com"
PASSWORD = "bintang088"

CLI_HEADERS = {
    "X-Requested-With": "XMLHttpRequest",
    "User-Agent": "CLI/2.95.0 CodeBuddy/2.95.0",
    "Content-Type": "application/json",
    "Accept": "application/json",
}


async def poll_for_jwt(state: str, timeout_seconds: int = 120) -> dict:
    """Poll /v2/plugin/auth/token until JWT is returned."""
    poll_url = f"{CODEBUDDY_BASE_URL}/v2/plugin/auth/token"
    start = time.time()

    async with aiohttp.ClientSession(headers=CLI_HEADERS) as client:
        while time.time() - start < timeout_seconds:
            try:
                async with client.get(f"{poll_url}?state={state}") as resp:
                    status = resp.status
                    try:
                        body = await resp.json()
                    except Exception:
                        text = await resp.text()
                        log.debug(f"Non-JSON: status={status} body={text[:100]}")
                        await asyncio.sleep(2)
                        continue

                    code = body.get("code", -1)

                    if status == 200 and code == 0:
                        token_data = body.get("data", {})
                        return {
                            "success": True,
                            "access_token": token_data.get("accessToken", ""),
                            "refresh_token": token_data.get("refreshToken", ""),
                        }
                    elif code == 14001:
                        elapsed = int(time.time() - start)
                        if elapsed % 10 == 0:
                            log.info(f"  Polling... ({elapsed}s elapsed, waiting for login)")
                        await asyncio.sleep(2)
                    else:
                        log.debug(f"  Poll: status={status} code={code} msg={body.get('msg','')}")
                        await asyncio.sleep(2)
            except Exception as e:
                log.debug(f"  Poll error: {e}")
                await asyncio.sleep(2)

    return {"success": False, "error": "timeout"}


async def automate_google_login(auth_url: str):
    """Open Camoufox, navigate to auth URL, automate Google login on new CB login page."""
    log.info(f"Opening Camoufox for Google login...")

    async with AsyncCamoufox(
        headless=False,
        os="windows",
        block_webrtc=True,
        screen=Screen(max_width=1920, max_height=1080),
        i_know_what_im_doing=True,
    ) as browser:
        page = await browser.new_page()
        page.set_default_timeout(20000)

        # Navigate to auth URL
        log.info(f"Navigating to: {auth_url[:80]}...")
        await page.goto(auth_url, wait_until="networkidle", timeout=45000)
        await asyncio.sleep(5)  # Extra wait for SPA hydration

        # Debug: print current page info
        current_url = page.url
        log.info(f"Current URL: {current_url[:100]}")

        # CodeBuddy login page uses an IFRAME to Keycloak.
        # We need to switch to the iframe to interact with login buttons.
        log.info("Waiting for login iframe to load...")
        await asyncio.sleep(5)

        # Find the login iframe
        login_frame = None
        for frame in page.frames:
            if "auth/realms" in frame.url:
                login_frame = frame
                log.info(f"Found login iframe: {frame.url[:80]}")
                break

        if not login_frame:
            log.error("Login iframe not found! Frames:")
            for f in page.frames:
                log.info(f"  {f.url[:80]}")
            log.info("Waiting 60s for manual login...")
            await asyncio.sleep(60)
            return

        # Wait for iframe content to render
        await asyncio.sleep(3)

        # Use login_frame instead of page for all interactions
        target = login_frame

        # Interact with the Keycloak iframe
        google_clicked = False

        # Step A: Click "Log in" tab (screenshot shows "Sign up" is active)
        try:
            login_tab = target.locator('text="Log in"').first
            if await login_tab.is_visible(timeout=5000):
                await login_tab.click()
                log.info("Clicked 'Log in' tab in iframe")
                await asyncio.sleep(2)
        except Exception as e:
            log.debug(f"Log in tab: {e}")

        # Step B: Check privacy policy checkbox
        try:
            checkbox = target.locator('input[type="checkbox"]').first
            if await checkbox.is_visible(timeout=3000):
                await checkbox.click()
                log.info("Checked privacy checkbox")
                await asyncio.sleep(0.5)
            else:
                # Try clicking the label text
                label = target.locator('text="I confirm"').first
                if await label.is_visible(timeout=2000):
                    await label.click()
                    log.info("Clicked checkbox label")
                    await asyncio.sleep(0.5)
        except Exception as e:
            log.debug(f"Checkbox: {e}")

        # Step C: Click Google login button
        google_selectors = [
            '#social-google',
            'a:has-text("Google")',
            'button:has-text("Google")',
            'text="Sign up with Google"',
            'text="Log in with Google"',
            'text="Sign in with Google"',
        ]
        for selector in google_selectors:
            try:
                el = target.locator(selector).first
                if await el.is_visible(timeout=2000):
                    await el.click()
                    log.info(f"Clicked Google via: {selector}")
                    google_clicked = True
                    await asyncio.sleep(3)
                    break
            except Exception:
                continue

        if not google_clicked:
            # Dump iframe content for debug
            try:
                iframe_text = await target.locator("body").text_content()
                log.info(f"Iframe body text: {(iframe_text or '')[:500]}")
            except Exception:
                pass
            log.error("Could not click Google login in iframe!")
            log.info("Waiting 60s for manual login...")
            await asyncio.sleep(60)
            return

        # After clicking Google, a "Service Agreement" modal appears — click Confirm
        await asyncio.sleep(2)
        try:
            # Modal might be in iframe or main page — try both
            confirm_btn = target.locator('button:has-text("Confirm")').first
            if await confirm_btn.is_visible(timeout=5000):
                await confirm_btn.click()
                log.info("Clicked 'Confirm' on Service Agreement modal")
                await asyncio.sleep(3)
            else:
                # Try main page
                confirm_btn = page.locator('button:has-text("Confirm")').first
                if await confirm_btn.is_visible(timeout=3000):
                    await confirm_btn.click()
                    log.info("Clicked 'Confirm' on modal (main page)")
                    await asyncio.sleep(3)
        except Exception as e:
            log.warning(f"Confirm modal: {e}")

        # After clicking Google in iframe, the main page should navigate to Google
        # Wait for Google page (check both main page URL and frames)
        log.info("Waiting for Google login page...")
        for _ in range(20):
            current_url = page.url
            if "accounts.google.com" in current_url:
                log.info("On Google login page (main frame)")
                break
            # Also check if any frame navigated to Google
            for frame in page.frames:
                if "accounts.google.com" in frame.url:
                    log.info("Google login in frame")
                    break
            await asyncio.sleep(1)
        else:
            log.warning(f"Not on Google after 20s. URL: {page.url[:80]}")
            # Take debug screenshot
            try:
                await page.screenshot(path=os.path.join(os.path.dirname(__file__), "debug_after_google_click.png"))
            except Exception:
                pass

        # Handle account picker
        current_url = page.url
        if "accounts.google.com" in current_url:
            try:
                account_el = page.locator(f'[data-email="{EMAIL}"]').first
                if await account_el.is_visible(timeout=3000):
                    await account_el.click()
                    log.info(f"Selected account from picker")
                    await asyncio.sleep(3)
                    # Check if we're done (no password needed for remembered accounts)
                    if "accounts.google.com" not in page.url:
                        log.info("Login complete after account pick")
                        await asyncio.sleep(5)
                        return
            except Exception:
                pass

            # Fill email if needed
            try:
                email_input = page.locator('#identifierId')
                if await email_input.is_visible(timeout=5000):
                    await email_input.click()
                    await asyncio.sleep(0.3)
                    await email_input.type(EMAIL, delay=50)
                    await asyncio.sleep(0.5)
                    next_btn = page.locator('#identifierNext')
                    await next_btn.click()
                    log.info("Email filled, clicked Next")
                    await asyncio.sleep(4)
            except Exception as e:
                log.debug(f"Email step: {e}")

            # Fill password
            try:
                pwd_input = page.locator('input[name="Passwd"]')
                if await pwd_input.is_visible(timeout=8000):
                    await pwd_input.click()
                    await asyncio.sleep(0.3)
                    await pwd_input.type(PASSWORD, delay=50)
                    await asyncio.sleep(0.5)
                    next_btn = page.locator('#passwordNext')
                    await next_btn.click()
                    log.info("Password filled, clicked Next")
                    await asyncio.sleep(4)
            except Exception as e:
                log.debug(f"Password step: {e}")

            # Handle consent
            try:
                allow_btn = page.locator('button:has-text("Allow"), button:has-text("Continue")').first
                if await allow_btn.is_visible(timeout=3000):
                    await allow_btn.click()
                    log.info("Clicked Allow/Continue on consent")
                    await asyncio.sleep(3)
            except Exception:
                pass

        # Wait for redirect back to codebuddy
        log.info("Waiting for redirect back to CodeBuddy...")
        for i in range(30):
            current_url = page.url
            if "codebuddy.ai" in current_url and "accounts.google.com" not in current_url:
                log.info(f"Back on CodeBuddy: {current_url[:80]}")
                break
            if i % 5 == 0:
                log.info(f"  Still waiting... ({page.url[:60]})")
            await asyncio.sleep(1)

        # Keep browser open for a bit to let server register the login
        await asyncio.sleep(10)
        log.info("Browser login automation complete")


async def main():
    print("=" * 60)
    print("HYBRID JWT CAPTURE TEST v2")
    print("  Method: Device auth (state+poll) + Camoufox Google login")
    print(f"  Account: {EMAIL}")
    print("=" * 60)

    # Step 1: Get auth state
    print("\n[Step 1] POST /v2/plugin/auth/state...")
    async with aiohttp.ClientSession(headers=CLI_HEADERS) as client:
        async with client.post(
            f"{CODEBUDDY_BASE_URL}/v2/plugin/auth/state?platform=IDE", json={}
        ) as resp:
            print(f"  Status: {resp.status}")
            data = await resp.json()
            print(f"  Code: {data.get('code')}")
            state_data = data.get("data", {})
            state = state_data.get("state", "")
            auth_url = state_data.get("authUrl", "")
            print(f"  State: {state[:40]}...")
            print(f"  AuthUrl: {auth_url[:80]}...")

    if not state or not auth_url:
        print("FAILED: No state/authUrl returned")
        return

    # Step 2: Start polling + login in parallel
    print(f"\n[Step 2] Starting JWT poll (background) + Google login (foreground)...")

    poll_task = asyncio.create_task(poll_for_jwt(state, timeout_seconds=120))
    login_task = asyncio.create_task(automate_google_login(auth_url))

    # Wait for login to complete
    await login_task
    print("\n[Step 3] Login automation done. Waiting for JWT poll result...")

    # Wait for poll (give it extra time after login completes)
    result = await poll_task

    print("\n" + "=" * 60)
    if result.get("success"):
        jwt = result["access_token"]
        refresh = result["refresh_token"]
        print(f"SUCCESS! JWT captured!")
        print(f"  JWT length: {len(jwt)}")
        print(f"  JWT prefix: {jwt[:60]}...")
        print(f"  Refresh token: {refresh[:40]}...")

        # Save
        output = {
            "email": EMAIL,
            "access_token": jwt,
            "refresh_token": refresh,
            "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        output_path = os.path.join(os.path.dirname(__file__), "captured_jwt.json")
        with open(output_path, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\n  Saved to: {output_path}")
    else:
        print(f"FAILED: {result.get('error', 'unknown')}")
        print("  JWT polling timed out.")

    print("=" * 60)


asyncio.run(main())
