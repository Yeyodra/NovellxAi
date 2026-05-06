"""Token refresh for CodeBuddy JWT tokens."""
import json
import time
import logging
from typing import Optional
import urllib.request
import urllib.error
import ssl
import gzip

log = logging.getLogger(__name__)

CODEBUDDY_BASE_URL = "https://www.codebuddy.ai"
REFRESH_ENDPOINT = f"{CODEBUDDY_BASE_URL}/v2/plugin/auth/token/refresh"


def refresh_token(jwt_token: str, refresh_tok: str, user_id: str) -> Optional[dict]:
    """
    Refresh a JWT token via CodeBuddy's refresh endpoint.
    
    Returns dict with new accessToken + refreshToken if successful.
    """
    if not jwt_token.startswith("Bearer "):
        jwt_token = f"Bearer {jwt_token}"

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": jwt_token,
        "X-Refresh-Token": refresh_tok,
        "X-Auth-Refresh-Source": "plugin",
        "X-User-Id": user_id,
        "X-Domain": "www.codebuddy.ai",
        "X-Product": "SaaS",
        "X-IDE-Type": "CLI",
        "X-IDE-Name": "CLI",
        "X-IDE-Version": "2.95.0",
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "CLI/2.95.0 CodeBuddy/2.95.0",
    }

    body = b"{}"

    # Gzip compress
    buf = gzip.compress(body)

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(REFRESH_ENDPOINT, data=buf, headers=headers, method="POST")
    req.add_header("Content-Encoding", "gzip")

    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            data = json.loads(resp.read().decode())
            if data.get("code") == 0 and data.get("data"):
                new_access = data["data"].get("accessToken", "")
                new_refresh = data["data"].get("refreshToken", refresh_tok)
                log.info(f"Token refreshed successfully (new token length: {len(new_access)})")
                return {
                    "accessToken": new_access,
                    "refreshToken": new_refresh,
                }
            else:
                log.error(f"Refresh failed: {data}")
                return None
    except urllib.error.HTTPError as e:
        log.error(f"Refresh HTTP error {e.code}: {e.read().decode()[:200]}")
        return None
    except Exception as e:
        log.error(f"Refresh error: {e}")
        return None
