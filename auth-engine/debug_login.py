"""Debug script to check what's available after successful login."""
import asyncio
import sys
import json

sys.path.insert(0, ".")
from src import config


async def debug():
    from camoufox.async_api import AsyncCamoufox
    from browserforge.fingerprints import Screen

    async with AsyncCamoufox(
        headless=True,
        os="windows",
        block_webrtc=True,
        screen=Screen(max_width=1920, max_height=1080),
    ) as browser:
        page = await browser.new_page()

        # Go through full login flow
        await page.goto(config.CODEBUDDY_AUTH_URL, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        # Click Google
        await page.locator("#social-google").first.click()
        await asyncio.sleep(1)

        # Confirm ToS
        try:
            checkbox = page.locator("#agree-policy")
            if await checkbox.is_visible(timeout=3000):
                await checkbox.click()
                await asyncio.sleep(0.5)
            confirm = page.locator('button:has-text("Confirm")').first
            if await confirm.is_visible(timeout=3000):
                await confirm.click()
        except Exception:
            pass

        # Wait for redirect to codebuddy home
        try:
            await page.wait_for_url("**/codebuddy.ai/**", timeout=30000)
        except Exception:
            pass
        await asyncio.sleep(5)

        url = page.url
        print(f"Final URL: {url}")

        # Check cookies
        cookies = await page.context.cookies()

        # Check localStorage
        local_storage = await page.evaluate("() => JSON.stringify(localStorage)")

        # Check sessionStorage
        session_storage = await page.evaluate("() => JSON.stringify(sessionStorage)")

        # Try to get token from the page's JS context
        token_check = await page.evaluate("""() => {
            // Check common token storage patterns
            const result = {};
            // localStorage
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                const val = localStorage.getItem(key);
                if (val && (val.includes('eyJ') || key.toLowerCase().includes('token') || key.toLowerCase().includes('auth'))) {
                    result['ls_' + key] = val.substring(0, 200);
                }
            }
            // sessionStorage
            for (let i = 0; i < sessionStorage.length; i++) {
                const key = sessionStorage.key(i);
                const val = sessionStorage.getItem(key);
                if (val && (val.includes('eyJ') || key.toLowerCase().includes('token') || key.toLowerCase().includes('auth'))) {
                    result['ss_' + key] = val.substring(0, 200);
                }
            }
            // Check cookies accessible from JS
            result['document_cookie'] = document.cookie.substring(0, 500);
            return result;
        }""")

        with open("debug_after_login.json", "w", encoding="utf-8") as f:
            json.dump(
                {
                    "url": url,
                    "cookies": [
                        {
                            "name": c["name"],
                            "value": c["value"][:80] + "..." if len(c["value"]) > 80 else c["value"],
                            "domain": c["domain"],
                        }
                        for c in cookies
                    ],
                    "token_check": token_check,
                    "localStorage_raw": local_storage[:2000] if local_storage else "{}",
                },
                f,
                indent=2,
                ensure_ascii=False,
            )
        print("Written to debug_after_login.json")


asyncio.run(debug())
