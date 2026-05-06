"""Google OAuth automation with JWT capture via Camoufox + Playwright."""
import asyncio
import json
import logging
import random
import base64
import time
from typing import Optional

from camoufox.async_api import AsyncCamoufox
from browserforge.fingerprints import Screen

log = logging.getLogger(__name__)


class GoogleOAuth:
    def __init__(self, email: str, password: str, config):
        self.email = email
        self.password = password
        self.config = config
        self.captured_jwt: Optional[str] = None
        self.captured_refresh: Optional[str] = None
        self.captured_user_id: Optional[str] = None
        self.captured_auth_code: Optional[str] = None

    async def login(self) -> dict:
        """
        Full automated Google OAuth login flow:
        1. Open Camoufox browser (anti-detect)
        2. Register response listener to capture JWT
        3. Navigate to CodeBuddy login/auth URL
        4. Handle CodeBuddy landing (ToS checkbox + "Continue with Google")
        5. Fill Google email
        6. Fill Google password
        7. Handle consent/account picker
        8. Wait for redirect to codebuddy.ai
        9. Fallback: call refresh endpoint from browser if JWT not captured
        10. Return result dict
        """
        try:
            proxy_config = None
            if self.config.PROXY_URL:
                proxy_config = {"server": self.config.PROXY_URL}

            async with AsyncCamoufox(
                headless=self.config.CAMOUFOX_HEADLESS,
                os="windows",
                block_webrtc=self.config.CAMOUFOX_BLOCK_WEBRTC,
                screen=Screen(max_width=self.config.CAMOUFOX_MAX_WIDTH, max_height=self.config.CAMOUFOX_MAX_HEIGHT),
                proxy=proxy_config,
                geoip=bool(self.config.PROXY_URL),
            ) as browser:
                page = await browser.new_page()

                # Register response interceptor for JWT capture
                page.on("response", self._on_response)

                # Register URL change listener to capture auth code from redirect
                def on_url_change(frame):
                    if frame == page.main_frame:
                        url = frame.url
                        if "codebuddy.ai" in url and "code=" in url:
                            import urllib.parse
                            parsed = urllib.parse.urlparse(url)
                            params = urllib.parse.parse_qs(parsed.query)
                            code = params.get("code", [None])[0]
                            if code and not self.captured_auth_code:
                                self.captured_auth_code = code
                                log.info(f"[{self.email}] Captured auth code from navigation: {code[:20]}...")

                page.on("framenavigated", on_url_change)

                # Navigate to CodeBuddy auth URL
                log.info(f"[{self.email}] Navigating to CodeBuddy login...")
                await page.goto(self.config.CODEBUDDY_AUTH_URL, wait_until="domcontentloaded", timeout=30000)
                await self._random_sleep(1, 3)

                # Check if we're on CodeBuddy landing page (needs ToS + Continue with Google)
                await self._handle_codebuddy_landing(page)

                # Now we should be on Google login page
                # Handle account picker if shown
                await self._handle_account_picker(page)

                # Fill email
                email_filled = await self._fill_email(page)
                if not email_filled:
                    return self._error_result("failed_email_input")

                # Check for errors after email
                error = await self._check_errors(page)
                if error:
                    return self._error_result(error)

                # Fill password
                password_filled = await self._fill_password(page)
                if not password_filled:
                    return self._error_result("failed_password_input")

                # Check for errors after password
                error = await self._check_errors(page)
                if error:
                    return self._error_result(error)

                # Handle consent screen if shown
                await self._handle_consent(page)

                # Wait for redirect back to codebuddy.ai
                await self._wait_for_redirect(page)

                # Try to capture JWT from the auth code in the redirect URL
                if not self.captured_jwt:
                    await self._exchange_auth_code(page)

                # If still not captured, try fallback strategies
                if not self.captured_jwt:
                    log.info(f"[{self.email}] JWT not captured via code exchange, trying fallback...")
                    await self._fallback_refresh(page)

                if self.captured_jwt:
                    user_id = self.captured_user_id or self._extract_sub(self.captured_jwt)
                    expires_at = self._extract_exp(self.captured_jwt)
                    log.info(f"[{self.email}] Login successful! user_id={user_id[:20]}...")
                    return {
                        "success": True,
                        "jwt_token": self.captured_jwt,
                        "refresh_token": self.captured_refresh or "",
                        "user_id": user_id,
                        "expires_at": expires_at,
                        "error": None,
                    }
                else:
                    return self._error_result("jwt_not_captured")

        except Exception as e:
            log.error(f"[{self.email}] Login exception: {e}")
            return self._error_result(f"exception: {str(e)}")

    async def _on_response(self, response):
        """Intercept responses to capture JWT tokens."""
        url = response.url
        try:
            # Watch for token-related responses
            if any(pattern in url for pattern in [
                "auth/realms/copilot/protocol/openid-connect/token",
                "token/refresh",
                "/v2/plugin/auth/token",
                "/v2/plugin/auth/login",
                "/api/auth",
            ]):
                body = await response.text()
                self._try_extract_token(body)
            # Also watch for any response that might contain a JWT
            elif response.status == 200 and "codebuddy.ai" in url:
                content_type = response.headers.get("content-type", "")
                if "json" in content_type:
                    body = await response.text()
                    if "eyJ" in body:  # JWT signature prefix
                        self._try_extract_token(body)
        except Exception:
            pass

    def _try_extract_token(self, body: str):
        """Try to extract JWT from response body."""
        try:
            data = json.loads(body)
            # Keycloak format
            if "access_token" in data:
                self.captured_jwt = data["access_token"]
                self.captured_refresh = data.get("refresh_token", "")
                log.debug(f"[{self.email}] Captured JWT from access_token field")
            # CodeBuddy format
            elif "accessToken" in data:
                self.captured_jwt = data["accessToken"]
                self.captured_refresh = data.get("refreshToken", "")
                log.debug(f"[{self.email}] Captured JWT from accessToken field")
        except (json.JSONDecodeError, KeyError):
            pass

    async def _handle_codebuddy_landing(self, page):
        """Handle Keycloak login page — click Google, handle ToS modal, confirm."""
        try:
            # Keycloak page has #social-google link with text "Log in with Google"
            google_link = page.locator('#social-google').first
            if await google_link.is_visible(timeout=5000):
                await google_link.click()
                log.info(f"[{self.email}] Clicked 'Log in with Google' on Keycloak")
                await self._random_sleep(1, 2)

                # A ToS modal appears — need to check the agreement checkbox and click Confirm
                # Check the policy checkbox in the modal
                policy_checkbox = page.locator('#agree-policy')
                try:
                    if await policy_checkbox.is_visible(timeout=3000):
                        await policy_checkbox.click()
                        await self._random_sleep(0.3, 0.8)
                except Exception:
                    pass

                # Click "Confirm" button in the modal
                confirm_btn = page.locator('button:has-text("Confirm"), a:has-text("Confirm")').first
                try:
                    if await confirm_btn.is_visible(timeout=3000):
                        await confirm_btn.click()
                        log.info(f"[{self.email}] Confirmed ToS modal")
                        await page.wait_for_load_state("domcontentloaded", timeout=15000)
                        await self._random_sleep(2, 4)
                except Exception:
                    pass

                # Wait for navigation to Google (URL should change to accounts.google.com)
                try:
                    await page.wait_for_url("**/accounts.google.com/**", timeout=15000)
                    await self._random_sleep(1, 2)
                except Exception:
                    log.warning(f"[{self.email}] Did not redirect to Google after ToS confirm")
        except Exception:
            # Not on Keycloak page, might already be on Google login
            pass

    async def _handle_account_picker(self, page):
        """Handle Google account picker if shown."""
        try:
            # Look for account picker with our email
            account_el = page.locator(f'[data-email="{self.email}"]').first
            if await account_el.is_visible(timeout=3000):
                await account_el.click()
                await self._random_sleep(1, 2)
                return

            # "Use another account" button
            another = page.locator('text="Use another account"').first
            if await another.is_visible(timeout=2000):
                await another.click()
                await self._random_sleep(1, 2)
        except Exception:
            pass

    async def _fill_email(self, page) -> bool:
        """Fill Google email field."""
        try:
            email_input = page.locator('#identifierId')
            await email_input.wait_for(state="visible", timeout=10000)
            await email_input.click()
            await self._random_sleep(0.3, 0.8)
            await email_input.type(self.email, delay=self.config.TYPING_DELAY_MS)
            await self._random_sleep(0.5, 1)

            # Click Next
            next_btn = page.locator('#identifierNext')
            await next_btn.click()
            await self._random_sleep(2, 4)
            return True
        except Exception as e:
            log.error(f"[{self.email}] Email input failed: {e}")
            return False

    async def _fill_password(self, page) -> bool:
        """Fill Google password field."""
        try:
            pwd_input = page.locator('input[name="Passwd"]')
            await pwd_input.wait_for(state="visible", timeout=10000)
            await pwd_input.click()
            await self._random_sleep(0.3, 0.8)
            await pwd_input.type(self.password, delay=self.config.TYPING_DELAY_MS)
            await self._random_sleep(0.5, 1)

            # Click Next
            next_btn = page.locator('#passwordNext')
            await next_btn.click()
            await self._random_sleep(2, 4)
            return True
        except Exception as e:
            log.error(f"[{self.email}] Password input failed: {e}")
            return False

    async def _handle_consent(self, page):
        """Handle Google consent/permission screen."""
        try:
            # Look for "Allow" or "Continue" button on consent screen
            allow_btn = page.locator('button:has-text("Allow")').first
            if await allow_btn.is_visible(timeout=3000):
                await allow_btn.click()
                await self._random_sleep(2, 3)
                return

            continue_btn = page.locator('button:has-text("Continue")').first
            if await continue_btn.is_visible(timeout=2000):
                await continue_btn.click()
                await self._random_sleep(2, 3)
        except Exception:
            pass

    async def _wait_for_redirect(self, page):
        """Wait for redirect back to codebuddy.ai and capture auth code from URL."""
        try:
            await page.wait_for_url("**/codebuddy.ai/**", timeout=30000)
            # Capture auth code from redirect URL before SPA navigates away
            import urllib.parse
            current_url = page.url
            parsed = urllib.parse.urlparse(current_url)
            params = urllib.parse.parse_qs(parsed.query)
            code = params.get("code", [None])[0]
            if code:
                self.captured_auth_code = code
                log.info(f"[{self.email}] Captured auth code from redirect URL")
            await self._random_sleep(2, 4)
            # Wait for network to settle
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception as e:
            log.warning(f"[{self.email}] Redirect wait: {e}")
            await self._random_sleep(3, 5)

    async def _exchange_auth_code(self, page):
        """Exchange the authorization code from redirect URL for JWT tokens via Keycloak token endpoint."""
        try:
            auth_code = self.captured_auth_code
            if not auth_code:
                # Try current URL as fallback
                import urllib.parse
                current_url = page.url
                parsed = urllib.parse.urlparse(current_url)
                params = urllib.parse.parse_qs(parsed.query)
                auth_code = params.get("code", [None])[0]

            if not auth_code:
                log.debug(f"[{self.email}] No auth code available for exchange")
                return

            log.info(f"[{self.email}] Got auth code: {auth_code[:20]}..., exchanging for tokens")

            # Exchange code for tokens via Keycloak token endpoint
            result = await page.evaluate("""async (code) => {
                try {
                    const params = new URLSearchParams();
                    params.append('grant_type', 'authorization_code');
                    params.append('client_id', 'console');
                    params.append('code', code);
                    params.append('redirect_uri', 'https://www.codebuddy.ai/');

                    const resp = await fetch('https://www.codebuddy.ai/auth/realms/copilot/protocol/openid-connect/token', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                        body: params.toString()
                    });

                    if (resp.ok) {
                        const data = await resp.json();
                        return {success: true, data: data};
                    }
                    const text = await resp.text();
                    return {success: false, status: resp.status, body: text.substring(0, 500)};
                } catch(e) {
                    return {success: false, error: e.message};
                }
            }""", auth_code)

            if result and result.get("success"):
                data = result["data"]
                self.captured_jwt = data.get("access_token", "")
                self.captured_refresh = data.get("refresh_token", "")
                if self.captured_jwt:
                    log.info(f"[{self.email}] JWT captured via Keycloak code exchange!")
                    return

            log.warning(f"[{self.email}] Code exchange failed: {result}")
        except Exception as e:
            log.warning(f"[{self.email}] Code exchange exception: {e}")

    async def _fallback_refresh(self, page):
        """Fallback: extract JWT from browser's localStorage/sessionStorage/cookies or trigger token fetch."""
        # Strategy 1: Check localStorage and sessionStorage for tokens
        try:
            token_data = await page.evaluate("""() => {
                const result = {};
                // Scan localStorage
                for (let i = 0; i < localStorage.length; i++) {
                    const key = localStorage.key(i);
                    const val = localStorage.getItem(key);
                    if (val && val.includes('eyJ')) {
                        try {
                            const parsed = JSON.parse(val);
                            if (parsed.access_token || parsed.accessToken || parsed.token) {
                                result.jwt = parsed.access_token || parsed.accessToken || parsed.token;
                                result.refresh = parsed.refresh_token || parsed.refreshToken || '';
                                return result;
                            }
                        } catch(e) {
                            // Value itself might be a JWT
                            if (val.startsWith('eyJ') && val.split('.').length === 3) {
                                result.jwt = val;
                                return result;
                            }
                        }
                    }
                }
                // Scan sessionStorage
                for (let i = 0; i < sessionStorage.length; i++) {
                    const key = sessionStorage.key(i);
                    const val = sessionStorage.getItem(key);
                    if (val && val.includes('eyJ')) {
                        try {
                            const parsed = JSON.parse(val);
                            if (parsed.access_token || parsed.accessToken || parsed.token) {
                                result.jwt = parsed.access_token || parsed.accessToken || parsed.token;
                                result.refresh = parsed.refresh_token || parsed.refreshToken || '';
                                return result;
                            }
                        } catch(e) {
                            if (val.startsWith('eyJ') && val.split('.').length === 3) {
                                result.jwt = val;
                                return result;
                            }
                        }
                    }
                }
                return result;
            }""")

            if token_data and token_data.get("jwt"):
                self.captured_jwt = token_data["jwt"]
                self.captured_refresh = token_data.get("refresh", "")
                log.info(f"[{self.email}] JWT captured from browser storage")
                return
        except Exception as e:
            log.debug(f"[{self.email}] Storage scan failed: {e}")

        # Strategy 2: Make an authenticated API call that returns user info with token
        try:
            result = await page.evaluate("""async () => {
                try {
                    // Try fetching user info endpoint which might return token
                    const resp = await fetch('/v2/plugin/user/info', {
                        method: 'GET',
                        headers: {
                            'Accept': 'application/json',
                            'X-Requested-With': 'XMLHttpRequest'
                        }
                    });
                    if (resp.ok) {
                        return {status: resp.status, body: await resp.text()};
                    }
                    return {status: resp.status, error: 'not ok'};
                } catch(e) {
                    return {error: e.message};
                }
            }""")
            if result and result.get("body") and "eyJ" in result.get("body", ""):
                self._try_extract_token(result["body"])
                if self.captured_jwt:
                    log.info(f"[{self.email}] JWT captured from user info endpoint")
                    return
        except Exception as e:
            log.debug(f"[{self.email}] User info fetch failed: {e}")

        # Strategy 3: Intercept outgoing request headers from the SPA
        # The SPA makes API calls with Authorization header — intercept it
        try:
            captured_auth = {}

            async def capture_request(route):
                headers = route.request.headers
                auth_header = headers.get("authorization", "")
                if auth_header and "eyJ" in auth_header:
                    captured_auth["jwt"] = auth_header
                    # Also grab refresh token if present
                    refresh = headers.get("x-refresh-token", "")
                    if refresh:
                        captured_auth["refresh"] = refresh
                await route.continue_()

            # Intercept all requests to codebuddy API
            await page.route("**/codebuddy.ai/v2/**", capture_request)
            await page.route("**/codebuddy.ai/api/**", capture_request)

            # Navigate to home to trigger SPA API calls
            await page.goto("https://www.codebuddy.ai/home", wait_until="networkidle", timeout=20000)
            await asyncio.sleep(5)

            # Unroute
            await page.unroute("**/codebuddy.ai/v2/**")
            await page.unroute("**/codebuddy.ai/api/**")

            if captured_auth.get("jwt"):
                self.captured_jwt = captured_auth["jwt"].replace("Bearer ", "")
                self.captured_refresh = captured_auth.get("refresh", "")
                log.info(f"[{self.email}] JWT captured from outgoing request headers")
                return
        except Exception as e:
            log.debug(f"[{self.email}] Request intercept failed: {e}")

        # Strategy 4: Use Keycloak token endpoint directly with the session cookies
        try:
            result = await page.evaluate("""async () => {
                try {
                    const resp = await fetch('https://www.codebuddy.ai/auth/realms/copilot/protocol/openid-connect/token', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                        body: 'grant_type=refresh_token&client_id=console&refresh_token='
                    });
                    // This will likely fail, but let's try userinfo instead
                    const userResp = await fetch('https://www.codebuddy.ai/auth/realms/copilot/protocol/openid-connect/userinfo');
                    if (userResp.ok) {
                        return {userinfo: await userResp.json(), status: 'ok'};
                    }
                    return {status: 'failed', code: userResp.status};
                } catch(e) {
                    return {error: e.message};
                }
            }""")
            log.debug(f"[{self.email}] Keycloak direct attempt: {result}")
        except Exception as e:
            log.debug(f"[{self.email}] Keycloak direct failed: {e}")

        log.warning(f"[{self.email}] All fallback strategies failed to capture JWT")

    async def _check_errors(self, page) -> Optional[str]:
        """Check for known error states."""
        try:
            # 2FA
            totp_pin = page.locator('#totpPin, input[name="totpPin"]')
            if await totp_pin.is_visible(timeout=2000):
                return "2fa_required"

            two_step_text = page.locator('text="2-Step Verification"')
            if await two_step_text.is_visible(timeout=1000):
                return "2fa_required"

            # Captcha
            captcha_img = page.locator('#captchaimg')
            if await captcha_img.is_visible(timeout=1000):
                return "captcha_detected"

            recaptcha_frame = page.locator('iframe[src*="recaptcha"]')
            if await recaptcha_frame.is_visible(timeout=1000):
                return "captcha_detected"

            # Account locked
            disabled_text = page.locator('text="This account has been disabled"')
            if await disabled_text.is_visible(timeout=1000):
                return "account_locked"

            # Rate limited
            rate_text = page.locator('text="Too many attempts"')
            if await rate_text.is_visible(timeout=1000):
                return "rate_limited"

        except Exception:
            pass
        return None

    async def _random_sleep(self, min_s: float, max_s: float):
        """Sleep for a random duration to mimic human behavior."""
        await asyncio.sleep(random.uniform(min_s, max_s))

    def _extract_sub(self, jwt_token: str) -> str:
        """Extract 'sub' claim from JWT."""
        try:
            token = jwt_token.replace("Bearer ", "")
            payload_b64 = token.split(".")[1]
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += "=" * padding
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            return payload.get("sub", "")
        except Exception:
            return ""

    def _extract_exp(self, jwt_token: str) -> str:
        """Extract expiry from JWT as ISO string."""
        try:
            token = jwt_token.replace("Bearer ", "")
            payload_b64 = token.split(".")[1]
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += "=" * padding
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            exp = payload.get("exp", 0)
            if exp:
                return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(exp))
        except Exception:
            pass
        return ""

    def _error_result(self, error: str) -> dict:
        return {
            "success": False,
            "jwt_token": None,
            "refresh_token": None,
            "user_id": None,
            "expires_at": None,
            "error": error,
        }
