"""CodeBuddy auth flow: get state, setup account, create API key."""
import logging
import time
from typing import Optional

import httpx

from ..config import settings

log = logging.getLogger(__name__)


class CodeBuddyAuth:
    """Handles CodeBuddy API interactions after browser OAuth."""

    def __init__(self, cookies: list[dict]):
        self.client = httpx.Client(
            base_url=settings.CODEBUDDY_BASE_URL,
            timeout=30,
            verify=False,
            headers={
                "User-Agent": settings.CODEBUDDY_USER_AGENT,
                "Content-Type": "application/json",
            },
        )
        # Set cookies from browser
        for cookie in cookies:
            self.client.cookies.set(
                cookie["name"],
                cookie["value"],
                domain=cookie.get("domain", ""),
                path=cookie.get("path", "/"),
            )

    def close(self):
        self.client.close()

    @staticmethod
    def get_auth_state() -> dict:
        """Step 1: Get OAuth state + auth URL from CodeBuddy."""
        resp = httpx.post(
            f"{settings.CODEBUDDY_BASE_URL}/v2/plugin/auth/state",
            params={"platform": "IDE"},
            headers={
                "User-Agent": settings.CODEBUDDY_USER_AGENT,
                "Content-Type": "application/json",
            },
            verify=False,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        log.info(f"Got auth state: {data.get('data', {}).get('state', 'N/A')[:20]}...")
        return data.get("data", {})

    def setup_region(self) -> bool:
        """Step 3: Set region to Singapore after OAuth."""
        try:
            resp = self.client.post(
                "/console/login/account",
                json={
                    "attributes": {
                        "countryCode": [settings.CODEBUDDY_REGION_CODE],
                        "countryFullName": [settings.CODEBUDDY_REGION_FULL],
                        "countryName": [settings.CODEBUDDY_REGION_NAME],
                    }
                },
            )
            log.info(f"Region setup: {resp.status_code}")
            return resp.status_code in (200, 201, 204)
        except Exception as e:
            log.warning(f"Region setup failed (might already be set): {e}")
            return True  # Not critical

    def get_enterprise_id(self) -> Optional[str]:
        """Step 4: Get user's enterprise ID."""
        try:
            resp = self.client.get("/console/accounts")
            if resp.status_code == 200:
                data = resp.json()
                accounts = data.get("data", [])
                if accounts:
                    eid = accounts[0].get("id", "")
                    log.info(f"Enterprise ID: {eid}")
                    return eid
        except Exception as e:
            log.error(f"Failed to get enterprise ID: {e}")
        return None

    def register_user(self, user_id: str) -> bool:
        """Register user in overseas realm."""
        try:
            resp = self.client.get(
                f"/auth/realms/copilot/overseas/user/register",
                params={"userId": user_id},
            )
            log.info(f"User registration: {resp.status_code}")
            return resp.status_code in (200, 201, 204)
        except Exception as e:
            log.warning(f"User registration failed (might already exist): {e}")
            return True

    def activate_trial(self) -> bool:
        """Activate free trial."""
        try:
            resp = self.client.post("/billing/ide/trial")
            log.info(f"Trial activation: {resp.status_code}")
            return resp.status_code in (200, 201, 204)
        except Exception as e:
            log.warning(f"Trial activation failed (might already be active): {e}")
            return True

    def create_api_key(self, enterprise_id: str) -> Optional[str]:
        """Step 5: Create an API key. THE MONEY ENDPOINT."""
        key_name = f"aiproxy-{int(time.time())}"
        try:
            resp = self.client.post(
                "/console/api/client/v1/api-keys",
                json={
                    "name": key_name,
                    "expire_in_days": settings.KEY_EXPIRE_DAYS,
                    "user_enterprise_id": enterprise_id,
                },
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                api_key = data.get("data", {}).get("key", "")
                if api_key:
                    log.info(f"Created API key: {api_key[:10]}...")
                    return api_key
            log.error(f"Key creation failed: {resp.status_code} {resp.text[:200]}")
        except Exception as e:
            log.error(f"Key creation error: {e}")
        return None

    def get_quota(self) -> dict:
        """Check remaining quota/credits."""
        try:
            resp = self.client.post("/billing/meter/get-user-resource")
            if resp.status_code == 200:
                return resp.json().get("data", {})
        except Exception as e:
            log.error(f"Quota check failed: {e}")
        return {}

    def claim_gift(self) -> bool:
        """Claim daily gift credits."""
        try:
            # Check if already claimed
            check = self.client.post("/billing/meter/check-gift-claimed")
            if check.status_code == 200:
                data = check.json().get("data", {})
                if data.get("claimed", False):
                    log.info("Gift already claimed today")
                    return True

            # Claim it
            resp = self.client.post("/billing/meter/claim-gift")
            if resp.status_code in (200, 201):
                log.info("Gift claimed successfully")
                return True
            log.warning(f"Gift claim: {resp.status_code}")
        except Exception as e:
            log.warning(f"Gift claim failed: {e}")
        return False
